#!/usr/sbin/env python

import click
import ipaddress
import json
import jsonpatch
import netaddr
import netifaces
import os
import re
import subprocess
import sys
import time
import itertools
import copy

from jsonpatch import JsonPatchConflict
from jsonpointer import JsonPointerException
from collections import OrderedDict
from generic_config_updater.generic_updater import GenericUpdater, ConfigFormat, extract_scope
from minigraph import parse_device_desc_xml, minigraph_encoder
from natsort import natsorted
from portconfig import get_child_ports
from socket import AF_INET, AF_INET6
from sonic_py_common import device_info, multi_asic
from sonic_py_common.interface import get_interface_table_name, get_port_table_name, get_intf_longname
from utilities_common import util_base
from swsscommon import swsscommon
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from utilities_common.db import Db
from utilities_common.intf_filter import parse_interface_in_filter
from utilities_common import bgp_util
import utilities_common.cli as clicommon
from utilities_common.helper import get_port_pbh_binding, get_port_acl_binding
from utilities_common.general import load_db_config, load_module_from_source
from .validated_config_db_connector import ValidatedConfigDBConnector
import utilities_common.multi_asic as multi_asic_util

from .utils import log

from . import aaa
from . import chassis_modules
from . import console
from . import feature
from . import flow_counters
from . import kdump
from . import kube
from . import muxcable
from . import nat
from . import vlan
from . import vxlan
from . import plugins
from .config_mgmt import ConfigMgmtDPB, ConfigMgmt
from . import mclag
from . import syslog

# mock masic APIs for unit test
try:
    if os.environ["UTILITIES_UNIT_TESTING"] == "1" or os.environ["UTILITIES_UNIT_TESTING"] == "2":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        tests_path = os.path.join(modules_path, "tests")
        sys.path.insert(0, modules_path)
        sys.path.insert(0, tests_path)
        import mock_tables.dbconnector
    if os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] == "multi_asic":
        import mock_tables.mock_multi_asic
        mock_tables.dbconnector.load_namespace_config()
except KeyError:
    pass


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

SONIC_GENERATED_SERVICE_PATH = '/etc/sonic/generated_services.conf'
SONIC_CFGGEN_PATH = '/usr/local/bin/sonic-cfggen'
VLAN_SUB_INTERFACE_SEPARATOR = '.'
ASIC_CONF_FILENAME = 'asic.conf'
DEFAULT_CONFIG_DB_FILE = '/etc/sonic/config_db.json'
DEFAULT_CONFIG_YANG_FILE = '/etc/sonic/config_yang.json'
NAMESPACE_PREFIX = 'asic'
INTF_KEY = "interfaces"
DEFAULT_GOLDEN_CONFIG_DB_FILE = '/etc/sonic/golden_config_db.json'

INIT_CFG_FILE = '/etc/sonic/init_cfg.json'

DEFAULT_NAMESPACE = ''
CFG_LOOPBACK_PREFIX = "Loopback"
CFG_LOOPBACK_PREFIX_LEN = len(CFG_LOOPBACK_PREFIX)
CFG_LOOPBACK_NAME_TOTAL_LEN_MAX = 11
CFG_LOOPBACK_ID_MAX_VAL = 999
CFG_LOOPBACK_NO="<0-999>"

CFG_PORTCHANNEL_PREFIX = "PortChannel"
CFG_PORTCHANNEL_PREFIX_LEN = 11
CFG_PORTCHANNEL_NAME_TOTAL_LEN_MAX = 15
CFG_PORTCHANNEL_MAX_VAL = 9999
CFG_PORTCHANNEL_NO="<0-9999>"

PORT_MTU = "mtu"
PORT_SPEED = "speed"
PORT_TPID = "tpid"
DEFAULT_TPID = "0x8100"

asic_type = None

DSCP_RANGE = click.IntRange(min=0, max=63)
TTL_RANGE = click.IntRange(min=0, max=255)
QUEUE_RANGE = click.IntRange(min=0, max=255)
GRE_TYPE_RANGE = click.IntRange(min=0, max=65535)
ADHOC_VALIDATION = True

# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')

#
# Helper functions
#

# Sort nested dict
def sort_dict(data):
    """ Sort of 1st level and 2nd level dict of data naturally by its key
        data: data to be sorted
    """
    if type(data) is not dict:
        return data

    for table in data:
        if type(data[table]) is dict:
            data[table] = OrderedDict(natsorted(data[table].items()))
    return OrderedDict(natsorted(data.items()))

# Read given JSON file
def read_json_file(fileName):
    try:
        with open(fileName) as f:
            result = json.load(f)
    except Exception as e:
        raise Exception(str(e))
    return result

def _get_breakout_options(ctx, args, incomplete):
    """ Provides dynamic mode option as per user argument i.e. interface name """
    all_mode_options = []
    interface_name = args[-1]

    breakout_cfg_file = device_info.get_path_to_port_config_file()

    if not os.path.isfile(breakout_cfg_file) or not breakout_cfg_file.endswith('.json'):
        return []
    else:
        breakout_file_input = read_json_file(breakout_cfg_file)
        if interface_name in breakout_file_input[INTF_KEY]:
            breakout_mode_options = [mode for i, v in breakout_file_input[INTF_KEY].items() if i == interface_name \
                                          for mode in v["breakout_modes"].keys()]
            all_mode_options = [str(c) for c in breakout_mode_options if incomplete in c]
        return all_mode_options

def _validate_interface_mode(ctx, breakout_cfg_file, interface_name, target_brkout_mode, cur_brkout_mode):
    """ Validate Parent interface and user selected mode before starting deletion or addition process """
    breakout_file_input = read_json_file(breakout_cfg_file)["interfaces"]

    if interface_name not in breakout_file_input:
        click.secho("[ERROR] {} is not a Parent port. So, Breakout Mode is not available on this port".format(interface_name), fg='red')
        return False

    # Check whether target breakout mode is available for the user-selected interface or not
    if target_brkout_mode not in breakout_file_input[interface_name]["breakout_modes"].keys():
        click.secho('[ERROR] Target mode {} is not available for the port {}'. format(target_brkout_mode, interface_name), fg='red')
        return False

    # Get config db context
    config_db = ctx.obj['config_db']
    port_dict = config_db.get_table('PORT')

    # Check whether there is any port in config db.
    if not port_dict:
        click.echo("port_dict is None!")
        return False

    # Check whether the  user-selected interface is part of  'port' table in config db.
    if interface_name not in port_dict:
        click.secho("[ERROR] {} is not in port_dict".format(interface_name))
        return False
    click.echo("\nRunning Breakout Mode : {} \nTarget Breakout Mode : {}".format(cur_brkout_mode, target_brkout_mode))
    if (cur_brkout_mode == target_brkout_mode):
        click.secho("[WARNING] No action will be taken as current and desired Breakout Mode are same.", fg='magenta')
        sys.exit(0)
    return True

def load_ConfigMgmt(verbose):
    """ Load config for the commands which are capable of change in config DB. """
    try:
        cm = ConfigMgmtDPB(debug=verbose)
        return cm
    except Exception as e:
        raise Exception("Failed to load the config. Error: {}".format(str(e)))

def breakout_warnUser_extraTables(cm, final_delPorts, confirm=True):
    """
    Function to warn user about extra tables while Dynamic Port Breakout(DPB).
    confirm: re-confirm from user to proceed.
    Config Tables Without Yang model considered extra tables.
    cm =  instance of config MGMT class.
    """
    try:
        # check if any extra tables exist
        eTables = cm.tablesWithOutYang()
        if len(eTables):
            # find relavent tables in extra tables, i.e. one which can have deleted
            # ports
            tables = cm.configWithKeys(configIn=eTables, keys=final_delPorts)
            click.secho("Below Config can not be verified, It may cause harm "\
                "to the system\n {}".format(json.dumps(tables, indent=2)))
            click.confirm('Do you wish to Continue?', abort=True)
    except Exception as e:
        raise Exception("Failed in breakout_warnUser_extraTables. Error: {}".format(str(e)))
    return

def breakout_Ports(cm, delPorts=list(), portJson=dict(), force=False, \
    loadDefConfig=False, verbose=False):

    deps, ret = cm.breakOutPort(delPorts=delPorts,  portJson=portJson, \
                    force=force, loadDefConfig=loadDefConfig)
    # check if DPB failed
    if ret == False:
        if not force and deps:
            click.echo("Dependencies Exist. No further action will be taken")
            click.echo("*** Printing dependencies ***")
            for dep in deps:
                click.echo(dep)
            sys.exit(0)
        else:
            click.echo("[ERROR] Port breakout Failed!!! Opting Out")
            raise click.Abort()
        return

#
# Helper functions
#


def _get_device_type():
    """
    Get device type

    TODO: move to sonic-py-common
    """

    command = [SONIC_CFGGEN_PATH, "-m", "-v", "DEVICE_METADATA.localhost.type"]
    proc = subprocess.Popen(command, text=True, stdout=subprocess.PIPE)
    device_type, err = proc.communicate()
    if err:
        click.echo("Could not get the device type from minigraph, setting device type to Unknown")
        device_type = 'Unknown'
    else:
        device_type = device_type.strip()

    return device_type

def interface_alias_to_name(config_db, interface_alias):
    """Return default interface name if alias name is given as argument
    """
    vlan_id = ""
    sub_intf_sep_idx = -1
    if interface_alias is not None:
        sub_intf_sep_idx = interface_alias.find(VLAN_SUB_INTERFACE_SEPARATOR)
        if sub_intf_sep_idx != -1:
            vlan_id = interface_alias[sub_intf_sep_idx + 1:]
            # interface_alias holds the parent port name so the subsequent logic still applies
            interface_alias = interface_alias[:sub_intf_sep_idx]

    # If the input parameter config_db is None, derive it from interface.
    # In single ASIC platform, get_port_namespace() returns DEFAULT_NAMESPACE.
    if config_db is None:
        namespace = get_port_namespace(interface_alias)
        if namespace is None:
            return None
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)

    config_db.connect()
    port_dict = config_db.get_table('PORT')

    if interface_alias is not None:
        if not port_dict:
            click.echo("port_dict is None!")
            raise click.Abort()
        for port_name in port_dict:
            if interface_alias == port_dict[port_name]['alias']:
                return port_name if sub_intf_sep_idx == -1 else port_name + VLAN_SUB_INTERFACE_SEPARATOR + vlan_id

    # Interface alias not in port_dict, just return interface_alias, e.g.,
    # portchannel is passed in as argument, which does not have an alias
    return interface_alias if sub_intf_sep_idx == -1 else interface_alias + VLAN_SUB_INTERFACE_SEPARATOR + vlan_id

def interface_name_is_valid(config_db, interface_name):
    """Check if the interface name is valid
    """
    # If the input parameter config_db is None, derive it from interface.
    # In single ASIC platform, get_port_namespace() returns DEFAULT_NAMESPACE.
    if config_db is None:
        namespace = get_port_namespace(interface_name)
        if namespace is None:
            return False
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)

    config_db.connect()
    port_dict = config_db.get_table('PORT')
    port_channel_dict = config_db.get_table('PORTCHANNEL')
    sub_port_intf_dict = config_db.get_table('VLAN_SUB_INTERFACE')
    loopback_dict = config_db.get_table('LOOPBACK_INTERFACE')

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)

    if interface_name is not None:
        if not port_dict:
            click.echo("port_dict is None!")
            raise click.Abort()
        for port_name in port_dict:
            if interface_name == port_name:
                return True
        if port_channel_dict:
            for port_channel_name in port_channel_dict:
                if interface_name == port_channel_name:
                    return True
        if sub_port_intf_dict:
            for sub_port_intf_name in sub_port_intf_dict:
                if interface_name == sub_port_intf_name:
                    return True
        if loopback_dict:
            for loopback_name in loopback_dict:
                if interface_name == loopback_name:
                    return True
    return False

def interface_name_to_alias(config_db, interface_name):
    """Return alias interface name if default name is given as argument
    """
    # If the input parameter config_db is None, derive it from interface.
    # In single ASIC platform, get_port_namespace() returns DEFAULT_NAMESPACE.
    if config_db is None:
        namespace = get_port_namespace(interface_name)
        if namespace is None:
            return None
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)

    config_db.connect()
    port_dict = config_db.get_table('PORT')

    if interface_name is not None:
        if not port_dict:
            click.echo("port_dict is None!")
            raise click.Abort()
        for port_name in port_dict:
            if interface_name == port_name:
                return port_dict[port_name]['alias']

    return None

def get_interface_ipaddresses(config_db, interface_name):
    """Get IP addresses attached to interface
    """
    ipaddresses = set()
    table_name = get_interface_table_name(interface_name)
    if not table_name:
        return ipaddresses

    keys = config_db.get_keys(table_name)
    for key in keys:
        if isinstance(key, tuple) and len(key) == 2:
            iface, interface_ip = key
            if iface == interface_name:
                ipaddresses.add(ipaddress.ip_interface(interface_ip))

    return ipaddresses

def is_vrf_exists(config_db, vrf_name):
    """Check if VRF exists
    """
    keys = config_db.get_keys("VRF")
    if vrf_name in keys:
        return True
    elif vrf_name == "mgmt" or vrf_name == "management":
        entry = config_db.get_entry("MGMT_VRF_CONFIG", "vrf_global")
        if entry and entry.get("mgmtVrfEnabled") == "true":
            return True

    return False

def is_interface_bind_to_vrf(config_db, interface_name):
    """Get interface if bind to vrf or not
    """
    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        return False
    entry = config_db.get_entry(table_name, interface_name)
    if entry and entry.get("vrf_name"):
        return True
    return False

def is_portchannel_name_valid(portchannel_name):
    """Port channel name validation
    """

    # Return True if Portchannel name is PortChannelXXXX (XXXX can be 0-9999)
    if portchannel_name[:CFG_PORTCHANNEL_PREFIX_LEN] != CFG_PORTCHANNEL_PREFIX:
        return False
    if (portchannel_name[CFG_PORTCHANNEL_PREFIX_LEN:].isdigit() is False or
          int(portchannel_name[CFG_PORTCHANNEL_PREFIX_LEN:]) > CFG_PORTCHANNEL_MAX_VAL) :
        return False
    if len(portchannel_name) > CFG_PORTCHANNEL_NAME_TOTAL_LEN_MAX:
        return False
    return True

def is_portchannel_present_in_db(db, portchannel_name):
    """Check if Portchannel is present in Config DB
    """

    # Return True if Portchannel name exists in the CONFIG_DB
    portchannel_list = db.get_table(CFG_PORTCHANNEL_PREFIX)
    if portchannel_list is None:
        return False
    if portchannel_name in portchannel_list:
        return True
    return False

def is_port_member_of_this_portchannel(db, port_name, portchannel_name):
    """Check if a port is member of given portchannel
    """
    portchannel_list = db.get_table(CFG_PORTCHANNEL_PREFIX)
    if portchannel_list is None:
        return False

    for k, v in db.get_table('PORTCHANNEL_MEMBER'):
        if (k == portchannel_name) and (v == port_name):
            return True

    return False

# Return the namespace where an interface belongs
# The port name input could be in default mode or in alias mode.
def get_port_namespace(port):
    # If it is a non multi-asic platform, or if the interface is management interface
    # return DEFAULT_NAMESPACE
    if not multi_asic.is_multi_asic() or port == 'eth0':
        return DEFAULT_NAMESPACE

    # Get the table to check for interface presence
    table_name = get_port_table_name(port)
    if table_name == "":
        return None

    ns_list = multi_asic.get_all_namespaces()
    namespaces = ns_list['front_ns'] + ns_list['back_ns']
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()

        # If the interface naming mode is alias, search the tables for alias_name.
        if clicommon.get_interface_naming_mode() == "alias":
            port_dict = config_db.get_table(table_name)
            if port_dict:
                for port_name in port_dict:
                    if port == port_dict[port_name]['alias']:
                        return namespace
        else:
            entry = config_db.get_entry(table_name, port)
            if entry:
                return namespace

    return None

def del_interface_bind_to_vrf(config_db, vrf_name):
    """del interface bind to vrf
    """
    tables = ['INTERFACE', 'PORTCHANNEL_INTERFACE', 'VLAN_INTERFACE', 'LOOPBACK_INTERFACE']
    for table_name in tables:
        interface_dict = config_db.get_table(table_name)
        if interface_dict:
            for interface_name in interface_dict:
                if 'vrf_name' in interface_dict[interface_name] and vrf_name == interface_dict[interface_name]['vrf_name']:
                    interface_ipaddresses = get_interface_ipaddresses(config_db, interface_name)
                    for ipaddress in interface_ipaddresses:
                        remove_router_interface_ip_address(config_db, interface_name, ipaddress)
                    config_db.set_entry(table_name, interface_name, None)

def set_interface_naming_mode(mode):
    """Modify SONIC_CLI_IFACE_MODE env variable in user .bashrc
    """
    user = os.getenv('SUDO_USER')
    bashrc_ifacemode_line = "export SONIC_CLI_IFACE_MODE={}".format(mode)

    # In case of multi-asic, we can check for the alias mode support in any of
    # the namespaces as this setting of alias mode should be identical everywhere.
    # Here by default we set the namespaces to be a list just having '' which
    # represents the linux host. In case of multi-asic, we take the first namespace
    # created for the front facing ASIC.

    namespaces = [DEFAULT_NAMESPACE]
    if multi_asic.is_multi_asic():
        namespaces = multi_asic.get_all_namespaces()['front_ns']

    # Ensure all interfaces have an 'alias' key in PORT dict
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespaces[0])
    config_db.connect()
    port_dict = config_db.get_table('PORT')

    if not port_dict:
        click.echo("port_dict is None!")
        raise click.Abort()

    for port_name in port_dict:
        try:
            if port_dict[port_name]['alias']:
                pass
        except KeyError:
            click.echo("Platform does not support alias mapping")
            raise click.Abort()

    if not user:
        user = os.getenv('USER')

    if user != "root":
        bashrc = "/home/{}/.bashrc".format(user)
    else:
        click.get_current_context().fail("Cannot set interface naming mode for root user!")

    f = open(bashrc, 'r')
    filedata = f.read()
    f.close()

    if "SONIC_CLI_IFACE_MODE" not in filedata:
        newdata = filedata + bashrc_ifacemode_line
        newdata += "\n"
    else:
        newdata = re.sub(r"export SONIC_CLI_IFACE_MODE=\w+",
                         bashrc_ifacemode_line, filedata)
    f = open(bashrc, 'w')
    f.write(newdata)
    f.close()
    click.echo("Please logout and log back in for changes take effect.")

def get_intf_ipv6_link_local_mode(ctx, interface_name, table_name):
    config_db = ctx.obj["config_db"]
    intf = config_db.get_table(table_name)
    if interface_name in intf:
        if 'ipv6_use_link_local_only' in intf[interface_name]:
            return intf[interface_name]['ipv6_use_link_local_only']
        else:
            return "disable"
    else:
        return ""

def _is_neighbor_ipaddress(config_db, ipaddress):
    """Returns True if a neighbor has the IP address <ipaddress>, False if not
    """
    entry = config_db.get_entry('BGP_NEIGHBOR', ipaddress)
    return True if entry else False

def _get_all_neighbor_ipaddresses(config_db):
    """Returns list of strings containing IP addresses of all BGP neighbors
    """
    addrs = []
    bgp_sessions = config_db.get_table('BGP_NEIGHBOR')
    for addr, session in bgp_sessions.items():
        addrs.append(addr)
    return addrs

def _get_neighbor_ipaddress_list_by_hostname(config_db, hostname):
    """Returns list of strings, each containing an IP address of neighbor with
       hostname <hostname>. Returns empty list if <hostname> not a neighbor
    """
    addrs = []
    bgp_sessions = config_db.get_table('BGP_NEIGHBOR')
    for addr, session in bgp_sessions.items():
        if 'name' in session and session['name'] == hostname:
            addrs.append(addr)
    return addrs

def _change_bgp_session_status_by_addr(config_db, ipaddress, status, verbose):
    """Start up or shut down BGP session by IP address
    """
    verb = 'Starting' if status == 'up' else 'Shutting'
    click.echo("{} {} BGP session with neighbor {}...".format(verb, status, ipaddress))

    config_db.mod_entry('bgp_neighbor', ipaddress, {'admin_status': status})

def _change_bgp_session_status(config_db, ipaddr_or_hostname, status, verbose):
    """Start up or shut down BGP session by IP address or hostname
    """
    ip_addrs = []

    # If we were passed an IP address, convert it to lowercase because IPv6 addresses were
    # stored in ConfigDB with all lowercase alphabet characters during minigraph parsing
    if _is_neighbor_ipaddress(config_db, ipaddr_or_hostname.lower()):
        ip_addrs.append(ipaddr_or_hostname.lower())
    else:
        # If <ipaddr_or_hostname> is not the IP address of a neighbor, check to see if it's a hostname
        ip_addrs = _get_neighbor_ipaddress_list_by_hostname(config_db, ipaddr_or_hostname)

    if not ip_addrs:
        return False

    for ip_addr in ip_addrs:
        _change_bgp_session_status_by_addr(config_db, ip_addr, status, verbose)

    return True

def _validate_bgp_neighbor(config_db, neighbor_ip_or_hostname):
    """validates whether the given ip or host name is a BGP neighbor
    """
    ip_addrs = []
    if _is_neighbor_ipaddress(config_db, neighbor_ip_or_hostname.lower()):
        ip_addrs.append(neighbor_ip_or_hostname.lower())
    else:
        ip_addrs = _get_neighbor_ipaddress_list_by_hostname(config_db, neighbor_ip_or_hostname.upper())

    return ip_addrs

def _remove_bgp_neighbor_config(config_db, neighbor_ip_or_hostname):
    """Removes BGP configuration of the given neighbor
    """
    ip_addrs = _validate_bgp_neighbor(config_db, neighbor_ip_or_hostname)

    if not ip_addrs:
        return False

    for ip_addr in ip_addrs:
        config_db.mod_entry('bgp_neighbor', ip_addr, None)
        click.echo("Removed configuration of BGP neighbor {}".format(ip_addr))

    return True

def _change_hostname(hostname):
    current_hostname = os.uname()[1]
    if current_hostname != hostname:
        clicommon.run_command('echo {} > /etc/hostname'.format(hostname), display_cmd=True)
        clicommon.run_command('hostname -F /etc/hostname', display_cmd=True)
        clicommon.run_command(r'sed -i "/\s{}$/d" /etc/hosts'.format(current_hostname), display_cmd=True)
        clicommon.run_command('echo "127.0.0.1 {}" >> /etc/hosts'.format(hostname), display_cmd=True)

def _clear_cbf():
    CBF_TABLE_NAMES = [
            'DSCP_TO_FC_MAP',
            'EXP_TO_FC_MAP']

    namespace_list = [DEFAULT_NAMESPACE]
    if multi_asic.get_num_asics() > 1:
        namespace_list = multi_asic.get_namespaces_from_linux()

    for ns in namespace_list:
        if ns is DEFAULT_NAMESPACE:
            config_db = ConfigDBConnector()
        else:
            config_db = ConfigDBConnector(
                use_unix_socket_path=True, namespace=ns
            )
        config_db.connect()
        for cbf_table in CBF_TABLE_NAMES:
            config_db.delete_table(cbf_table)

#API to validate the interface passed for storm-control configuration
def storm_control_interface_validate(port_name):
    if clicommon.get_interface_naming_mode() == "alias":
        port_name = interface_alias_to_name(None, port_name)
        if port_name is None:
            click.echo("'port_name' is None!")
            return False

    if (port_name.startswith("Ethernet")):
        if interface_name_is_valid(None, port_name) is False:
            click.echo("Interface name %s is invalid. Please enter a valid interface name" %(port_name))
            return False
    else:
        click.echo("Storm-control is supported only on Ethernet interfaces. Not supported on %s" %(port_name))
        return False

    return True

def is_storm_control_supported(storm_type, namespace):
    asic_id = multi_asic.get_asic_index_from_namespace(namespace)
    #state_db[asic_id] = swsscommon.DBConnector("STATE_DB", REDIS_TIMEOUT_MSECS, True, namespace)
    #supported = state_db[asic_id].get_entry('BUM_STORM_CAPABILITY', storm_type)
    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)
    entry_name="BUM_STORM_CAPABILITY|"+storm_type
    supported = state_db.get(state_db.STATE_DB, entry_name,"supported")
    return supported

#API to configure the PORT_STORM_CONTROL table
def storm_control_set_entry(port_name, kbps, storm_type, namespace):

    if storm_control_interface_validate(port_name) is False:
        return False

    if is_storm_control_supported(storm_type, namespace) == 0:
        click.echo("Storm-control is not supported on this namespace {}".format(namespace))
        return False

    #Validate kbps value
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    key = port_name + '|' + storm_type
    entry = config_db.get_entry('PORT_STORM_CONTROL', key)

    if len(entry) == 0:
        try:
            config_db.set_entry('PORT_STORM_CONTROL', key, {'kbps':kbps})
        except ValueError as e:
            ctx = click.get_current_context()
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        kbps_value = int(entry.get('kbps',0))
        if kbps_value != kbps:
            try:
                config_db.mod_entry('PORT_STORM_CONTROL', key, {'kbps':kbps})
            except ValueError as e:
                ctx = click.get_current_context()
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    return True

#API to remove an entry from PORT_STORM_CONTROL table
def storm_control_delete_entry(port_name, storm_type):

    if storm_control_interface_validate(port_name) is False:
        return False

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    key = port_name + '|' + storm_type
    entry = config_db.get_entry('PORT_STORM_CONTROL', key)

    if len(entry) == 0:
        click.echo("%s storm-control not enabled on interface %s" %(storm_type, port_name))
        return False
    else:
        try:
            config_db.set_entry('PORT_STORM_CONTROL', key, None)
        except JsonPatchConflict as e:
            ctx = click.get_current_context()
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    return True


def _wait_until_clear(tables, interval=0.5, timeout=30, verbose=False):
    start = time.time()
    empty = False
    app_db = SonicV2Connector(host='127.0.0.1')
    app_db.connect(app_db.APPL_DB)

    while not empty and time.time() - start < timeout:
        non_empty_table_count = 0
        for table in tables:
            keys = app_db.keys(app_db.APPL_DB, table)
            if keys:
                non_empty_table_count += 1
                if verbose:
                    click.echo("Some entries matching {} still exist: {}".format(table, keys[0]))
                time.sleep(interval)
        empty = (non_empty_table_count == 0)
    if not empty:
        click.echo("Operation not completed successfully, please save and reload configuration.")
    return empty


def _clear_qos(delay=False, verbose=False):
    QOS_TABLE_NAMES = [
            'PORT_QOS_MAP',
            'QUEUE',
            'TC_TO_PRIORITY_GROUP_MAP',
            'MAP_PFC_PRIORITY_TO_QUEUE',
            'TC_TO_QUEUE_MAP',
            'DSCP_TO_TC_MAP',
            'MPLS_TC_TO_TC_MAP',
            'SCHEDULER',
            'PFC_PRIORITY_TO_PRIORITY_GROUP_MAP',
            'WRED_PROFILE',
            'CABLE_LENGTH',
            'BUFFER_PG',
            'BUFFER_QUEUE',
            'BUFFER_PORT_INGRESS_PROFILE_LIST',
            'BUFFER_PORT_EGRESS_PROFILE_LIST',
            'BUFFER_PROFILE',
            'BUFFER_POOL',
            'DEFAULT_LOSSLESS_BUFFER_PARAMETER',
            'LOSSLESS_TRAFFIC_PATTERN']

    namespace_list = [DEFAULT_NAMESPACE]
    if multi_asic.get_num_asics() > 1:
        namespace_list = multi_asic.get_namespaces_from_linux()

    for ns in namespace_list:
        if ns is DEFAULT_NAMESPACE:
            config_db = ConfigDBConnector()
        else:
            config_db = ConfigDBConnector(
                use_unix_socket_path=True, namespace=ns
            )
        config_db.connect()
        for qos_table in QOS_TABLE_NAMES:
            config_db.delete_table(qos_table)
    if delay:
        device_metadata = config_db.get_entry('DEVICE_METADATA', 'localhost')
        # Traditional buffer manager do not remove buffer tables in any case, no need to wait.
        timeout = 120 if device_metadata and device_metadata.get('buffer_model') == 'dynamic' else 0
        _wait_until_clear(["BUFFER_*_TABLE:*", "BUFFER_*_SET"], interval=0.5, timeout=timeout, verbose=verbose)

def _get_sonic_generated_services(num_asic):
    if not os.path.isfile(SONIC_GENERATED_SERVICE_PATH):
        return None
    generated_services_list = []
    generated_multi_instance_services = []
    with open(SONIC_GENERATED_SERVICE_PATH) as generated_service_file:
        for line in generated_service_file:
            if '@' in line:
                line = line.replace('@', '')
                if num_asic > 1:
                    generated_multi_instance_services.append(line.rstrip('\n'))
                else:
                    generated_services_list.append(line.rstrip('\n'))
            else:
                generated_services_list.append(line.rstrip('\n'))
    return generated_services_list, generated_multi_instance_services

# Callback for confirmation prompt. Aborts if user enters "n"
def _abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


def _get_disabled_services_list(config_db):
    disabled_services_list = []

    feature_table = config_db.get_table('FEATURE')
    if feature_table is not None:
        for feature_name in feature_table:
            if not feature_name:
                log.log_warning("Feature is None")
                continue

            state = feature_table[feature_name]['state']
            if not state:
                log.log_warning("Enable state of feature '{}' is None".format(feature_name))
                continue

            if state == "disabled":
                disabled_services_list.append(feature_name)
    else:
        log.log_warning("Unable to retreive FEATURE table")

    return disabled_services_list


def _stop_services():
    try:
        subprocess.check_call(['sudo', 'monit', 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        click.echo("Disabling container monitoring ...")
        clicommon.run_command("sudo monit unmonitor container_checker")
    except subprocess.CalledProcessError as err:
        pass

    click.echo("Stopping SONiC target ...")
    clicommon.run_command("sudo systemctl stop sonic.target --job-mode replace-irreversibly")


def _get_sonic_services():
    out, _ = clicommon.run_command("systemctl list-dependencies --plain sonic.target | sed '1d'", return_cmd=True)
    return (unit.strip() for unit in out.splitlines())


def _reset_failed_services():
    for service in _get_sonic_services():
        clicommon.run_command("systemctl reset-failed {}".format(service))


def _restart_services():
    click.echo("Restarting SONiC target ...")
    clicommon.run_command("sudo systemctl restart sonic.target")

    try:
        subprocess.check_call(['sudo', 'monit', 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        click.echo("Enabling container monitoring ...")
        clicommon.run_command("sudo monit monitor container_checker")
    except subprocess.CalledProcessError as err:
        pass

    # Reload Monit configuration to pick up new hostname in case it changed
    click.echo("Reloading Monit configuration ...")
    clicommon.run_command("sudo monit reload")


def _per_namespace_swss_ready(service_name):
    out, _ = clicommon.run_command("systemctl show {} --property ActiveState --value".format(service_name), return_cmd=True)
    if out.strip() != "active":
        return False
    out, _ = clicommon.run_command("systemctl show {} --property ActiveEnterTimestampMonotonic --value".format(service_name), return_cmd=True)
    swss_up_time = float(out.strip())/1000000
    now =  time.monotonic()
    if (now - swss_up_time > 120):
        return True
    else:
        return False

def _swss_ready():
    list_of_swss = []
    num_asics = multi_asic.get_num_asics()
    if num_asics == 1:
        list_of_swss.append("swss.service")
    else:
        for asic in range(num_asics):
            service = "swss@{}.service".format(asic)
            list_of_swss.append(service)

    for service_name in list_of_swss:
        if _per_namespace_swss_ready(service_name) == False:
            return False

    return True

def _is_system_starting():
    out, _ = clicommon.run_command("sudo systemctl is-system-running", return_cmd=True)
    return out.strip() == "starting"

def interface_is_in_vlan(vlan_member_table, interface_name):
    """ Check if an interface is in a vlan """
    for _, intf in vlan_member_table:
        if intf == interface_name:
            return True

    return False

def interface_is_in_portchannel(portchannel_member_table, interface_name):
    """ Check if an interface is part of portchannel """
    for _, intf in portchannel_member_table:
        if intf == interface_name:
            return True

    return False

def check_mirror_direction_config(v, direction):
    """ Check if port is already configured for mirror in same direction """
    if direction:
        direction = direction.upper()
        if ('direction' in v and v['direction'] == 'BOTH') or (direction == 'BOTH'):
            return True
        if 'direction' in v and v['direction'] == direction:
            return True
    else:
        return True

def interface_has_mirror_config(ctx, mirror_table, dst_port, src_port, direction):
    """ Check if dst/src port is already configured with mirroring in same direction """
    for _, v in mirror_table.items():
        if src_port:
            for port in src_port.split(","):
                if 'dst_port' in v and v['dst_port'] == port:
                    ctx.fail("Error: Source Interface {} already has mirror config".format(port))
                if 'src_port' in v and re.search(port,v['src_port']):
                    if check_mirror_direction_config(v, direction):
                        ctx.fail("Error: Source Interface {} already has mirror config in same direction".format(port))
        if dst_port:
            if ('dst_port' in v and v['dst_port'] == dst_port) or ('src_port' in v and re.search(dst_port,v['src_port'])):
                ctx.fail("Error: Destination Interface {} already has mirror config".format(dst_port))

    return False

def validate_mirror_session_config(config_db, session_name, dst_port, src_port, direction):
    """ Check if SPAN mirror-session config is valid """
    ctx = click.get_current_context()
    if len(config_db.get_entry('MIRROR_SESSION', session_name)) != 0:
        click.echo("Error: {} already exists".format(session_name))
        return False

    vlan_member_table = config_db.get_table('VLAN_MEMBER')
    mirror_table = config_db.get_table('MIRROR_SESSION')
    portchannel_member_table = config_db.get_table('PORTCHANNEL_MEMBER')

    if dst_port:
        if not interface_name_is_valid(config_db, dst_port):
            ctx.fail("Error: Destination Interface {} is invalid".format(dst_port))

        if is_portchannel_present_in_db(config_db, dst_port):
            ctx.fail("Error: Destination Interface {} is not supported".format(dst_port))

        if interface_is_in_vlan(vlan_member_table, dst_port):
            ctx.fail("Error: Destination Interface {} has vlan config".format(dst_port))


        if interface_is_in_portchannel(portchannel_member_table, dst_port):
            ctx.fail("Error: Destination Interface {} has portchannel config".format(dst_port))

        if clicommon.is_port_router_interface(config_db, dst_port):
            ctx.fail("Error: Destination Interface {} is a L3 interface".format(dst_port))

    if src_port:
        for port in src_port.split(","):
            if not interface_name_is_valid(config_db, port):
                ctx.fail("Error: Source Interface {} is invalid".format(port))
            if dst_port and dst_port == port:
                ctx.fail("Error: Destination Interface cant be same as Source Interface")

    if interface_has_mirror_config(ctx, mirror_table, dst_port, src_port, direction):
        return False

    if direction:
        if direction not in ['rx', 'tx', 'both']:
            ctx.fail("Error: Direction {} is invalid".format(direction))

    return True

def cli_sroute_to_config(ctx, command_str, strict_nh = True):
    if len(command_str) < 2 or len(command_str) > 9:
        ctx.fail("argument is not in pattern prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>!")
    if "prefix" not in command_str:
        ctx.fail("argument is incomplete, prefix not found!")
    if "nexthop" not in command_str and strict_nh:
        ctx.fail("argument is incomplete, nexthop not found!")

    nexthop_str = None
    config_entry = {}
    vrf_name = ""
    config_db = ctx.obj['config_db']

    if "nexthop" in command_str:
        idx = command_str.index("nexthop")
        prefix_str = command_str[:idx]
        nexthop_str = command_str[idx:]
    else:
        prefix_str = command_str[:]

    if prefix_str:
        if 'prefix' in prefix_str and 'vrf' in prefix_str:
            # prefix_str: ['prefix', 'vrf', Vrf-name, ip]
            vrf_name = prefix_str[2]
            if not is_vrf_exists(config_db, vrf_name):
                ctx.fail("VRF %s does not exist!"%(vrf_name))
            ip_prefix = prefix_str[3]
        elif 'prefix' in prefix_str:
            # prefix_str: ['prefix', ip]
            ip_prefix = prefix_str[1]
            vrf_name = "default"
        else:
            ctx.fail("prefix is not in pattern!")

    if nexthop_str:
        if 'nexthop' in nexthop_str and 'vrf' in nexthop_str:
            # nexthop_str: ['nexthop', 'vrf', Vrf-name, ip]
            config_entry["nexthop"] = nexthop_str[3]
            if not is_vrf_exists(config_db, nexthop_str[2]):
                ctx.fail("VRF %s does not exist!"%(nexthop_str[2]))
            config_entry["nexthop-vrf"] = nexthop_str[2]
        elif 'nexthop' in nexthop_str and 'dev' in nexthop_str:
            # nexthop_str: ['nexthop', 'dev', ifname]
            config_entry["ifname"] = nexthop_str[2]
        elif 'nexthop' in nexthop_str:
            # nexthop_str: ['nexthop', ip]
            config_entry["nexthop"] = nexthop_str[1]
        else:
            ctx.fail("nexthop is not in pattern!")

    try:
        ipaddress.ip_network(ip_prefix)
        if 'nexthop' in config_entry:
            nh_list = config_entry['nexthop'].split(',')
            for nh in nh_list:
                # Nexthop to portchannel
                if nh.startswith('PortChannel'):
                    config_db = ctx.obj['config_db']
                    if not nh in config_db.get_keys('PORTCHANNEL'):
                        ctx.fail("portchannel does not exist.")
                else:
                    ipaddress.ip_address(nh)
    except ValueError:
        ctx.fail("ip address is not valid.")

    if not vrf_name == "":
        key = vrf_name + "|" + ip_prefix
    else:
        key = ip_prefix

    return key, config_entry

def update_sonic_environment():
    """Prepare sonic environment variable using SONiC environment template file.
    """
    SONIC_ENV_TEMPLATE_FILE = os.path.join('/', "usr", "share", "sonic", "templates", "sonic-environment.j2")
    SONIC_VERSION_YML_FILE = os.path.join('/', "etc", "sonic", "sonic_version.yml")
    SONIC_ENV_FILE = os.path.join('/', "etc", "sonic", "sonic-environment")

    if os.path.isfile(SONIC_ENV_TEMPLATE_FILE) and os.path.isfile(SONIC_VERSION_YML_FILE):
        clicommon.run_command(
            "{} -d -y {} -t {},{}".format(
                SONIC_CFGGEN_PATH,
                SONIC_VERSION_YML_FILE,
                SONIC_ENV_TEMPLATE_FILE,
                SONIC_ENV_FILE
            ),
            display_cmd=True
        )

def remove_router_interface_ip_address(config_db, interface_name, ipaddress_to_remove):
    table_name = get_interface_table_name(interface_name)
    keys = config_db.get_keys(table_name)

    for key in keys:
        if not isinstance(key, tuple) or len(key) != 2:
            continue

        iface, ipaddress_string = key
        if iface != interface_name:
            continue

        if ipaddress.ip_interface(ipaddress_string) == ipaddress_to_remove:
            config_db.set_entry(table_name, (interface_name, ipaddress_string), None)

def validate_ipv4_address(ctx, param, ip_addr):
    """Helper function to validate ipv4 address
    """
    try:
        ip_n = ipaddress.ip_network(ip_addr, False)
        if ip_n.version != 4:
            raise click.UsageError("{} is not a valid IPv4 address".format(ip_addr))
        return ip_addr
    except ValueError as e:
        raise click.UsageError(str(e))

def validate_gre_type(ctx, _, value):
    """A validator for validating input gre_type
    """
    if value is None:
        return None
    try:
        base = 10
        if value.lower().startswith('0x'):
            base = 16
        gre_type_value = int(value, base)
        if gre_type_value < GRE_TYPE_RANGE.min or gre_type_value > GRE_TYPE_RANGE.max:
            raise click.UsageError("{} is not a valid GRE type".format(value))
        return gre_type_value
    except ValueError:
        raise click.UsageError("{} is not a valid GRE type".format(value))
    
# Function to apply patch for a single ASIC.
def apply_patch_for_scope(scope_changes, results, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_path):
    scope, changes = scope_changes
    # Replace localhost to DEFAULT_NAMESPACE which is db definition of Host
    if scope.lower() == "localhost" or scope == "":
        scope = multi_asic.DEFAULT_NAMESPACE
        
    scope_for_log = scope if scope else "localhost"
    try:
        # Call apply_patch with the ASIC-specific changes and predefined parameters
        GenericUpdater(namespace=scope).apply_patch(jsonpatch.JsonPatch(changes), config_format, verbose, dry_run, ignore_non_yang_tables, ignore_path)
        results[scope_for_log] = {"success": True, "message": "Success"}
        log.log_notice(f"'apply-patch' executed successfully for {scope_for_log} by {changes}")
    except Exception as e:
        results[scope_for_log] = {"success": False, "message": str(e)}
        log.log_error(f"'apply-patch' executed failed for {scope_for_log} by {changes} due to {str(e)}")


# This is our main entrypoint - the main 'config' command
@click.group(cls=clicommon.AbbreviationGroup, context_settings=CONTEXT_SETTINGS)
@click.pass_context
def config(ctx):
    """SONiC command line - 'config' command"""
    #
    # Load asic_type for further use
    #
    global asic_type

    try:
        version_info = device_info.get_sonic_version_info()
        if version_info:
            asic_type = version_info['asic_type']
        else:
            asic_type = None
    except (KeyError, TypeError) as e:
        print("Caught an exception: " + str(e))
        raise click.Abort()

    if asic_type == 'cisco-8000':
        from sonic_platform.cli.cisco import cisco
        platform.add_command(cisco)

    # Load database config files
    load_db_config()

    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")

    ctx.obj = Db()


# Add groups from other modules
config.add_command(aaa.aaa)
config.add_command(aaa.tacacs)
config.add_command(aaa.radius)
config.add_command(chassis_modules.chassis)
config.add_command(console.console)
config.add_command(feature.feature)
config.add_command(flow_counters.flowcnt_route)
config.add_command(kdump.kdump)
config.add_command(kube.kubernetes)
config.add_command(muxcable.muxcable)
config.add_command(nat.nat)
config.add_command(vlan.vlan)
config.add_command(vxlan.vxlan)

#add mclag commands
config.add_command(mclag.mclag)
config.add_command(mclag.mclag_member)
config.add_command(mclag.mclag_unique_ip)

# syslog module
config.add_command(syslog.syslog)

@config.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Existing files will be overwritten, continue?')
@click.argument('filename', required=False)
def save(filename):
    """Export current config DB to a file on disk.\n
       <filename> : Names of configuration file(s) to save, separated by comma with no spaces in between
    """
    num_asic = multi_asic.get_num_asics()
    cfg_files = []

    num_cfg_file = 1
    if multi_asic.is_multi_asic():
        num_cfg_file += num_asic

    # If the user give the filename[s], extract the file names.
    if filename is not None:
        cfg_files = filename.split(',')

        if len(cfg_files) != num_cfg_file:
            click.echo("Input {} config file(s) separated by comma for multiple files ".format(num_cfg_file))
            return

    # In case of multi-asic mode we have additional config_db{NS}.json files for
    # various namespaces created per ASIC. {NS} is the namespace index.
    for inst in range(-1, num_cfg_file-1):
        #inst = -1, refers to the linux host where there is no namespace.
        if inst == -1:
            namespace = None
        else:
            namespace = "{}{}".format(NAMESPACE_PREFIX, inst)

        # Get the file from user input, else take the default file /etc/sonic/config_db{NS_id}.json
        if cfg_files:
            file = cfg_files[inst+1]
        else:
            if namespace is None:
                file = DEFAULT_CONFIG_DB_FILE
            else:
                file = "/etc/sonic/config_db{}.json".format(inst)

        if namespace is None:
            command = "{} -d --print-data > {}".format(SONIC_CFGGEN_PATH, file)
        else:
            command = "{} -n {} -d --print-data > {}".format(SONIC_CFGGEN_PATH, namespace, file)

        log.log_info("'save' executing...")
        clicommon.run_command(command, display_cmd=True)

        config_db = sort_dict(read_json_file(file))
        with open(file, 'w') as config_db_file:
            json.dump(config_db, config_db_file, indent=4)

@config.command()
@click.option('-y', '--yes', is_flag=True)
@click.argument('filename', required=False)
def load(filename, yes):
    """Import a previous saved config DB dump file.
       <filename> : Names of configuration file(s) to load, separated by comma with no spaces in between
    """
    if filename is None:
        message = 'Load config from the default config file(s) ?'
    else:
        message = 'Load config from the file(s) {} ?'.format(filename)

    if not yes:
        click.confirm(message, abort=True)

    num_asic = multi_asic.get_num_asics()
    cfg_files = []

    num_cfg_file = 1
    if multi_asic.is_multi_asic():
        num_cfg_file += num_asic

    # If the user give the filename[s], extract the file names.
    if filename is not None:
        cfg_files = filename.split(',')

        if len(cfg_files) != num_cfg_file:
            click.echo("Input {} config file(s) separated by comma for multiple files ".format(num_cfg_file))
            return

    # In case of multi-asic mode we have additional config_db{NS}.json files for
    # various namespaces created per ASIC. {NS} is the namespace index.
    for inst in range(-1, num_cfg_file-1):
        #inst = -1, refers to the linux host where there is no namespace.
        if inst == -1:
            namespace = None
        else:
            namespace = "{}{}".format(NAMESPACE_PREFIX, inst)

        # Get the file from user input, else take the default file /etc/sonic/config_db{NS_id}.json
        if cfg_files:
            file = cfg_files[inst+1]
        else:
            if namespace is None:
                file = DEFAULT_CONFIG_DB_FILE
            else:
                file = "/etc/sonic/config_db{}.json".format(inst)

        # if any of the config files in linux host OR namespace is not present, return
        if not os.path.exists(file):
            click.echo("The config_db file {} doesn't exist".format(file))
            return

        if namespace is None:
            command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, file)
        else:
            command = "{} -n {} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, namespace, file)

        log.log_info("'load' executing...")
        clicommon.run_command(command, display_cmd=True)

def print_dry_run_message(dry_run):
    if dry_run:
        click.secho("** DRY RUN EXECUTION **", fg="yellow", underline=True)

@config.command('apply-patch')
@click.argument('patch-file-path', type=str, required=True)
@click.option('-f', '--format', type=click.Choice([e.name for e in ConfigFormat]),
               default=ConfigFormat.CONFIGDB.name,
               help='format of config of the patch is either ConfigDb(ABNF) or SonicYang',
               show_default=True)
@click.option('-d', '--dry-run', is_flag=True, default=False, help='test out the command without affecting config state')
@click.option('-n', '--ignore-non-yang-tables', is_flag=True, default=False, help='ignore validation for tables without YANG models', hidden=True)
@click.option('-i', '--ignore-path', multiple=True, help='ignore validation for config specified by given path which is a JsonPointer', hidden=True)
@click.option('-v', '--verbose', is_flag=True, default=False, help='print additional details of what the operation is doing')
@click.pass_context
def apply_patch(ctx, patch_file_path, format, dry_run, ignore_non_yang_tables, ignore_path, verbose):
    """Apply given patch of updates to Config. A patch is a JsonPatch which follows rfc6902.
       This command can be used do partial updates to the config with minimum disruption to running processes.
       It allows addition as well as deletion of configs. The patch file represents a diff of ConfigDb(ABNF)
       format or SonicYang format.

       <patch-file-path>: Path to the patch file on the file-system."""
    try:
        print_dry_run_message(dry_run)

        with open(patch_file_path, 'r') as fh:
            text = fh.read()
            patch_as_json = json.loads(text)
            patch = jsonpatch.JsonPatch(patch_as_json)

        results = {}
        config_format = ConfigFormat[format.upper()]
        # Initialize a dictionary to hold changes categorized by scope
        changes_by_scope = {}

        # Iterate over each change in the JSON Patch
        for change in patch:
            scope, modified_path = extract_scope(change["path"])

            # Modify the 'path' in the change to remove the scope
            change["path"] = modified_path

            # Check if the scope is already in our dictionary, if not, initialize it
            if scope not in changes_by_scope:
                changes_by_scope[scope] = []

            # Add the modified change to the appropriate list based on scope
            changes_by_scope[scope].append(change)

        # Empty case to force validate YANG model.
        if not changes_by_scope:
            asic_list = [multi_asic.DEFAULT_NAMESPACE]
            asic_list.extend(multi_asic.get_namespace_list())
            for asic in asic_list:
                changes_by_scope[asic] = []

        # Apply changes for each scope
        for scope_changes in changes_by_scope.items():
            apply_patch_for_scope(scope_changes, results, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_path)

        # Check if any updates failed
        failures = [scope for scope, result in results.items() if not result['success']]

        if failures:
            failure_messages = '\n'.join([f"- {failed_scope}: {results[failed_scope]['message']}" for failed_scope in failures])
            raise Exception(f"Failed to apply patch on the following scopes:\n{failure_messages}")

        log.log_notice(f"Patch applied successfully for {patch}.")
        click.secho("Patch applied successfully.", fg="cyan", underline=True)
    except Exception as ex:
        click.secho("Failed to apply patch due to: {}".format(ex), fg="red", underline=True, err=True)
        ctx.fail(ex)

@config.command()
@click.argument('target-file-path', type=str, required=True)
@click.option('-f', '--format', type=click.Choice([e.name for e in ConfigFormat]),
               default=ConfigFormat.CONFIGDB.name,
               help='format of target config is either ConfigDb(ABNF) or SonicYang',
               show_default=True)
@click.option('-d', '--dry-run', is_flag=True, default=False, help='test out the command without affecting config state')
@click.option('-n', '--ignore-non-yang-tables', is_flag=True, default=False, help='ignore validation for tables without YANG models', hidden=True)
@click.option('-i', '--ignore-path', multiple=True, help='ignore validation for config specified by given path which is a JsonPointer', hidden=True)
@click.option('-v', '--verbose', is_flag=True, default=False, help='print additional details of what the operation is doing')
@click.pass_context
def replace(ctx, target_file_path, format, dry_run, ignore_non_yang_tables, ignore_path, verbose):
    """Replace the whole config with the specified config. The config is replaced with minimum disruption e.g.
       if ACL config is different between current and target config only ACL config is updated, and other config/services
       such as DHCP will not be affected.

       **WARNING** The target config file should be the whole config, not just the part intended to be updated.

       <target-file-path>: Path to the target file on the file-system."""
    try:
        print_dry_run_message(dry_run)

        with open(target_file_path, 'r') as fh:
            target_config_as_text = fh.read()
            target_config = json.loads(target_config_as_text)

        config_format = ConfigFormat[format.upper()]

        GenericUpdater().replace(target_config, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_path)

        click.secho("Config replaced successfully.", fg="cyan", underline=True)
    except Exception as ex:
        click.secho("Failed to replace config", fg="red", underline=True, err=True)
        ctx.fail(ex)

@config.command()
@click.argument('checkpoint-name', type=str, required=True)
@click.option('-d', '--dry-run', is_flag=True, default=False, help='test out the command without affecting config state')
@click.option('-n', '--ignore-non-yang-tables', is_flag=True, default=False, help='ignore validation for tables without YANG models', hidden=True)
@click.option('-i', '--ignore-path', multiple=True, help='ignore validation for config specified by given path which is a JsonPointer', hidden=True)
@click.option('-v', '--verbose', is_flag=True, default=False, help='print additional details of what the operation is doing')
@click.pass_context
def rollback(ctx, checkpoint_name, dry_run, ignore_non_yang_tables, ignore_path, verbose):
    """Rollback the whole config to the specified checkpoint. The config is rolled back with minimum disruption e.g.
       if ACL config is different between current and checkpoint config only ACL config is updated, and other config/services
       such as DHCP will not be affected.

       <checkpoint-name>: The checkpoint name, use `config list-checkpoints` command to see available checkpoints."""
    try:
        print_dry_run_message(dry_run)

        GenericUpdater().rollback(checkpoint_name, verbose, dry_run, ignore_non_yang_tables, ignore_path)

        click.secho("Config rolled back successfully.", fg="cyan", underline=True)
    except Exception as ex:
        click.secho("Failed to rollback config", fg="red", underline=True, err=True)
        ctx.fail(ex)

@config.command()
@click.argument('checkpoint-name', type=str, required=True)
@click.option('-v', '--verbose', is_flag=True, default=False, help='print additional details of what the operation is doing')
@click.pass_context
def checkpoint(ctx, checkpoint_name, verbose):
    """Take a checkpoint of the whole current config with the specified checkpoint name.

       <checkpoint-name>: The checkpoint name, use `config list-checkpoints` command to see available checkpoints."""
    try:
        GenericUpdater().checkpoint(checkpoint_name, verbose)

        click.secho("Checkpoint created successfully.", fg="cyan", underline=True)
    except Exception as ex:
        click.secho("Failed to create a config checkpoint", fg="red", underline=True, err=True)
        ctx.fail(ex)

@config.command('delete-checkpoint')
@click.argument('checkpoint-name', type=str, required=True)
@click.option('-v', '--verbose', is_flag=True, default=False, help='print additional details of what the operation is doing')
@click.pass_context
def delete_checkpoint(ctx, checkpoint_name, verbose):
    """Delete a checkpoint with the specified checkpoint name.

       <checkpoint-name>: The checkpoint name, use `config list-checkpoints` command to see available checkpoints."""
    try:
        GenericUpdater().delete_checkpoint(checkpoint_name, verbose)

        click.secho("Checkpoint deleted successfully.", fg="cyan", underline=True)
    except Exception as ex:
        click.secho("Failed to delete config checkpoint", fg="red", underline=True, err=True)
        ctx.fail(ex)

@config.command('list-checkpoints')
@click.option('-v', '--verbose', is_flag=True, default=False, help='print additional details of what the operation is doing')
@click.pass_context
def list_checkpoints(ctx, verbose):
    """List the config checkpoints available."""
    try:
        checkpoints_list = GenericUpdater().list_checkpoints(verbose)
        formatted_output = json.dumps(checkpoints_list, indent=4)
        click.echo(formatted_output)
    except Exception as ex:
        click.secho("Failed to list config checkpoints", fg="red", underline=True, err=True)
        ctx.fail(ex)

@config.command()
@click.option('-y', '--yes', is_flag=True)
@click.option('-l', '--load-sysinfo', is_flag=True, help='load system default information (mac, portmap etc) first.')
@click.option('-n', '--no_service_restart', default=False, is_flag=True, help='Do not restart docker services')
@click.option('-f', '--force', default=False, is_flag=True, help='Force config reload without system checks')
@click.option('-t', '--file_format', default='config_db',type=click.Choice(['config_yang', 'config_db']),show_default=True,help='specify the file format')
@click.argument('filename', required=False)
@clicommon.pass_db
def reload(db, filename, yes, load_sysinfo, no_service_restart, force, file_format):
    """Clear current configuration and import a previous saved config DB dump file.
       <filename> : Names of configuration file(s) to load, separated by comma with no spaces in between
    """
    CONFIG_RELOAD_NOT_READY = 1
    if not force and not no_service_restart:
        if _is_system_starting():
            click.echo("System is not up. Retry later or use -f to avoid system checks")
            sys.exit(CONFIG_RELOAD_NOT_READY)

        if not _swss_ready():
            click.echo("SwSS container is not ready. Retry later or use -f to avoid system checks")
            sys.exit(CONFIG_RELOAD_NOT_READY)

    if filename is None:
        message = 'Clear current config and reload config in {} format from the default config file(s) ?'.format(file_format)
    else:
        message = 'Clear current config and reload config in {} from the file(s) {} ?'.format(file_format, filename)

    if not yes:
        click.confirm(message, abort=True)

    argv_str = ' '.join(['config', *sys.argv[1:]])
    log.log_notice(f"'reload' executing with command: {argv_str}")

    num_asic = multi_asic.get_num_asics()
    cfg_files = []

    num_cfg_file = 1
    # single config_yang file for the multi asic device
    if multi_asic.is_multi_asic() and file_format == 'config_db':
        num_cfg_file += num_asic

    # If the user give the filename[s], extract the file names.
    if filename is not None:
        cfg_files = filename.split(',')

        if len(cfg_files) != num_cfg_file:
            click.echo("Input {} config file(s) separated by comma for multiple files ".format(num_cfg_file))
            return

    #Stop services before config push
    if not no_service_restart:
        log.log_notice("'reload' stopping services...")
        _stop_services()

    # In Single ASIC platforms we have single DB service. In multi-ASIC platforms we have a global DB
    # service running in the host + DB services running in each ASIC namespace created per ASIC.
    # In the below logic, we get all namespaces in this platform and add an empty namespace ''
    # denoting the current namespace which we are in ( the linux host )
    for inst in range(-1, num_cfg_file-1):
        # Get the namespace name, for linux host it is None
        if inst == -1:
            namespace = None
        else:
            namespace = "{}{}".format(NAMESPACE_PREFIX, inst)

        # Get the file from user input, else take the default file /etc/sonic/config_db{NS_id}.json
        if cfg_files:
            file = cfg_files[inst+1]
        else:
            if file_format == 'config_db':
                if namespace is None:
                    file = DEFAULT_CONFIG_DB_FILE
                else:
                    file = "/etc/sonic/config_db{}.json".format(inst)
            else:
                file = DEFAULT_CONFIG_YANG_FILE


        # Check the file exists before proceeding.
        if not os.path.exists(file):
            click.echo("The config file {} doesn't exist".format(file))
            continue

        if file_format == 'config_db':
            file_input = read_json_file(file)

            platform = file_input.get("DEVICE_METADATA", {}).\
                get("localhost", {}).get("platform")
            mac = file_input.get("DEVICE_METADATA", {}).\
                get("localhost", {}).get("mac")

            if not platform or not mac:
                log.log_warning("Input file does't have platform or mac. platform: {}, mac: {}"
                    .format(None if platform is None else platform, None if mac is None else mac))
                load_sysinfo = True

        if load_sysinfo:
            try:
                command = [SONIC_CFGGEN_PATH, "-j", file, '-v', "DEVICE_METADATA.localhost.hwsku"]
                proc = subprocess.Popen(command, text=True, stdout=subprocess.PIPE)
                output, err = proc.communicate()

            except FileNotFoundError as e:
                click.echo("{}".format(str(e)), err=True)
                raise click.Abort()
            except Exception as e:
                click.echo("{}\n{}".format(type(e), str(e)), err=True)
                raise click.Abort()

            if not output:
                click.secho("Could not get the HWSKU from config file,  Exiting!!!", fg='magenta')
                sys.exit(1)

            cfg_hwsku = output.strip()

        if namespace is None:
            config_db = ConfigDBConnector()
        else:
            config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)

        config_db.connect()
        client = config_db.get_redis_client(config_db.CONFIG_DB)
        client.flushdb()

        if load_sysinfo:
            if namespace is None:
                command = "{} -H -k {} --write-to-db".format(SONIC_CFGGEN_PATH, cfg_hwsku)
            else:
                command = "{} -H -k {} -n {} --write-to-db".format(SONIC_CFGGEN_PATH, cfg_hwsku, namespace)
            clicommon.run_command(command, display_cmd=True)

        # For the database service running in linux host we use the file user gives as input
        # or by default DEFAULT_CONFIG_DB_FILE. In the case of database service running in namespace,
        # the default config_db<namespaceID>.json format is used.


        config_gen_opts = ""

        if os.path.isfile(INIT_CFG_FILE):
            config_gen_opts += " -j {} ".format(INIT_CFG_FILE)

        if file_format == 'config_db':
            config_gen_opts += ' -j {} '.format(file)
        else:
            config_gen_opts += ' -Y {} '.format(file)

        if namespace is not None:
            config_gen_opts += " -n {} ".format(namespace)


        command = "{sonic_cfggen} {options} --write-to-db".format(
            sonic_cfggen=SONIC_CFGGEN_PATH,
            options=config_gen_opts)

        clicommon.run_command(command, display_cmd=True)
        client.set(config_db.INIT_INDICATOR, 1)

        # Migrate DB contents to latest version
        db_migrator='/usr/local/bin/db_migrator.py'
        if os.path.isfile(db_migrator) and os.access(db_migrator, os.X_OK):
            if namespace is None:
                command = "{} -o migrate".format(db_migrator)
            else:
                command = "{} -o migrate -n {}".format(db_migrator, namespace)
            clicommon.run_command(command, display_cmd=True)

    # Re-generate the environment variable in case config_db.json was edited
    update_sonic_environment()

    # We first run "systemctl reset-failed" to remove the "failed"
    # status from all services before we attempt to restart them
    if not no_service_restart:
        _reset_failed_services()
        log.log_notice("'reload' restarting services...")
        _restart_services()

@config.command("load_mgmt_config")
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload mgmt config?')
@click.argument('filename', default='/etc/sonic/device_desc.xml', type=click.Path(exists=True))
def load_mgmt_config(filename):
    """Reconfigure hostname and mgmt interface based on device description file."""
    log.log_info("'load_mgmt_config' executing...")
    command = "{} -M {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    clicommon.run_command(command, display_cmd=True)
    #FIXME: After config DB daemon for hostname and mgmt interface is implemented, we'll no longer need to do manual configuration here
    config_data = parse_device_desc_xml(filename)
    hostname = config_data['DEVICE_METADATA']['localhost']['hostname']
    _change_hostname(hostname)
    for key in list(config_data['MGMT_INTERFACE'].keys()):
        # key: (eth0, ipprefix)
        # value: { gwaddr: ip }
        mgmt_conf = netaddr.IPNetwork(key[1])
        gw_addr = config_data['MGMT_INTERFACE'][key]['gwaddr']
        if mgmt_conf.version == 4:
            command = "ifconfig eth0 {} netmask {}".format(str(mgmt_conf.ip), str(mgmt_conf.netmask))
            clicommon.run_command(command, display_cmd=True)
        else:
            command = "ifconfig eth0 add {}".format(str(mgmt_conf))
            # Ignore error for IPv6 configuration command due to it not allows config the same IP twice
            clicommon.run_command(command, display_cmd=True, ignore_error=True)
        command = "ip{} route add default via {} dev eth0 table default".format(" -6" if mgmt_conf.version == 6 else "", gw_addr)
        clicommon.run_command(command, display_cmd=True, ignore_error=True)
        command = "ip{} rule add from {} table default".format(" -6" if mgmt_conf.version == 6 else "", str(mgmt_conf.ip))
        clicommon.run_command(command, display_cmd=True, ignore_error=True)
    if len(config_data['MGMT_INTERFACE'].keys()) > 0:
        command = "[ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid"
        clicommon.run_command(command, display_cmd=True, ignore_error=True)
    click.echo("Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.")

@config.command("load_minigraph")
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload config from minigraph?')
@click.option('-n', '--no_service_restart', default=False, is_flag=True, help='Do not restart docker services')
@click.option('-t', '--traffic_shift_away', default=False, is_flag=True, help='Keep device in maintenance with TSA')
@click.option('-o', '--override_config', default=False, is_flag=True, help='Enable config override. Proceed with default path.')
@click.option('-p', '--golden_config_path', help='Provide golden config path to override. Use with --override_config')
@clicommon.pass_db
def load_minigraph(db, no_service_restart, traffic_shift_away, override_config, golden_config_path):
    """Reconfigure based on minigraph."""
    argv_str = ' '.join(['config', *sys.argv[1:]])
    log.log_notice(f"'load_minigraph' executing with command: {argv_str}")

    #Stop services before config push
    if not no_service_restart:
        log.log_notice("'load_minigraph' stopping services...")
        _stop_services()

    # For Single Asic platform the namespace list has the empty string
    # for mulit Asic platform the empty string to generate the config
    # for host
    namespace_list = [DEFAULT_NAMESPACE]
    num_npus = multi_asic.get_num_asics()
    if num_npus > 1:
        namespace_list += multi_asic.get_namespaces_from_linux()

    for namespace in namespace_list:
        if namespace is DEFAULT_NAMESPACE:
            config_db = ConfigDBConnector()
            cfggen_namespace_option = " "
            ns_cmd_prefix = ""
        else:
            config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
            cfggen_namespace_option = " -n {}".format(namespace)
            ns_cmd_prefix = "sudo ip netns exec {} ".format(namespace)
        config_db.connect()
        client = config_db.get_redis_client(config_db.CONFIG_DB)
        client.flushdb()
        if os.path.isfile('/etc/sonic/init_cfg.json'):
            command = "{} -H -m -j /etc/sonic/init_cfg.json {} --write-to-db".format(SONIC_CFGGEN_PATH, cfggen_namespace_option)
        else:
            command = "{} -H -m --write-to-db {}".format(SONIC_CFGGEN_PATH, cfggen_namespace_option)
        clicommon.run_command(command, display_cmd=True)
        client.set(config_db.INIT_INDICATOR, 1)

    # Update SONiC environmnet file
    update_sonic_environment()

    if os.path.isfile('/etc/sonic/acl.json'):
        clicommon.run_command("acl-loader update full /etc/sonic/acl.json", display_cmd=True)

    # Load port_config.json
    try:
        load_port_config(db.cfgdb, '/etc/sonic/port_config.json')
    except Exception as e:
        click.secho("Failed to load port_config.json, Error: {}".format(str(e)), fg='magenta')

    # generate QoS and Buffer configs
    clicommon.run_command("config qos reload --no-dynamic-buffer --no-delay", display_cmd=True)

    # get the device type
    device_type = _get_device_type()
    if device_type != 'MgmtToRRouter' and device_type != 'MgmtTsToR' and device_type != 'BmcMgmtToRRouter' and device_type != 'EPMS':
        clicommon.run_command("pfcwd start_default", display_cmd=True)

    # Write latest db version string into db
    db_migrator='/usr/local/bin/db_migrator.py'
    if os.path.isfile(db_migrator) and os.access(db_migrator, os.X_OK):
        for namespace in namespace_list:
            if namespace is DEFAULT_NAMESPACE:
                cfggen_namespace_option = " "
            else:
                cfggen_namespace_option = " -n {}".format(namespace)
            clicommon.run_command(db_migrator + ' -o set_version' + cfggen_namespace_option)

    # Keep device isolated with TSA
    if traffic_shift_away:
        clicommon.run_command("TSA", display_cmd=True)
        if override_config:
            log.log_warning("Golden configuration may override System Maintenance state. Please execute TSC to check the current System mode")
            click.secho("[WARNING] Golden configuration may override Traffic-shift-away state. Please execute TSC to check the current System mode")

    # Load golden_config_db.json
    if override_config:
        if golden_config_path is None:
            golden_config_path = DEFAULT_GOLDEN_CONFIG_DB_FILE
        if not os.path.isfile(golden_config_path):
            click.secho("Cannot find '{}'!".format(golden_config_path),
                        fg='magenta')
            raise click.Abort()
        override_config_by(golden_config_path)

    # Invoke platform script if available before starting the services
    platform_path, _ = device_info.get_paths_to_platform_and_hwsku_dirs()
    platform_mg_plugin = platform_path + '/plugins/platform_mg_post_check'
    if os.path.isfile(platform_mg_plugin):
        click.echo("Running Platform plugin ............!")
        proc = subprocess.Popen([platform_mg_plugin], text=True, stdout=subprocess.PIPE)
        proc.communicate()
        if proc.returncode != 0:
            click.echo("Platform plugin failed! retruncode {}".format(proc.returncode))
            raise click.Abort()

    # We first run "systemctl reset-failed" to remove the "failed"
    # status from all services before we attempt to restart them
    if not no_service_restart:
        _reset_failed_services()
        #FIXME: After config DB daemon is implemented, we'll no longer need to restart every service.
        log.log_notice("'load_minigraph' restarting services...")
        _restart_services()
    click.echo("Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.")

def load_port_config(config_db, port_config_path):
    if not os.path.isfile(port_config_path):
        return

    try:
        # Load port_config.json
        port_config_input = read_json_file(port_config_path)
    except Exception:
        raise Exception("Bad format: json file broken")

    # Validate if the input is an array
    if not isinstance(port_config_input, list):
        raise Exception("Bad format: port_config is not an array")

    if len(port_config_input) == 0 or 'PORT' not in port_config_input[0]:
        raise Exception("Bad format: PORT table not exists")

    port_config = port_config_input[0]['PORT']

    # Ensure all ports are exist
    port_table = {}
    for port_name in port_config.keys():
        port_entry = config_db.get_entry('PORT', port_name)
        if not port_entry:
            raise Exception("Port {} is not defined in current device".format(port_name))
        port_table[port_name] = port_entry

    # Update port state
    for port_name in port_config.keys():
        if 'admin_status' not in port_config[port_name]:
            continue
        if 'admin_status' in port_table[port_name]:
            if port_table[port_name]['admin_status'] == port_config[port_name]['admin_status']:
                continue
            clicommon.run_command('config interface {} {}'.format(
                'startup' if port_config[port_name]['admin_status'] == 'up' else 'shutdown',
                port_name), display_cmd=True)
    return


def override_config_by(golden_config_path):
    # Override configDB with golden config
    clicommon.run_command('config override-config-table {}'.format(
        golden_config_path), display_cmd=True)
    return


#
# 'override-config-table' command ('config override-config-table ...')
#
@config.command('override-config-table')
@click.argument('input-config-db', required=True)
@click.option(
    '--dry-run', is_flag=True, default=False,
    help='test out the command without affecting config state'
)
@clicommon.pass_db
def override_config_table(db, input_config_db, dry_run):
    """Override current configDB with input config."""

    try:
        # Load golden config json
        config_input = read_json_file(input_config_db)
    except Exception as e:
        click.secho("Bad format: json file broken. {}".format(str(e)),
                    fg='magenta')
        sys.exit(1)

    # Validate if the input is dict
    if not isinstance(config_input, dict):
        click.secho("Bad format: input_config_db is not a dict",
                    fg='magenta')
        sys.exit(1)

    config_db = db.cfgdb

    # Read config from configDB
    current_config = config_db.get_config()
    # Serialize to the same format as json input
    sonic_cfggen.FormatConverter.to_serialized(current_config)

    updated_config = update_config(current_config, config_input)

    yang_enabled = device_info.is_yang_config_validation_enabled(config_db)
    if yang_enabled:
        # The ConfigMgmt will load YANG and running
        # config during initialization.
        try:
            cm = ConfigMgmt()
            cm.validateConfigData()
        except Exception as ex:
            click.secho("Failed to validate running config. Error: {}".format(ex), fg="magenta")
            sys.exit(1)

        # Validate input config
        validate_config_by_cm(cm, config_input, "config_input")
        # Validate updated whole config
        validate_config_by_cm(cm, updated_config, "updated_config")

    if dry_run:
        print(json.dumps(updated_config, sort_keys=True,
                         indent=4, cls=minigraph_encoder))
    else:
        override_config_db(config_db, config_input)


def validate_config_by_cm(cm, config_json, jname):
    tmp_config_json = copy.deepcopy(config_json)
    try:
        cm.loadData(tmp_config_json)
        cm.validateConfigData()
    except Exception as ex:
        click.secho("Failed to validate {}. Error: {}".format(jname, ex), fg="magenta")
        sys.exit(1)


def update_config(current_config, config_input):
    updated_config = copy.deepcopy(current_config)
    # Override current config with golden config
    for table in config_input:
        updated_config[table] = config_input[table]
    return updated_config


def override_config_db(config_db, config_input):
    # Deserialized golden config to DB recognized format
    sonic_cfggen.FormatConverter.to_deserialized(config_input)
    # Delete table from DB then mod_config to apply golden config
    click.echo("Removing configDB overriden table first ...")
    for table in config_input:
        config_db.delete_table(table)
    click.echo("Overriding input config to configDB ...")
    data = sonic_cfggen.FormatConverter.output_to_db(config_input)
    config_db.mod_config(data)
    click.echo("Overriding completed. No service is restarted.")


#
# 'hostname' command
#
@config.command('hostname')
@click.argument('new_hostname', metavar='<new_hostname>', required=True)
def hostname(new_hostname):
    """Change device hostname without impacting the traffic."""
    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.mod_entry(swsscommon.CFG_DEVICE_METADATA_TABLE_NAME, 'localhost',
                            {'hostname': new_hostname})
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Failed to write new hostname to ConfigDB. Error: {}".format(e))


    click.echo('Please note loaded setting will be lost after system reboot. To'
               ' preserve setting, run `config save`.')

#
# 'synchronous_mode' command ('config synchronous_mode ...')
#
@config.command('synchronous_mode')
@click.argument('sync_mode', metavar='<enable|disable>', required=True)
def synchronous_mode(sync_mode):
    """ Enable or disable synchronous mode between orchagent and syncd \n
        swss restart required to apply the configuration \n
        Options to restart swss and apply the configuration: \n
            1. config save -y \n
               config reload -y \n
            2. systemctl restart swss
    """
    if ADHOC_VALIDATION:
        if sync_mode != 'enable' and sync_mode != 'disable':
            raise click.BadParameter("Error: Invalid argument %s, expect either enable or disable" % sync_mode)

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.mod_entry('DEVICE_METADATA' , 'localhost', {"synchronous_mode" : sync_mode})
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Error: Invalid argument %s, expect either enable or disable" % sync_mode)

    click.echo("""Wrote %s synchronous mode into CONFIG_DB, swss restart required to apply the configuration: \n
    Option 1. config save -y \n
              config reload -y \n
    Option 2. systemctl restart swss""" % sync_mode)

#
# 'suppress-fib-pending' command ('config suppress-fib-pending ...')
#
@config.command('suppress-fib-pending')
@click.argument('state', metavar='<enabled|disabled>', required=True, type=click.Choice(['enabled', 'disabled']))
@clicommon.pass_db
def suppress_pending_fib(db, state):
    ''' Enable or disable pending FIB suppression. Once enabled, BGP will not advertise routes that are not yet installed in the hardware '''

    config_db = db.cfgdb
    config_db.mod_entry('DEVICE_METADATA' , 'localhost', {"suppress-fib-pending" : state})

#
# 'yang_config_validation' command ('config yang_config_validation ...')
#
@config.command('yang_config_validation')
@click.argument('yang_config_validation', metavar='<enable|disable>', required=True)
def yang_config_validation(yang_config_validation):
    if ADHOC_VALIDATION:
        if yang_config_validation != 'enable' and yang_config_validation != 'disable':
            raise click.BadParameter("Error: Invalid argument %s, expect either enable or disable" % yang_config_validation)

    config_db = ValidatedConfigDBConnector(ConfigDBConnector())
    config_db.connect()
    try:
        config_db.mod_entry('DEVICE_METADATA', 'localhost', {"yang_config_validation": yang_config_validation})
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Error: Invalid argument %s, expect either enable or disable" % yang_config_validation)

    click.echo("""Wrote %s yang config validation into CONFIG_DB""" % yang_config_validation)

#
# 'portchannel' group ('config portchannel ...')
#
@config.group(cls=clicommon.AbbreviationGroup)
# TODO add "hidden=True if this is a single ASIC platform, once we have click 7.0 in all branches.
@click.option('-n', '--namespace', help='Namespace name',
             required=True if multi_asic.is_multi_asic() else False, type=click.Choice(multi_asic.get_namespace_list()))
@click.pass_context
@clicommon.pass_db
def portchannel(db, ctx, namespace):
    # Set namespace to default_namespace if it is None.
    if namespace is None:
        namespace = DEFAULT_NAMESPACE

    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=str(namespace))
    config_db.connect()
    ctx.obj = {'db': config_db, 'namespace': str(namespace), 'db_wrap': db}

@portchannel.command('add')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.option('--min-links', default=1, type=click.IntRange(1,1024))
@click.option('--fallback', default='false')
@click.option('--fast-rate', default='false',
              type=click.Choice(['true', 'false'],
                                case_sensitive=False))
@click.pass_context
def add_portchannel(ctx, portchannel_name, min_links, fallback, fast_rate):
    """Add port channel"""

    fvs = {
        'admin_status': 'up',
        'mtu': '9100',
        'lacp_key': 'auto',
        'fast_rate': fast_rate.lower(),
    }

    if min_links != 0:
        fvs['min_links'] = str(min_links)
    if fallback != 'false':
        fvs['fallback'] = 'true'

    db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if is_portchannel_name_valid(portchannel_name) != True:
            ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'"
                    .format(portchannel_name, CFG_PORTCHANNEL_PREFIX, CFG_PORTCHANNEL_NO))
        if is_portchannel_present_in_db(db, portchannel_name):
            ctx.fail("{} already exists!".format(portchannel_name)) # TODO: MISSING CONSTRAINT IN YANG MODEL

    try:
        db.set_entry('PORTCHANNEL', portchannel_name, fvs)
    except ValueError:
        ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'".format(portchannel_name, CFG_PORTCHANNEL_PREFIX, CFG_PORTCHANNEL_NO))

@portchannel.command('del')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.pass_context
def remove_portchannel(ctx, portchannel_name):
    """Remove port channel"""

    db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if is_portchannel_name_valid(portchannel_name) != True:
            ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'"
                    .format(portchannel_name, CFG_PORTCHANNEL_PREFIX, CFG_PORTCHANNEL_NO))

        # Don't proceed if the port channel does not exist
        if is_portchannel_present_in_db(db, portchannel_name) is False:
            ctx.fail("{} is not present.".format(portchannel_name))

        # Dont let to remove port channel if vlan membership exists
        for k,v in db.get_table('VLAN_MEMBER'): # TODO: MISSING CONSTRAINT IN YANG MODEL
            if v == portchannel_name:
                ctx.fail("{} has vlan {} configured, remove vlan membership to proceed".format(portchannel_name, str(k)))

        if len([(k, v) for k, v in db.get_table('PORTCHANNEL_MEMBER') if k == portchannel_name]) != 0: # TODO: MISSING CONSTRAINT IN YANG MODEL
            ctx.fail("Error: Portchannel {} contains members. Remove members before deleting Portchannel!".format(portchannel_name))

    try:
        db.set_entry('PORTCHANNEL', portchannel_name, None)
    except JsonPatchConflict:
        ctx.fail("{} is not present.".format(portchannel_name))

@portchannel.group(cls=clicommon.AbbreviationGroup, name='member')
@click.pass_context
def portchannel_member(ctx):
    pass

@portchannel_member.command('add')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.argument('port_name', metavar='<port_name>', required=True)
@click.pass_context
def add_portchannel_member(ctx, portchannel_name, port_name):
    """Add member to port channel"""
    db = ValidatedConfigDBConnector(ctx.obj['db'])

    if ADHOC_VALIDATION:
        if clicommon.is_port_mirror_dst_port(db, port_name):
            ctx.fail("{} is configured as mirror destination port".format(port_name)) # TODO: MISSING CONSTRAINT IN YANG MODEL

        # Check if the member interface given by user is valid in the namespace.
        if port_name.startswith("Ethernet") is False or interface_name_is_valid(db, port_name) is False:
            ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

        # Dont proceed if the port channel name is not valid
        if is_portchannel_name_valid(portchannel_name) is False:
            ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'"
                     .format(portchannel_name, CFG_PORTCHANNEL_PREFIX, CFG_PORTCHANNEL_NO))

        # Dont proceed if the port channel does not exist
        if is_portchannel_present_in_db(db, portchannel_name) is False:
            ctx.fail("{} is not present.".format(portchannel_name))

        # Don't allow a port to be member of port channel if it is configured with an IP address
        for key,value in db.get_table('INTERFACE').items():
            if type(key) == tuple:
                continue
            if key == port_name:
                ctx.fail(" {} has ip address configured".format(port_name))  # TODO: MISSING CONSTRAINT IN YANG MODEL
                return

        for key in db.get_keys('VLAN_SUB_INTERFACE'):
            if type(key) == tuple:
                continue
            intf = key.split(VLAN_SUB_INTERFACE_SEPARATOR)[0]
            parent_intf = get_intf_longname(intf)
            if parent_intf == port_name:
                ctx.fail(" {} has subinterfaces configured".format(port_name))  # TODO: MISSING CONSTRAINT IN YANG MODEL

        # Dont allow a port to be member of port channel if it is configured as a VLAN member
        for k,v in db.get_table('VLAN_MEMBER'):
            if v == port_name:
                ctx.fail("%s Interface configured as VLAN_MEMBER under vlan : %s" %(port_name,str(k)))   # TODO: MISSING CONSTRAINT IN YANG MODEL
                return

        # Dont allow a port to be member of port channel if it is already member of a port channel
        for k,v in db.get_table('PORTCHANNEL_MEMBER'):
            if v == port_name:
                ctx.fail("{} Interface is already member of {} ".format(v,k))    # TODO: MISSING CONSTRAINT IN YANG MODEL

        # Dont allow a port to be member of port channel if its speed does not match with existing members
        for k,v in db.get_table('PORTCHANNEL_MEMBER'):
            if k == portchannel_name:
                member_port_entry = db.get_entry('PORT', v)
                port_entry = db.get_entry('PORT', port_name)

                if member_port_entry is not None and port_entry is not None:
                    member_port_speed = member_port_entry.get(PORT_SPEED)

                    port_speed = port_entry.get(PORT_SPEED) # TODO: MISSING CONSTRAINT IN YANG MODEL
                    if member_port_speed != port_speed:
                        ctx.fail("Port speed of {} is different than the other members of the portchannel {}"
                                 .format(port_name, portchannel_name))

        # Dont allow a port to be member of port channel if its MTU does not match with portchannel
        portchannel_entry =  db.get_entry('PORTCHANNEL', portchannel_name)
        if portchannel_entry and portchannel_entry.get(PORT_MTU) is not None :
            port_entry = db.get_entry('PORT', port_name)

            if port_entry and port_entry.get(PORT_MTU) is not None:
                port_mtu = port_entry.get(PORT_MTU)

                portchannel_mtu = portchannel_entry.get(PORT_MTU) # TODO: MISSING CONSTRAINT IN YANG MODEL
                if portchannel_mtu != port_mtu:
                    ctx.fail("Port MTU of {} is different than the {} MTU size"
                             .format(port_name, portchannel_name))

        # Dont allow a port to be member of port channel if its TPID is not at default 0x8100
        # If TPID is supported at LAG level, when member is added, the LAG's TPID is applied to the
        # new member by SAI.
        port_entry = db.get_entry('PORT', port_name)
        if port_entry and port_entry.get(PORT_TPID) is not None:
            port_tpid = port_entry.get(PORT_TPID) # TODO: MISSING CONSTRAINT IN YANG MODEL
            if port_tpid != DEFAULT_TPID:
                ctx.fail("Port TPID of {}: {} is not at default 0x8100".format(port_name, port_tpid))

        # Don't allow a port to be a member of portchannel if already has ACL bindings
        try:
            acl_bindings = get_port_acl_binding(ctx.obj['db_wrap'], port_name, ctx.obj['namespace']) # TODO: MISSING CONSTRAINT IN YANG MODEL
            if acl_bindings:
                ctx.fail("Port {} is already bound to following ACL_TABLES: {}".format(port_name, acl_bindings))
        except Exception as e:
            ctx.fail(str(e))

        # Don't allow a port to be a member of portchannel if already has PBH bindings
        try:
            pbh_bindings = get_port_pbh_binding(ctx.obj['db_wrap'], port_name, DEFAULT_NAMESPACE) # TODO: MISSING CONSTRAINT IN YANG MODEL
            if pbh_bindings:
                ctx.fail("Port {} is already bound to following PBH_TABLES: {}".format(port_name, pbh_bindings))
        except Exception as e:
            ctx.fail(str(e))

    try:
        db.set_entry('PORTCHANNEL_MEMBER', (portchannel_name, port_name),
                {'NULL': 'NULL'})
    except ValueError:
        ctx.fail("Portchannel or interface name is invalid or nonexistent")

@portchannel_member.command('del')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.argument('port_name', metavar='<port_name>', required=True)
@click.pass_context
def del_portchannel_member(ctx, portchannel_name, port_name):
    """Remove member from portchannel"""
    # Dont proceed if the port channel name is not valid
    if is_portchannel_name_valid(portchannel_name) is False:
        ctx.fail("{} is invalid!, name should have prefix '{}' and suffix '{}'"
                 .format(portchannel_name, CFG_PORTCHANNEL_PREFIX, CFG_PORTCHANNEL_NO))

    db = ValidatedConfigDBConnector(ctx.obj['db'])

    if ADHOC_VALIDATION:
        # Check if the member interface given by user is valid in the namespace.
        if interface_name_is_valid(db, port_name) is False:
            ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

        # Dont proceed if the port channel does not exist
        if is_portchannel_present_in_db(db, portchannel_name) is False:
            ctx.fail("{} is not present.".format(portchannel_name))

        # Dont proceed if the the port is not an existing member of the port channel
        if not is_port_member_of_this_portchannel(db, port_name, portchannel_name):
            ctx.fail("{} is not a member of portchannel {}".format(port_name, portchannel_name))

    try:
        db.set_entry('PORTCHANNEL_MEMBER', portchannel_name + '|' + port_name, None)
    except JsonPatchConflict:
        ctx.fail("Invalid or nonexistent portchannel or interface. Please ensure existence of portchannel member.")


#
# 'mirror_session' group ('config mirror_session ...')
#
@config.group(cls=clicommon.AbbreviationGroup, name='mirror_session')
def mirror_session():
    pass

#
# 'add' subgroup ('config mirror_session add ...')
#

@mirror_session.command('add')
@click.argument('session_name', metavar='<session_name>', required=True)
@click.argument('src_ip', metavar='<src_ip>', callback=validate_ipv4_address, required=True)
@click.argument('dst_ip', metavar='<dst_ip>', callback=validate_ipv4_address, required=True)
@click.argument('dscp', metavar='<dscp>', type=DSCP_RANGE, required=True)
@click.argument('ttl', metavar='<ttl>', type=TTL_RANGE, required=True)
@click.argument('gre_type', metavar='[gre_type]', callback=validate_gre_type, required=False)
@click.argument('queue', metavar='[queue]', type=QUEUE_RANGE, required=False)
@click.option('--policer')
def add(session_name, src_ip, dst_ip, dscp, ttl, gre_type, queue, policer):
    """ Add ERSPAN mirror session.(Legacy support) """
    add_erspan(session_name, src_ip, dst_ip, dscp, ttl, gre_type, queue, policer)

@mirror_session.group(cls=clicommon.AbbreviationGroup, name='erspan')
@click.pass_context
def erspan(ctx):
    """ ERSPAN mirror_session """
    pass


#
# 'add' subcommand
#

@erspan.command('add')
@click.argument('session_name', metavar='<session_name>', required=True)
@click.argument('src_ip', metavar='<src_ip>', callback=validate_ipv4_address, required=True)
@click.argument('dst_ip', metavar='<dst_ip>', callback=validate_ipv4_address,required=True)
@click.argument('dscp', metavar='<dscp>', type=DSCP_RANGE, required=True)
@click.argument('ttl', metavar='<ttl>', type=TTL_RANGE, required=True)
@click.argument('gre_type', metavar='[gre_type]', callback=validate_gre_type, required=False)
@click.argument('queue', metavar='[queue]', type=QUEUE_RANGE, required=False)
@click.argument('src_port', metavar='[src_port]', required=False)
@click.argument('direction', metavar='[direction]', required=False)
@click.option('--policer')
def add(session_name, src_ip, dst_ip, dscp, ttl, gre_type, queue, policer, src_port, direction):
    """ Add ERSPAN mirror session """
    add_erspan(session_name, src_ip, dst_ip, dscp, ttl, gre_type, queue, policer, src_port, direction)

def gather_session_info(session_info, policer, queue, src_port, direction):
    if policer:
        session_info['policer'] = policer

    if queue is not None:
        session_info['queue'] = queue

    if src_port:
        if clicommon.get_interface_naming_mode() == "alias":
            src_port_list = []
            for port in src_port.split(","):
                src_port_list.append(interface_alias_to_name(None, port))
            src_port=",".join(src_port_list)

        session_info['src_port'] = src_port
        if not direction:
            direction = "both"
        session_info['direction'] = direction.upper()

    return session_info

def add_erspan(session_name, src_ip, dst_ip, dscp, ttl, gre_type, queue, policer, src_port=None, direction=None):
    session_info = {
            "type" : "ERSPAN",
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "dscp": dscp,
            "ttl": ttl
            }

    if gre_type is not None:
        session_info['gre_type'] = gre_type

    session_info = gather_session_info(session_info, policer, queue, src_port, direction)
    ctx = click.get_current_context()

    """
    For multi-npu platforms we need to program all front asic namespaces
    """
    namespaces = multi_asic.get_all_namespaces()
    if not namespaces['front_ns']:
        config_db = ValidatedConfigDBConnector(ConfigDBConnector())
        config_db.connect()
        if ADHOC_VALIDATION:
            if validate_mirror_session_config(config_db, session_name, None, src_port, direction) is False:
                return
        try:
            config_db.set_entry("MIRROR_SESSION", session_name, session_info)
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    else:
        per_npu_configdb = {}
        for front_asic_namespaces in namespaces['front_ns']:
            per_npu_configdb[front_asic_namespaces] = ValidatedConfigDBConnector(ConfigDBConnector(use_unix_socket_path=True, namespace=front_asic_namespaces))
            per_npu_configdb[front_asic_namespaces].connect()
            if ADHOC_VALIDATION:
                if validate_mirror_session_config(per_npu_configdb[front_asic_namespaces], session_name, None, src_port, direction) is False:
                    return
            try:
                per_npu_configdb[front_asic_namespaces].set_entry("MIRROR_SESSION", session_name, session_info)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@mirror_session.group(cls=clicommon.AbbreviationGroup, name='span')
@click.pass_context
def span(ctx):
    """ SPAN mirror session """
    pass

@span.command('add')
@click.argument('session_name', metavar='<session_name>', required=True)
@click.argument('dst_port', metavar='<dst_port>', required=True)
@click.argument('src_port', metavar='[src_port]', required=False)
@click.argument('direction', metavar='[direction]', required=False)
@click.argument('queue', metavar='[queue]', type=QUEUE_RANGE, required=False)
@click.option('--policer')
def add(session_name, dst_port, src_port, direction, queue, policer):
    """ Add SPAN mirror session """
    add_span(session_name, dst_port, src_port, direction, queue, policer)

def add_span(session_name, dst_port, src_port, direction, queue, policer):
    if clicommon.get_interface_naming_mode() == "alias":
        dst_port = interface_alias_to_name(None, dst_port)
        if dst_port is None:
            click.echo("Error: Destination Interface {} is invalid".format(dst_port))
            return False

    session_info = {
            "type" : "SPAN",
            "dst_port": dst_port,
            }

    session_info = gather_session_info(session_info, policer, queue, src_port, direction)
    ctx = click.get_current_context()

    """
    For multi-npu platforms we need to program all front asic namespaces
    """
    namespaces = multi_asic.get_all_namespaces()
    if not namespaces['front_ns']:
        config_db = ValidatedConfigDBConnector(ConfigDBConnector())
        config_db.connect()
        if ADHOC_VALIDATION:
            if validate_mirror_session_config(config_db, session_name, dst_port, src_port, direction) is False:
                return
        try:
            config_db.set_entry("MIRROR_SESSION", session_name, session_info)
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        per_npu_configdb = {}
        for front_asic_namespaces in namespaces['front_ns']:
            per_npu_configdb[front_asic_namespaces] = ValidatedConfigDBConnector(ConfigDBConnector(use_unix_socket_path=True, namespace=front_asic_namespaces))
            per_npu_configdb[front_asic_namespaces].connect()
            if ADHOC_VALIDATION:
                if validate_mirror_session_config(per_npu_configdb[front_asic_namespaces], session_name, dst_port, src_port, direction) is False:
                    return
            try:
                per_npu_configdb[front_asic_namespaces].set_entry("MIRROR_SESSION", session_name, session_info)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))


@mirror_session.command()
@click.argument('session_name', metavar='<session_name>', required=True)
def remove(session_name):
    """ Delete mirror session """

    """
    For multi-npu platforms we need to program all front asic namespaces
    """
    namespaces = multi_asic.get_all_namespaces()
    ctx = click.get_current_context()
    if not namespaces['front_ns']:
        config_db = ValidatedConfigDBConnector(ConfigDBConnector())
        config_db.connect()
        try:
            config_db.set_entry("MIRROR_SESSION", session_name, None)
        except JsonPatchConflict as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        per_npu_configdb = {}
        for front_asic_namespaces in namespaces['front_ns']:
            per_npu_configdb[front_asic_namespaces] = ValidatedConfigDBConnector(ConfigDBConnector(use_unix_socket_path=True, namespace=front_asic_namespaces))
            per_npu_configdb[front_asic_namespaces].connect()
            try:
                per_npu_configdb[front_asic_namespaces].set_entry("MIRROR_SESSION", session_name, None)
            except JsonPatchConflict as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'pfcwd' group ('config pfcwd ...')
#
@config.group(cls=clicommon.AbbreviationGroup)
def pfcwd():
    """Configure pfc watchdog """
    pass

@pfcwd.command()
@click.option('--action', '-a', type=click.Choice(['drop', 'forward', 'alert']))
@click.option('--restoration-time', '-r', type=click.IntRange(100, 60000))
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('ports', nargs=-1)
@click.argument('detection-time', type=click.IntRange(100, 5000))
def start(action, restoration_time, ports, detection_time, verbose):
    """
    Start PFC watchdog on port(s). To config all ports, use all as input.

    Example:
        config pfcwd start --action drop all 400 --restoration-time 400
    """
    cmd = "pfcwd start"

    if action:
        cmd += " --action {}".format(action)

    if ports:
        ports = set(ports) - set(['ports', 'detection-time'])
        cmd += " {}".format(' '.join(ports))

    if detection_time:
        cmd += " {}".format(detection_time)

    if restoration_time:
        cmd += " --restoration-time {}".format(restoration_time)

    clicommon.run_command(cmd, display_cmd=verbose)

@pfcwd.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def stop(verbose):
    """ Stop PFC watchdog """

    cmd = "pfcwd stop"

    clicommon.run_command(cmd, display_cmd=verbose)

@pfcwd.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('poll_interval', type=click.IntRange(100, 3000))
def interval(poll_interval, verbose):
    """ Set PFC watchdog counter polling interval (ms) """

    cmd = "pfcwd interval {}".format(poll_interval)

    clicommon.run_command(cmd, display_cmd=verbose)

@pfcwd.command('counter_poll')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('counter_poll', type=click.Choice(['enable', 'disable']))
def counter_poll(counter_poll, verbose):
    """ Enable/disable counter polling """

    cmd = "pfcwd counter_poll {}".format(counter_poll)

    clicommon.run_command(cmd, display_cmd=verbose)

@pfcwd.command('big_red_switch')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('big_red_switch', type=click.Choice(['enable', 'disable']))
def big_red_switch(big_red_switch, verbose):
    """ Enable/disable BIG_RED_SWITCH mode """

    cmd = "pfcwd big_red_switch {}".format(big_red_switch)

    clicommon.run_command(cmd, display_cmd=verbose)

@pfcwd.command('start_default')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def start_default(verbose):
    """ Start PFC WD by default configurations  """

    cmd = "pfcwd start_default"

    clicommon.run_command(cmd, display_cmd=verbose)

#
# 'cbf' group ('config cbf ...')
#
@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def cbf(ctx):
    """CBF-related configuration tasks"""
    pass

@cbf.command('clear')
def clear():
    """Clear CBF configuration"""
    log.log_info("'cbf clear' executing...")
    _clear_cbf()

@cbf.command('reload')
@click.pass_context
@click.option(
    '--json-data', type=click.STRING,
    help="json string with additional data, valid with --dry-run option"
)
@click.option(
    '--dry_run', type=click.STRING,
    help="Dry run, writes config to the given file"
)
def reload(ctx, dry_run, json_data):
    """Reload CBF configuration"""
    log.log_info("'cbf reload' executing...")
    _clear_cbf()

    _, hwsku_path = device_info.get_paths_to_platform_and_hwsku_dirs()
    sonic_version_file = device_info.get_sonic_version_file()
    from_db = "-d --write-to-db"
    if dry_run:
        from_db = "--additional-data \'{}\'".format(json_data) if json_data else ""

    namespace_list = [DEFAULT_NAMESPACE]
    if multi_asic.get_num_asics() > 1:
        namespace_list = multi_asic.get_namespaces_from_linux()

    for ns in namespace_list:
        if ns is DEFAULT_NAMESPACE:
            asic_id_suffix = ""
            config_db = ConfigDBConnector()
        else:
            asic_id = multi_asic.get_asic_id_from_name(ns)
            if asic_id is None:
                click.secho(
                    "Command 'cbf reload' failed with invalid namespace '{}'".
                        format(ns),
                    fg="yellow"
                )
                raise click.Abort()
            asic_id_suffix = str(asic_id)

            config_db = ConfigDBConnector(
                use_unix_socket_path=True, namespace=ns
            )

        config_db.connect()

        cbf_template_file = os.path.join(hwsku_path, asic_id_suffix, "cbf.json.j2")
        if os.path.isfile(cbf_template_file):
            cmd_ns = "" if ns is DEFAULT_NAMESPACE else "-n {}".format(ns)
            fname = "{}{}".format(dry_run, asic_id_suffix) if dry_run else "config-db"
            command = "{} {} {} -t {},{} -y {}".format(
                SONIC_CFGGEN_PATH, cmd_ns, from_db,
                cbf_template_file, fname, sonic_version_file
            )

            # Apply the configuration
            clicommon.run_command(command, display_cmd=True)
        else:
            click.secho("CBF definition template not found at {}".format(
                cbf_template_file
            ), fg="yellow")

#
# 'qos' group ('config qos ...')
#
@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def qos(ctx):
    """QoS-related configuration tasks"""
    pass

@qos.command('clear')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def clear(verbose):
    """Clear QoS configuration"""
    log.log_info("'qos clear' executing...")
    _clear_qos(verbose=verbose)

def _update_buffer_calculation_model(config_db, model):
    """Update the buffer calculation model into CONFIG_DB"""
    buffer_model_changed = False
    device_metadata = config_db.get_entry('DEVICE_METADATA', 'localhost')
    if device_metadata.get('buffer_model') != model:
        buffer_model_changed = True
        device_metadata['buffer_model'] = model
        config_db.set_entry('DEVICE_METADATA', 'localhost', device_metadata)
    return buffer_model_changed

@qos.command('reload')
@click.pass_context
@click.option('--ports', is_flag=False, required=False, help="List of ports that needs to be updated")
@click.option('--no-dynamic-buffer', is_flag=True, help="Disable dynamic buffer calculation")
@click.option('--no-delay', is_flag=True, hidden=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option(
    '--json-data', type=click.STRING,
    help="json string with additional data, valid with --dry-run option"
)
@click.option(
    '--dry_run', type=click.STRING,
    help="Dry run, writes config to the given file"
)
def reload(ctx, no_dynamic_buffer, no_delay, dry_run, json_data, ports, verbose):
    """Reload QoS configuration"""
    if ports:
        log.log_info("'qos reload --ports {}' executing...".format(ports))
        _qos_update_ports(ctx, ports, dry_run, json_data)
        return

    log.log_info("'qos reload' executing...")
    if not dry_run:
        _clear_qos(delay = not no_delay, verbose=verbose)

    _, hwsku_path = device_info.get_paths_to_platform_and_hwsku_dirs()
    sonic_version_file = device_info.get_sonic_version_file()
    from_db = "-d --write-to-db"
    if dry_run:
        from_db = "--additional-data \'{}\'".format(json_data) if json_data else ""

    namespace_list = [DEFAULT_NAMESPACE]
    if multi_asic.get_num_asics() > 1:
        namespace_list = multi_asic.get_namespaces_from_linux()

    buffer_model_updated = False
    vendors_supporting_dynamic_buffer = ["mellanox", "barefoot"]

    for ns in namespace_list:
        if ns is DEFAULT_NAMESPACE:
            asic_id_suffix = ""
            config_db = ConfigDBConnector()
        else:
            asic_id = multi_asic.get_asic_id_from_name(ns)
            if asic_id is None:
                click.secho(
                    "Command 'qos reload' failed with invalid namespace '{}'".
                        format(ns),
                    fg="yellow"
                )
                raise click.Abort()
            asic_id_suffix = str(asic_id)

            config_db = ConfigDBConnector(
                use_unix_socket_path=True, namespace=ns
            )

        config_db.connect()

        if not no_dynamic_buffer and asic_type in vendors_supporting_dynamic_buffer:
            buffer_template_file = os.path.join(hwsku_path, asic_id_suffix, "buffers_dynamic.json.j2")
            buffer_model_updated |= _update_buffer_calculation_model(config_db, "dynamic")
        else:
            buffer_template_file = os.path.join(hwsku_path, asic_id_suffix, "buffers.json.j2")
            if asic_type in vendors_supporting_dynamic_buffer:
                buffer_model_updated |= _update_buffer_calculation_model(config_db, "traditional")

        if os.path.isfile(buffer_template_file):
            qos_template_file = os.path.join(
                hwsku_path, asic_id_suffix, "qos.json.j2"
            )
            if os.path.isfile(qos_template_file):
                cmd_ns = "" if ns is DEFAULT_NAMESPACE else "-n {}".format(ns)
                fname = "{}{}".format(dry_run, asic_id_suffix) if dry_run else "config-db"
                command = "{} {} {} -t {},{} -t {},{} -y {}".format(
                    SONIC_CFGGEN_PATH, cmd_ns, from_db, buffer_template_file,
                    fname, qos_template_file, fname, sonic_version_file
                )
                # Apply the configurations only when both buffer and qos
                # configuration files are present
                clicommon.run_command(command, display_cmd=True)
            else:
                click.secho("QoS definition template not found at {}".format(
                    qos_template_file
                ), fg="yellow")
        else:
            click.secho("Buffer definition template not found at {}".format(
                buffer_template_file
            ), fg="yellow")

    if buffer_model_updated:
        print("Buffer calculation model updated, restarting swss is required to take effect")

def _qos_update_ports(ctx, ports, dry_run, json_data):
    """Reload QoS configuration"""
    _, hwsku_path = device_info.get_paths_to_platform_and_hwsku_dirs()
    sonic_version_file = device_info.get_sonic_version_file()

    portlist = ports.split(',')
    portset_to_handle = set(portlist)
    portset_handled = set()

    namespace_list = [DEFAULT_NAMESPACE]
    if multi_asic.get_num_asics() > 1:
        namespace_list = multi_asic.get_namespaces_from_linux()

    # Tables whose key is port only
    tables_single_index = [
        'PORT_QOS_MAP',
        'BUFFER_PORT_INGRESS_PROFILE_LIST',
        'BUFFER_PORT_EGRESS_PROFILE_LIST']
    # Tables whose key is port followed by other element
    tables_multi_index = [
        'QUEUE',
        'BUFFER_PG',
        'BUFFER_QUEUE']

    if json_data:
        from_db = "--additional-data \'{}\'".format(json_data) if json_data else ""
    else:
        from_db = "-d"

    items_to_update = {}
    config_dbs = {}

    for ns in namespace_list:
        if ns is DEFAULT_NAMESPACE:
            asic_id_suffix = ""
            config_db = ConfigDBConnector()
        else:
            asic_id = multi_asic.get_asic_id_from_name(ns)
            if asic_id is None:
                click.secho("Command 'qos update' failed with invalid namespace '{}'".format(ns), fg="yellow")
                raise click.Abort()
            asic_id_suffix = str(asic_id)

            config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=ns)

        config_db.connect()
        config_dbs[ns] = config_db
        if is_dynamic_buffer_enabled(config_db):
            buffer_template_file = os.path.join(hwsku_path, asic_id_suffix, "buffers_dynamic.json.j2")
        else:
            buffer_template_file = os.path.join(hwsku_path, asic_id_suffix, "buffers.json.j2")

        if not os.path.isfile(buffer_template_file):
            click.secho("Buffer definition template not found at {}".format(buffer_template_file), fg="yellow")
            ctx.abort()

        qos_template_file = os.path.join(hwsku_path, asic_id_suffix, "qos.json.j2")

        if not os.path.isfile(qos_template_file):
            click.secho("QoS definition template not found at {}".format(qos_template_file), fg="yellow")
            ctx.abort()

        # Remove multi indexed entries first
        for table_name in tables_multi_index:
            entries = config_db.get_keys(table_name)
            for key in entries:
                port, _ = key
                if not port in portset_to_handle:
                    continue
                config_db.set_entry(table_name, '|'.join(key), None)

        cmd_ns = "" if ns is DEFAULT_NAMESPACE else "-n {}".format(ns)
        command = "{} {} {} -t {},config-db -t {},config-db -y {} --print-data".format(
            SONIC_CFGGEN_PATH, cmd_ns, from_db, buffer_template_file, qos_template_file, sonic_version_file
        )
        jsonstr, _ = clicommon.run_command(command, display_cmd=False, return_cmd=True)

        jsondict = json.loads(jsonstr)
        port_table = jsondict.get('PORT')
        if port_table:
            ports_to_update = set(port_table.keys()).intersection(portset_to_handle)
            if not ports_to_update:
                continue
        else:
            continue

        portset_handled.update(ports_to_update)

        items_to_apply = {}

        for table_name in tables_single_index:
            table_items_rendered = jsondict.get(table_name)
            if table_items_rendered:
                for key, data in table_items_rendered.items():
                    port = key
                    if not port in ports_to_update:
                        continue
                    # Push the rendered data to config-db
                    if not items_to_apply.get(table_name):
                        items_to_apply[table_name] = {}
                    items_to_apply[table_name][key] = data

        for table_name in tables_multi_index:
            table_items_rendered = jsondict.get(table_name)
            if table_items_rendered:
                for key, data in table_items_rendered.items():
                    port = key.split('|')[0]
                    if not port in ports_to_update:
                        continue
                    # Push the result to config-db
                    if not items_to_apply.get(table_name):
                        items_to_apply[table_name] = {}
                    items_to_apply[table_name][key] = data

        # Handle CABLE_LENGTH
        # This table needs to be specially handled because the port is not the index but the field name
        # The idea is for all the entries in template, the same entries in CONFIG_DB will be merged together
        # Eg. there is entry AZURE rendered from template for ports Ethernet0, Ethernet4 with cable length "5m":
        # and entry AZURE in CONFIG_DB for ports Ethernet8, Ethernet12, Ethernet16 with cable length "40m"
        # The entry that will eventually be pushed into CONFIG_DB is
        # {"AZURE": {"Ethernet0": "5m", "Ethernet4": "5m", "Ethernet8": "40m", "Ethernet12": "40m", "Ethernet16": "40m"}}
        table_name = 'CABLE_LENGTH'
        cable_length_table = jsondict.get(table_name)
        if cable_length_table:
            for key, item in cable_length_table.items():
                cable_length_from_db = config_db.get_entry(table_name, key)
                cable_length_from_template = {}
                for port in ports_to_update:
                    cable_len = item.get(port)
                    if cable_len:
                        cable_length_from_template[port] = cable_len
                # Reaching this point,
                # - cable_length_from_template contains cable length rendered from the template, eg Ethernet0 and Ethernet4 in the above example
                # - cable_length_from_db contains cable length existing in the CONFIG_DB, eg Ethernet8, Ethernet12, and Ethernet16 in the above exmaple

                if not items_to_apply.get(table_name):
                    items_to_apply[table_name] = {}

                if cable_length_from_db:
                    cable_length_from_db.update(cable_length_from_template)
                    items_to_apply[table_name][key] = cable_length_from_db
                else:
                    items_to_apply[table_name][key] = cable_length_from_template

        if items_to_apply:
            items_to_update[ns] = items_to_apply

        if dry_run:
            with open(dry_run + ns, "w+") as f:
                json.dump(items_to_apply, f, sort_keys=True, indent=4)
        else:
            jsonstr = json.dumps(items_to_apply)
            cmd_ns = "" if ns is DEFAULT_NAMESPACE else "-n {}".format(ns)
            command = "{} {} --additional-data '{}' --write-to-db".format(SONIC_CFGGEN_PATH, cmd_ns, jsonstr)
            clicommon.run_command(command, display_cmd=False)

    if portset_to_handle != portset_handled:
        click.echo("The port(s) {} are not updated because they do not exist".format(portset_to_handle - portset_handled))

def is_dynamic_buffer_enabled(config_db):
    """Return whether the current system supports dynamic buffer calculation"""
    device_metadata = config_db.get_entry('DEVICE_METADATA', 'localhost')
    return 'dynamic' == device_metadata.get('buffer_model')

#
# 'warm_restart' group ('config warm_restart ...')
#
@config.group(cls=clicommon.AbbreviationGroup, name='warm_restart')
@click.pass_context
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def warm_restart(ctx, redis_unix_socket_path):
    """warm_restart-related configuration tasks"""
    # Note: redis_unix_socket_path is a path string, and the ground truth is now from database_config.json.
    # We only use it as a bool indicator on either unix_socket_path or tcp port
    use_unix_socket_path = bool(redis_unix_socket_path)
    config_db = ConfigDBConnector(use_unix_socket_path=use_unix_socket_path)
    config_db.connect(wait_for_init=False)

    # warm restart enable/disable config is put in stateDB, not persistent across cold reboot, not saved to config_DB.json file
    state_db = SonicV2Connector(use_unix_socket_path=use_unix_socket_path)
    state_db.connect(state_db.STATE_DB, False)
    TABLE_NAME_SEPARATOR = '|'
    prefix = 'WARM_RESTART_ENABLE_TABLE' + TABLE_NAME_SEPARATOR
    ctx.obj = {'db': config_db, 'state_db': state_db, 'prefix': prefix}

@warm_restart.command('enable')
@click.argument('module', metavar='<module>', default='system', required=False)
@click.pass_context
def warm_restart_enable(ctx, module):
    state_db = ctx.obj['state_db']
    config_db = ctx.obj['db']
    feature_table = config_db.get_table('FEATURE')
    if module != 'system' and module not in feature_table:
        sys.exit('Feature {} is unknown'.format(module))
    prefix = ctx.obj['prefix']
    _hash = '{}{}'.format(prefix, module)
    state_db.set(state_db.STATE_DB, _hash, 'enable', 'true')
    state_db.close(state_db.STATE_DB)

@warm_restart.command('disable')
@click.argument('module', metavar='<module>', default='system', required=False)
@click.pass_context
def warm_restart_disable(ctx, module):
    state_db = ctx.obj['state_db']
    config_db = ctx.obj['db']
    feature_table = config_db.get_table('FEATURE')
    if module != 'system' and module not in feature_table:
        sys.exit('Feature {} is unknown'.format(module))
    prefix = ctx.obj['prefix']
    _hash = '{}{}'.format(prefix, module)
    state_db.set(state_db.STATE_DB, _hash, 'enable', 'false')
    state_db.close(state_db.STATE_DB)

@warm_restart.command('neighsyncd_timer')
@click.argument('seconds', metavar='<seconds>', required=True, type=int)
@click.pass_context
def warm_restart_neighsyncd_timer(ctx, seconds):
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if seconds not in range(1, 9999):
            ctx.fail("neighsyncd warm restart timer must be in range 1-9999")
    try:
        db.mod_entry('WARM_RESTART', 'swss', {'neighsyncd_timer': seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@warm_restart.command('bgp_timer')
@click.argument('seconds', metavar='<seconds>', required=True, type=int)
@click.pass_context
def warm_restart_bgp_timer(ctx, seconds):
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if seconds not in range(1, 3600):
            ctx.fail("bgp warm restart timer must be in range 1-3600")
    try:
        db.mod_entry('WARM_RESTART', 'bgp', {'bgp_timer': seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@warm_restart.command('teamsyncd_timer')
@click.argument('seconds', metavar='<seconds>', required=True, type=int)
@click.pass_context
def warm_restart_teamsyncd_timer(ctx, seconds):
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if seconds not in range(1, 3600):
            ctx.fail("teamsyncd warm restart timer must be in range 1-3600")
    try:
        db.mod_entry('WARM_RESTART', 'teamd', {'teamsyncd_timer': seconds})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@warm_restart.command('bgp_eoiu')
@click.argument('enable', metavar='<enable>', default='true', required=False, type=click.Choice(["true", "false"]))
@click.pass_context
def warm_restart_bgp_eoiu(ctx, enable):
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    try:
        db.mod_entry('WARM_RESTART', 'bgp', {'bgp_eoiu': enable})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

def vrf_add_management_vrf(config_db):
    """Enable management vrf in config DB"""

    entry = config_db.get_entry('MGMT_VRF_CONFIG', "vrf_global")
    if entry and entry['mgmtVrfEnabled'] == 'true' :
        click.echo("ManagementVRF is already Enabled.")
        return None
    try:
        config_db.mod_entry('MGMT_VRF_CONFIG', "vrf_global", {"mgmtVrfEnabled": "true"})
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


def vrf_delete_management_vrf(config_db):
    """Disable management vrf in config DB"""

    entry = config_db.get_entry('MGMT_VRF_CONFIG', "vrf_global")
    if not entry or entry['mgmtVrfEnabled'] == 'false' :
        click.echo("ManagementVRF is already Disabled.")
        return None
    try:
        config_db.mod_entry('MGMT_VRF_CONFIG', "vrf_global", {"mgmtVrfEnabled": "false"})
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def snmpagentaddress(ctx):
    """SNMP agent listening IP address, port, vrf configuration"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

ip_family = {4: AF_INET, 6: AF_INET6}

@snmpagentaddress.command('add')
@click.argument('agentip', metavar='<SNMP AGENT LISTENING IP Address>', required=True)
@click.option('-p', '--port', help="SNMP AGENT LISTENING PORT")
@click.option('-v', '--vrf', help="VRF Name mgmt/DataVrfName/None")
@click.pass_context
def add_snmp_agent_address(ctx, agentip, port, vrf):
    """Add the SNMP agent listening IP:Port%Vrf configuration"""

    #Construct SNMP_AGENT_ADDRESS_CONFIG table key in the format ip|<port>|<vrf>
    if not clicommon.is_ipaddress(agentip):
        click.echo("Invalid IP address")
        return False
    config_db = ctx.obj['db']
    if not vrf:
        entry = config_db.get_entry('MGMT_VRF_CONFIG', "vrf_global")
        if entry and entry['mgmtVrfEnabled'] == 'true' :
            click.echo("ManagementVRF is Enabled. Provide vrf.")
            return False
    found = 0
    ip = ipaddress.ip_address(agentip)
    for intf in netifaces.interfaces():
        ipaddresses = netifaces.ifaddresses(intf)
        if ip_family[ip.version] in ipaddresses:
            for ipaddr in ipaddresses[ip_family[ip.version]]:
                if agentip.lower() == ipaddr['addr'].lower():
                    found = 1
                    break
        if found == 1:
            break
    else:
        click.echo("IP address is not available")
        return

    key = agentip+'|'
    if port:
        key = key+port
    #snmpd does not start if we have two entries with same ip and port.
    key1 = "SNMP_AGENT_ADDRESS_CONFIG|" + key + '*'
    entry = config_db.get_keys(key1)
    if entry:
        ip_port = agentip + ":" + port
        click.echo("entry with {} already exists ".format(ip_port))
        return
    key = key+'|'
    if vrf:
        key = key+vrf
    config_db.set_entry('SNMP_AGENT_ADDRESS_CONFIG', key, {})

    #Restarting the SNMP service will regenerate snmpd.conf and rerun snmpd
    cmd="systemctl restart snmp"
    os.system (cmd)

@snmpagentaddress.command('del')
@click.argument('agentip', metavar='<SNMP AGENT LISTENING IP Address>', required=True)
@click.option('-p', '--port', help="SNMP AGENT LISTENING PORT")
@click.option('-v', '--vrf', help="VRF Name mgmt/DataVrfName/None")
@click.pass_context
def del_snmp_agent_address(ctx, agentip, port, vrf):
    """Delete the SNMP agent listening IP:Port%Vrf configuration"""

    key = agentip+'|'
    if port:
        key = key+port
    key = key+'|'
    if vrf:
        key = key+vrf
    config_db = ctx.obj['db']
    config_db.set_entry('SNMP_AGENT_ADDRESS_CONFIG', key, None)
    cmd="systemctl restart snmp"
    os.system (cmd)

@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def snmptrap(ctx):
    """SNMP Trap server configuration to send traps"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

@snmptrap.command('modify')
@click.argument('ver', metavar='<SNMP Version>', type=click.Choice(['1', '2', '3']), required=True)
@click.argument('serverip', metavar='<SNMP TRAP SERVER IP Address>', required=True)
@click.option('-p', '--port', help="SNMP Trap Server port, default 162", default="162")
@click.option('-v', '--vrf', help="VRF Name mgmt/DataVrfName/None", default="None")
@click.option('-c', '--comm', help="Community", default="public")
@click.pass_context
def modify_snmptrap_server(ctx, ver, serverip, port, vrf, comm):
    """Modify the SNMP Trap server configuration"""

    #SNMP_TRAP_CONFIG for each SNMP version
    config_db = ctx.obj['db']
    if ver == "1":
        #By default, v1TrapDest value in snmp.yml is "NotConfigured". Modify it.
        config_db.mod_entry('SNMP_TRAP_CONFIG', "v1TrapDest", {"DestIp": serverip, "DestPort": port, "vrf": vrf, "Community": comm})
    elif ver == "2":
        config_db.mod_entry('SNMP_TRAP_CONFIG', "v2TrapDest", {"DestIp": serverip, "DestPort": port, "vrf": vrf, "Community": comm})
    else:
        config_db.mod_entry('SNMP_TRAP_CONFIG', "v3TrapDest", {"DestIp": serverip, "DestPort": port, "vrf": vrf, "Community": comm})

    cmd="systemctl restart snmp"
    os.system (cmd)

@snmptrap.command('del')
@click.argument('ver', metavar='<SNMP Version>', type=click.Choice(['1', '2', '3']), required=True)
@click.pass_context
def delete_snmptrap_server(ctx, ver):
    """Delete the SNMP Trap server configuration"""

    config_db = ctx.obj['db']
    if ver == "1":
        config_db.mod_entry('SNMP_TRAP_CONFIG', "v1TrapDest", None)
    elif ver == "2":
        config_db.mod_entry('SNMP_TRAP_CONFIG', "v2TrapDest", None)
    else:
        config_db.mod_entry('SNMP_TRAP_CONFIG', "v3TrapDest", None)
    cmd="systemctl restart snmp"
    os.system (cmd)



#
# 'snmp' group ('config snmp ...')
#
@config.group(cls=clicommon.AbbreviationGroup, name='snmp')
@clicommon.pass_db
def snmp(db):
    """SNMP configuration tasks"""


@snmp.group(cls=clicommon.AbbreviationGroup)
@clicommon.pass_db
def community(db):
    pass


def is_valid_community_type(commstr_type):
    commstr_types = ['RO', 'RW']
    if commstr_type not in commstr_types:
        click.echo("Invalid community type.  Must be either RO or RW")
        return False
    return True


def is_valid_user_type(user_type):
    convert_user_type = {'noauthnopriv': 'noAuthNoPriv', 'authnopriv': 'AuthNoPriv', 'priv': 'Priv'}
    if user_type not in convert_user_type:
        message = ("Invalid user type.  Must be one of these one of these three "
                   "'noauthnopriv' or 'authnopriv' or 'priv'")
        click.echo(message)
        return False, message
    return True, convert_user_type[user_type]


def is_valid_auth_type(user_auth_type):
    user_auth_types = ['MD5', 'SHA', 'HMAC-SHA-2']
    if user_auth_type not in user_auth_types:
        click.echo("Invalid user authentication type. Must be one of these 'MD5', 'SHA', or 'HMAC-SHA-2'")
        return False
    return True


def is_valid_encrypt_type(encrypt_type):
    encrypt_types = ['DES', 'AES']
    if encrypt_type not in encrypt_types:
        click.echo("Invalid user encryption type.  Must be one of these two 'DES' or 'AES'")
        return False
    return True


def snmp_community_secret_check(snmp_secret):
    excluded_special_symbols = ['@', ":"]
    if len(snmp_secret) > 32:
        click.echo("SNMP community string length should be not be greater than 32")
        click.echo("SNMP community string should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        click.echo("FAILED: SNMP community string length should be not be greater than 32")
        return False
    if any(char in excluded_special_symbols for char in snmp_secret):
        click.echo("SNMP community string length should be not be greater than 32")
        click.echo("SNMP community string should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        click.echo("FAILED: SNMP community string should not have any of these "
                   "special symbols {}".format(excluded_special_symbols))
        return False
    return True


def snmp_username_check(snmp_username):
    excluded_special_symbols = ['@', ":"]
    if len(snmp_username) > 32:
        click.echo("SNMP user {} length should be not be greater than 32 characters".format(snmp_username))
        click.echo("SNMP community string should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        click.echo("FAILED: SNMP user {} length should not be greater than 32 characters".format(snmp_username))
        return False
    if any(char in excluded_special_symbols for char in snmp_username):
        click.echo("SNMP user {} length should be not be greater than 32 characters".format(snmp_username))
        click.echo("SNMP community string should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        click.echo("FAILED: SNMP user {} should not have any of these special "
                   "symbols {}".format(snmp_username, excluded_special_symbols))
        return False
    return True


def snmp_user_secret_check(snmp_secret):
    excluded_special_symbols = ['@', ":"]
    if len(snmp_secret) < 8:
        click.echo("SNMP user password length should be at least 8 characters")
        click.echo("SNMP user password length should be not be greater than 64")
        click.echo("SNMP user password should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        click.echo("FAILED: SNMP user password length should be at least 8 characters")
        return False
    if len(snmp_secret) > 64:
        click.echo("SNMP user password length should be at least 8 characters")
        click.echo("SNMP user password length should be not be greater than 64")
        click.echo("SNMP user password should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        click.echo("FAILED: SNMP user password length should be not be greater than 64")
        return False
    if any(char in excluded_special_symbols for char in snmp_secret):
        click.echo("SNMP user password length should be at least 8 characters")
        click.echo("SNMP user password length should be not be greater than 64")
        click.echo("SNMP user password should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        click.echo("FAILED: SNMP user password should not have any of these special "
                   "symbols {}".format(excluded_special_symbols))
        return False
    return True


@community.command('add')
@click.argument('community', metavar='<snmp_community>', required=True)
@click.argument('string_type', metavar='<RO|RW>', required=True)
@clicommon.pass_db
def add_community(db, community, string_type):
    """ Add snmp community string"""
    string_type = string_type.upper()
    if ADHOC_VALIDATION:
        if not is_valid_community_type(string_type):
            sys.exit(1)
        if not snmp_community_secret_check(community):
            sys.exit(2)
        snmp_communities = db.cfgdb.get_table("SNMP_COMMUNITY")
        if community in snmp_communities:
            click.echo("SNMP community {} is already configured".format(community))
            sys.exit(3)

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    try:
        config_db.set_entry('SNMP_COMMUNITY', community, {'TYPE': string_type})
        click.echo("SNMP community {} added to configuration".format(community))
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("SNMP community configuration failed. Error: {}".format(e))

    try:
        click.echo("Restarting SNMP service...")
        clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
        clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
    except SystemExit as e:
        click.echo("Restart service snmp failed with error {}".format(e))
        raise click.Abort()


@community.command('del')
@click.argument('community', metavar='<snmp_community>', required=True)
@clicommon.pass_db
def del_community(db, community):
    """ Delete snmp community string"""
    if ADHOC_VALIDATION:
        snmp_communities = db.cfgdb.get_table("SNMP_COMMUNITY")
        if community not in snmp_communities:
            click.echo("SNMP community {} is not configured".format(community))
            sys.exit(1)

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    try:
        config_db.set_entry('SNMP_COMMUNITY', community, None)
        click.echo("SNMP community {} removed from configuration".format(community))
    except JsonPatchConflict as e:
        ctx = click.get_current_context()
        ctx.fail("SNMP community {} is not configured. Error: {}".format(community, e))

    try:
        click.echo("Restarting SNMP service...")
        clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
        clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
    except SystemExit as e:
        click.echo("Restart service snmp failed with error {}".format(e))
        raise click.Abort()


@community.command('replace')
@click.argument('current_community', metavar='<current_community_string>', required=True)
@click.argument('new_community', metavar='<new_community_string>', required=True)
@clicommon.pass_db
def replace_community(db, current_community, new_community):
    """ Replace snmp community string"""
    snmp_communities = db.cfgdb.get_table("SNMP_COMMUNITY")
    if not current_community in snmp_communities:
        click.echo("Current SNMP community {} is not configured".format(current_community))
        sys.exit(1)
    if not snmp_community_secret_check(new_community):
        sys.exit(2)
    elif new_community in snmp_communities:
        click.echo("New SNMP community {} to replace current SNMP community {} already "
                   "configured".format(new_community, current_community))
        sys.exit(3)
    else:
        string_type = snmp_communities[current_community]['TYPE']
        db.cfgdb.set_entry('SNMP_COMMUNITY', new_community, {'TYPE': string_type})
        click.echo("SNMP community {} added to configuration".format(new_community))
        db.cfgdb.set_entry('SNMP_COMMUNITY', current_community, None)
        click.echo('SNMP community {} replace community {}'.format(new_community, current_community))
        try:
            click.echo("Restarting SNMP service...")
            clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
            clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
        except SystemExit as e:
            click.echo("Restart service snmp failed with error {}".format(e))
            raise click.Abort()


@snmp.group(cls=clicommon.AbbreviationGroup)
@clicommon.pass_db
def contact(db):
    pass


def is_valid_email(email):
    return bool(re.search(r"^[\w\.\+\-]+\@[\w]+\.[a-z]{2,3}$", email))


@contact.command('add')
@click.argument('contact', metavar='<contact_name>', required=True)
@click.argument('contact_email', metavar='<contact_email>', required=True)
@clicommon.pass_db
def add_contact(db, contact, contact_email):
    """ Add snmp contact name and email """
    snmp = db.cfgdb.get_table("SNMP")
    try:
        if snmp['CONTACT']:
            click.echo("Contact already exists.  Use sudo config snmp contact modify instead")
            sys.exit(1)
        else:
            db.cfgdb.set_entry('SNMP', 'CONTACT', {contact: contact_email}) # TODO: ERROR IN YANG MODEL. Contact name is not defined as key
            click.echo("Contact name {} and contact email {} have been added to "
                       "configuration".format(contact, contact_email))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()
    except KeyError:
        if "CONTACT" not in snmp.keys():
            if not is_valid_email(contact_email):
                click.echo("Contact email {} is not valid".format(contact_email))
                sys.exit(2)
            db.cfgdb.set_entry('SNMP', 'CONTACT', {contact: contact_email})
            click.echo("Contact name {} and contact email {} have been added to "
                       "configuration".format(contact, contact_email))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()


@contact.command('del')
@click.argument('contact', metavar='<contact_name>', required=True)
@clicommon.pass_db
def del_contact(db, contact):
    """ Delete snmp contact name and email """
    snmp = db.cfgdb.get_table("SNMP")
    try:
        if not contact in (list(snmp['CONTACT'].keys()))[0]:
            click.echo("SNMP contact {} is not configured".format(contact))
            sys.exit(1)
        else:
            db.cfgdb.set_entry('SNMP', 'CONTACT', None)
            click.echo("SNMP contact {} removed from configuration".format(contact))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()
    except KeyError:
        if "CONTACT" not in snmp.keys():
            click.echo("Contact name {} is not configured".format(contact))
            sys.exit(2)


@contact.command('modify')
@click.argument('contact', metavar='<contact>', required=True)
@click.argument('contact_email', metavar='<contact email>', required=True)
@clicommon.pass_db
def modify_contact(db, contact, contact_email):
    """ Modify snmp contact"""
    snmp = db.cfgdb.get_table("SNMP")
    try:
        current_snmp_contact_name = (list(snmp['CONTACT'].keys()))[0]
        if current_snmp_contact_name == contact:
            current_snmp_contact_email = snmp['CONTACT'][contact]
        else:
            current_snmp_contact_email = ''
        if contact == current_snmp_contact_name and contact_email == current_snmp_contact_email:
            click.echo("SNMP contact {} {} already exists".format(contact, contact_email))
            sys.exit(1)
        elif contact == current_snmp_contact_name and contact_email != current_snmp_contact_email:
            if not is_valid_email(contact_email):
                click.echo("Contact email {} is not valid".format(contact_email))
                sys.exit(2)
            db.cfgdb.mod_entry('SNMP', 'CONTACT', {contact: contact_email})
            click.echo("SNMP contact {} email updated to {}".format(contact, contact_email))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()
        else:
            if not is_valid_email(contact_email):
                click.echo("Contact email {} is not valid".format(contact_email))
                sys.exit(2)
            db.cfgdb.set_entry('SNMP', 'CONTACT', None)
            db.cfgdb.set_entry('SNMP', 'CONTACT', {contact: contact_email})
            click.echo("SNMP contact {} and contact email {} updated".format(contact, contact_email))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()
    except KeyError:
        if "CONTACT" not in snmp.keys():
            click.echo("Contact name {} is not configured".format(contact))
            sys.exit(3)


@snmp.group(cls=clicommon.AbbreviationGroup)
@clicommon.pass_db
def location(db):
    pass


@location.command('add')
@click.argument('location', metavar='<location>', required=True, nargs=-1)
@clicommon.pass_db
def add_location(db, location):
    """ Add snmp location"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    if isinstance(location, tuple):
        location = " ".join(location)
    elif isinstance(location, list):
        location = " ".join(location)
    snmp = config_db.get_table("SNMP")
    try:
        if snmp['LOCATION']:
            click.echo("Location already exists")
            sys.exit(1)
    except KeyError:
        if "LOCATION" not in snmp.keys():
            try:
                config_db.set_entry('SNMP', 'LOCATION', {'Location': location})
                click.echo("SNMP Location {} has been added to configuration".format(location))
            except ValueError:
                ctx = click.get_current_context()
                ctx.fail("Failed to set SNMP location. Error: {}".format(e))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()


@location.command('del')
@click.argument('location', metavar='<location>', required=True, nargs=-1)
@clicommon.pass_db
def delete_location(db, location):
    """ Delete snmp location"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    if isinstance(location, tuple):
        location = " ".join(location)
    elif isinstance(location, list):
        location = " ".join(location)
    snmp = db.cfgdb.get_table("SNMP")
    try:
        if location == snmp['LOCATION']['Location']:
            try:
                config_db.set_entry('SNMP', 'LOCATION', None)
                click.echo("SNMP Location {} removed from configuration".format(location))
            except (ValueError, JsonPatchConflict) as e:
                ctx = click.get_current_context()
                ctx.fail("Failed to remove SNMP location from configuration. Error: {}".format(e))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()
        else:
            click.echo("SNMP Location {} does not exist.  The location is {}".format(location, snmp['LOCATION']['Location']))
            sys.exit(1)
    except KeyError:
        if "LOCATION" not in snmp.keys():
            click.echo("SNMP Location {} is not configured".format(location))
            sys.exit(2)


@location.command('modify')
@click.argument('location', metavar='<location>', required=True, nargs=-1)
@clicommon.pass_db
def modify_location(db, location):
    """ Modify snmp location"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    if isinstance(location, tuple):
        location = " ".join(location)
    elif isinstance(location, list):
        location = " ".join(location)
    snmp = config_db.get_table("SNMP")
    try:
        snmp_location = snmp['LOCATION']['Location']
        if location in snmp_location:
            click.echo("SNMP location {} already exists".format(location))
            sys.exit(1)
        else:
            try:
                config_db.mod_entry('SNMP', 'LOCATION', {'Location': location})
                click.echo("SNMP location {} modified in configuration".format(location))
            except ValueError as e:
                ctx = click.get_current_context()
                ctx.fail("Failed to modify SNMP location. Error: {}".format(e))
            try:
                click.echo("Restarting SNMP service...")
                clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
                clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
            except SystemExit as e:
                click.echo("Restart service snmp failed with error {}".format(e))
                raise click.Abort()
    except KeyError:
        click.echo("Cannot modify SNMP Location.  You must use 'config snmp location add command <snmp_location>'")
        sys.exit(2)


from enum import IntEnum
class SnmpUserError(IntEnum):
    NameCheckFailure = 1
    TypeNoAuthNoPrivOrAuthNoPrivOrPrivCheckFailure = 2
    RoRwCheckFailure = 3
    NoAuthNoPrivHasAuthType = 4
    AuthTypeMd5OrShaOrHmacsha2IsMissing = 5
    AuthTypeMd5OrShaOrHmacsha2Failure = 6
    AuthPasswordMissing = 7
    AuthPasswordFailsComplexityRequirements = 8
    EncryptPasswordNotAllowedWithAuthNoPriv = 9
    EncryptTypeDesOrAesIsMissing = 10
    EncryptTypeFailsComplexityRequirements = 11
    EncryptPasswordMissingFailure = 12
    EncryptPasswordFailsComplexityRequirements = 13
    UserAlreadyConfigured = 14


@snmp.group(cls=clicommon.AbbreviationGroup)
@clicommon.pass_db
def user(db):
    pass


@user.command('add')
@click.argument('user', metavar='<snmp_user>', required=True)
@click.argument('user_type', metavar='<noAuthNoPriv|AuthNoPriv|Priv>', required=True)
@click.argument('user_permission_type', metavar='<RO|RW>', required=True)
@click.argument('user_auth_type', metavar='<MD5|SHA|HMAC-SHA-2>', required=False)
@click.argument('user_auth_password', metavar='<auth_password>', required=False)
@click.argument('user_encrypt_type', metavar='<DES|AES>', required=False)
@click.argument('user_encrypt_password', metavar='<encrypt_password>', required=False)
@clicommon.pass_db
def add_user(db, user, user_type, user_permission_type, user_auth_type, user_auth_password, user_encrypt_type,
             user_encrypt_password):
    """ Add snmp user"""
    if not snmp_username_check(user):
        sys.exit(SnmpUserError.NameCheckFailure)
    user_type = user_type.lower()
    user_type_info = is_valid_user_type(user_type)
    if not user_type_info[0]:
        sys.exit(SnmpUserError.TypeNoAuthNoPrivOrAuthNoPrivOrPrivCheckFailure)
    user_type = user_type_info[1]
    user_permission_type = user_permission_type.upper()
    if not is_valid_community_type(user_permission_type):
        sys.exit(SnmpUserError.RoRwCheckFailure)
    if user_type == "noAuthNoPriv":
        if user_auth_type:
            click.echo("User auth type not used with 'noAuthNoPriv'.  Please use 'AuthNoPriv' or 'Priv' instead")
            sys.exit(SnmpUserError.NoAuthNoPrivHasAuthType)
    else:
        if not user_auth_type:
            click.echo("User auth type is missing.  Must be MD5, SHA, or HMAC-SHA-2")
            sys.exit(SnmpUserError.AuthTypeMd5OrShaOrHmacsha2IsMissing)
        if user_auth_type:
            user_auth_type = user_auth_type.upper()
            if not is_valid_auth_type(user_auth_type):
                sys.exit(SnmpUserError.AuthTypeMd5OrShaOrHmacsha2Failure)
            elif not user_auth_password:
                click.echo("User auth password is missing")
                sys.exit(SnmpUserError.AuthPasswordMissing)
            elif user_auth_password:
                if not snmp_user_secret_check(user_auth_password):
                    sys.exit(SnmpUserError.AuthPasswordFailsComplexityRequirements)
        if user_type == "AuthNoPriv":
            if user_encrypt_type:
                click.echo("User encrypt type not used with 'AuthNoPriv'.  Please use 'Priv' instead")
                sys.exit(SnmpUserError.EncryptPasswordNotAllowedWithAuthNoPriv)
        elif user_type == "Priv":
            if not user_encrypt_type:
                click.echo("User encrypt type is missing.  Must be DES or AES")
                sys.exit(SnmpUserError.EncryptTypeDesOrAesIsMissing)
            if user_encrypt_type:
                user_encrypt_type = user_encrypt_type.upper()
                if not is_valid_encrypt_type(user_encrypt_type):
                    sys.exit(SnmpUserError.EncryptTypeFailsComplexityRequirements)
                elif not user_encrypt_password:
                    click.echo("User encrypt password is missing")
                    sys.exit(SnmpUserError.EncryptPasswordMissingFailure)
                elif user_encrypt_password:
                    if not snmp_user_secret_check(user_encrypt_password):
                        sys.exit(SnmpUserError.EncryptPasswordFailsComplexityRequirements)
    snmp_users = db.cfgdb.get_table("SNMP_USER")
    if user in snmp_users.keys():
        click.echo("SNMP user {} is already configured".format(user))
        sys.exit(SnmpUserError.UserAlreadyConfigured)
    else:
        if not user_auth_type:
            user_auth_type = ''
        if not user_auth_password:
            user_auth_password = ''
        if not user_encrypt_type:
            user_encrypt_type = ''
        if not user_encrypt_password:
            user_encrypt_password = ''
        db.cfgdb.set_entry('SNMP_USER', user, {'SNMP_USER_TYPE': user_type,
                                               'SNMP_USER_PERMISSION': user_permission_type,
                                               'SNMP_USER_AUTH_TYPE': user_auth_type,
                                               'SNMP_USER_AUTH_PASSWORD': user_auth_password,
                                               'SNMP_USER_ENCRYPTION_TYPE': user_encrypt_type,
                                               'SNMP_USER_ENCRYPTION_PASSWORD': user_encrypt_password})
        click.echo("SNMP user {} added to configuration".format(user))
        try:
            click.echo("Restarting SNMP service...")
            clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
            clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
        except SystemExit as e:
            click.echo("Restart service snmp failed with error {}".format(e))
            raise click.Abort()


@user.command('del')
@click.argument('user', metavar='<snmp_user>', required=True)
@clicommon.pass_db
def del_user(db, user):
    """ Del snmp user"""
    snmp_users = db.cfgdb.get_table("SNMP_USER")
    if user not in snmp_users:
        click.echo("SNMP user {} is not configured".format(user))
        sys.exit(1)
    else:
        db.cfgdb.set_entry('SNMP_USER', user, None)
        click.echo("SNMP user {} removed from configuration".format(user))
        try:
            click.echo("Restarting SNMP service...")
            clicommon.run_command("systemctl reset-failed snmp.service", display_cmd=False)
            clicommon.run_command("systemctl restart snmp.service", display_cmd=False)
        except SystemExit as e:
            click.echo("Restart service snmp failed with error {}".format(e))
            raise click.Abort()

#
# 'bgp' group ('config bgp ...')
#

@config.group(cls=clicommon.AbbreviationGroup)
def bgp():
    """BGP-related configuration tasks"""
    pass

#
# 'shutdown' subgroup ('config bgp shutdown ...')
#

@bgp.group(cls=clicommon.AbbreviationGroup)
def shutdown():
    """Shut down BGP session(s)"""
    pass

# 'all' subcommand
@shutdown.command()
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Shut down all BGP sessions
       In the case of Multi-Asic platform, we shut only the EBGP sessions with external neighbors.
    """
    log.log_info("'bgp shutdown all' executing...")
    namespaces = [DEFAULT_NAMESPACE]

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list['front_ns']

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses(config_db)
        for ipaddress in bgp_neighbor_ip_list:
            _change_bgp_session_status_by_addr(config_db, ipaddress, 'down', verbose)

# 'neighbor' subcommand
@shutdown.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Shut down BGP session by neighbor IP address or hostname.
       User can specify either internal or external BGP neighbor to shutdown
    """
    log.log_info("'bgp shutdown neighbor {}' executing...".format(ipaddr_or_hostname))
    namespaces = [DEFAULT_NAMESPACE]
    found_neighbor = False

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list['front_ns'] + ns_list['back_ns']

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        if _change_bgp_session_status(config_db, ipaddr_or_hostname, 'down', verbose):
            found_neighbor = True

    if not found_neighbor:
        click.get_current_context().fail("Could not locate neighbor '{}'".format(ipaddr_or_hostname))

@bgp.group(cls=clicommon.AbbreviationGroup)
def startup():
    """Start up BGP session(s)"""
    pass

# 'all' subcommand
@startup.command()
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Start up all BGP sessions
       In the case of Multi-Asic platform, we startup only the EBGP sessions with external neighbors.
    """
    log.log_info("'bgp startup all' executing...")
    namespaces = [DEFAULT_NAMESPACE]

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list['front_ns']

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses(config_db)
        for ipaddress in bgp_neighbor_ip_list:
            _change_bgp_session_status_by_addr(config_db, ipaddress, 'up', verbose)

# 'neighbor' subcommand
@startup.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    log.log_info("'bgp startup neighbor {}' executing...".format(ipaddr_or_hostname))
    """Start up BGP session by neighbor IP address or hostname.
       User can specify either internal or external BGP neighbor to startup
    """
    namespaces = [DEFAULT_NAMESPACE]
    found_neighbor = False

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list['front_ns'] + ns_list['back_ns']

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        if _change_bgp_session_status(config_db, ipaddr_or_hostname, 'up', verbose):
            found_neighbor = True

    if not found_neighbor:
        click.get_current_context().fail("Could not locate neighbor '{}'".format(ipaddr_or_hostname))

#
# 'remove' subgroup ('config bgp remove ...')
#

@bgp.group(cls=clicommon.AbbreviationGroup)
def remove():
    "Remove BGP neighbor configuration from the device"
    pass

@remove.command('neighbor')
@click.argument('neighbor_ip_or_hostname', metavar='<neighbor_ip_or_hostname>', required=True)
def remove_neighbor(neighbor_ip_or_hostname):
    """Deletes BGP neighbor configuration of given hostname or ip from devices
       User can specify either internal or external BGP neighbor to remove
    """
    namespaces = [DEFAULT_NAMESPACE]
    removed_neighbor = False

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list['front_ns'] + ns_list['back_ns']

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        if _remove_bgp_neighbor_config(config_db, neighbor_ip_or_hostname):
            removed_neighbor = True

    if not removed_neighbor:
        click.get_current_context().fail("Could not locate neighbor '{}'".format(neighbor_ip_or_hostname))

#
# 'interface' group ('config interface ...')
#

@config.group(cls=clicommon.AbbreviationGroup)
# TODO add "hidden=True if this is a single ASIC platform, once we have click 7.0 in all branches.
@click.option('-n', '--namespace', help='Namespace name',
             required=True if multi_asic.is_multi_asic() else False, type=click.Choice(multi_asic.get_namespace_list()))
@click.pass_context
def interface(ctx, namespace):
    """Interface-related configuration tasks"""
    # Set namespace to default_namespace if it is None.
    if namespace is None:
        namespace = DEFAULT_NAMESPACE
    config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=str(namespace))
    config_db.connect()
    ctx.obj = {'config_db': config_db, 'namespace': str(namespace)}
#
# 'startup' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def startup(ctx, interface_name):
    """Start up interface"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    intf_fs = parse_interface_in_filter(interface_name)
    if len(intf_fs) > 1 and multi_asic.is_multi_asic():
        ctx.fail("Interface range not supported in multi-asic platforms !!")

    if len(intf_fs) == 1 and interface_name_is_valid(config_db, interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    log.log_info("'interface startup {}' executing...".format(interface_name))
    port_dict = config_db.get_table('PORT')
    for port_name in port_dict:
        if port_name in intf_fs:
            config_db.mod_entry("PORT", port_name, {"admin_status": "up"})

    portchannel_list = config_db.get_table("PORTCHANNEL")
    for po_name in portchannel_list:
        if po_name in intf_fs:
            config_db.mod_entry("PORTCHANNEL", po_name, {"admin_status": "up"})

    subport_list = config_db.get_table("VLAN_SUB_INTERFACE")
    for sp_name in subport_list:
        if sp_name in intf_fs:
            config_db.mod_entry("VLAN_SUB_INTERFACE", sp_name, {"admin_status": "up"})

#
# 'shutdown' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def shutdown(ctx, interface_name):
    """Shut down interface"""
    log.log_info("'interface shutdown {}' executing...".format(interface_name))
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    intf_fs = parse_interface_in_filter(interface_name)
    if len(intf_fs) > 1 and multi_asic.is_multi_asic():
        ctx.fail("Interface range not supported in multi-asic platforms !!")

    if len(intf_fs) == 1 and interface_name_is_valid(config_db, interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    port_dict = config_db.get_table('PORT')
    for port_name in port_dict:
        if port_name in intf_fs:
            config_db.mod_entry("PORT", port_name, {"admin_status": "down"})

    portchannel_list = config_db.get_table("PORTCHANNEL")
    for po_name in portchannel_list:
        if po_name in intf_fs:
            config_db.mod_entry("PORTCHANNEL", po_name, {"admin_status": "down"})

    subport_list = config_db.get_table("VLAN_SUB_INTERFACE")
    for sp_name in subport_list:
        if sp_name in intf_fs:
            config_db.mod_entry("VLAN_SUB_INTERFACE", sp_name, {"admin_status": "down"})

#
# 'speed' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_speed', metavar='<interface_speed>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def speed(ctx, interface_name, interface_speed, verbose):
    """Set interface speed"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    log.log_info("'interface speed {} {}' executing...".format(interface_name, interface_speed))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -s {}".format(interface_name, interface_speed)
    else:
        command = "portconfig -p {} -s {} -n {}".format(interface_name, interface_speed, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'link-training' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('mode', metavar='<mode>', required=True, type=click.Choice(["on", "off"]))
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def link_training(ctx, interface_name, mode, verbose):
    """Set interface link training mode"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    log.log_info("'interface link-training {} {}' executing...".format(interface_name, mode))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -lt {}".format(interface_name, mode)
    else:
        command = "portconfig -p {} -lt {} -n {}".format(interface_name, mode, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'autoneg' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('mode', metavar='<mode>', required=True, type=click.Choice(["enabled", "disabled"]))
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def autoneg(ctx, interface_name, mode, verbose):
    """Set interface auto negotiation mode"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    log.log_info("'interface autoneg {} {}' executing...".format(interface_name, mode))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -an {}".format(interface_name, mode)
    else:
        command = "portconfig -p {} -an {} -n {}".format(interface_name, mode, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'adv-speeds' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('speed_list', metavar='<speed_list>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def advertised_speeds(ctx, interface_name, speed_list, verbose):
    """Set interface advertised speeds"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    log.log_info("'interface advertised_speeds {} {}' executing...".format(interface_name, speed_list))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -S {}".format(interface_name, speed_list)
    else:
        command = "portconfig -p {} -S {} -n {}".format(interface_name, speed_list, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'interface-type' subcommand
#

@interface.command(name='type')
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_type_value', metavar='<interface_type_value>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def interface_type(ctx, interface_name, interface_type_value, verbose):
    """Set interface type"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    log.log_info("'interface interface_type {} {}' executing...".format(interface_name, interface_type_value))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -t {}".format(interface_name, interface_type_value)
    else:
        command = "portconfig -p {} -t {} -n {}".format(interface_name, interface_type_value, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'advertised-interface-types' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_type_list', metavar='<interface_type_list>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def advertised_types(ctx, interface_name, interface_type_list, verbose):
    """Set interface advertised types"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    log.log_info("'interface advertised_interface_types {} {}' executing...".format(interface_name, interface_type_list))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -T {}".format(interface_name, interface_type_list)
    else:
        command = "portconfig -p {} -T {} -n {}".format(interface_name, interface_type_list, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'breakout' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('mode', required=True, type=click.STRING, autocompletion=_get_breakout_options)
@click.option('-f', '--force-remove-dependencies', is_flag=True,  help='Clear all dependencies internally first.')
@click.option('-l', '--load-predefined-config', is_flag=True,  help='load predefied user configuration (alias, lanes, speed etc) first.')
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false, expose_value=False, prompt='Do you want to Breakout the port, continue?')
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
@click.pass_context
def breakout(ctx, interface_name, mode, verbose, force_remove_dependencies, load_predefined_config):
    """ Set interface breakout mode """
    breakout_cfg_file = device_info.get_path_to_port_config_file()

    if not os.path.isfile(breakout_cfg_file) or not breakout_cfg_file.endswith('.json'):
        click.secho("[ERROR] Breakout feature is not available without platform.json file", fg='red')
        raise click.Abort()

    # Get the config_db connector
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])

    target_brkout_mode = mode

    # Get current breakout mode
    cur_brkout_dict = config_db.get_table('BREAKOUT_CFG')
    if len(cur_brkout_dict) == 0:
        click.secho("[ERROR] BREAKOUT_CFG table is NOT present in CONFIG DB", fg='red')
        raise click.Abort()

    if interface_name not in cur_brkout_dict.keys():
        click.secho("[ERROR] {} interface is NOT present in BREAKOUT_CFG table of CONFIG DB".format(interface_name), fg='red')
        raise click.Abort()

    cur_brkout_mode = cur_brkout_dict[interface_name]["brkout_mode"]

    # Validate Interface and Breakout mode
    if not _validate_interface_mode(ctx, breakout_cfg_file, interface_name, mode, cur_brkout_mode):
        raise click.Abort()

    """ Interface Deletion Logic """
    # Get list of interfaces to be deleted
    del_ports = get_child_ports(interface_name, cur_brkout_mode, breakout_cfg_file)
    del_intf_dict = {intf: del_ports[intf]["speed"] for intf in del_ports}

    if del_intf_dict:
        click.echo("\nPorts to be deleted : \n {}".format(json.dumps(del_intf_dict, indent=4)))
    else:
        click.secho("[ERROR] del_intf_dict is None! No interfaces are there to be deleted", fg='red')
        raise click.Abort()

    """ Interface Addition Logic """
    # Get list of interfaces to be added
    add_ports = get_child_ports(interface_name, target_brkout_mode, breakout_cfg_file)
    add_intf_dict = {intf: add_ports[intf]["speed"] for intf in add_ports}

    if add_intf_dict:
        click.echo("Ports to be added : \n {}".format(json.dumps(add_intf_dict, indent=4)))
    else:
        click.secho("[ERROR] port_dict is None!", fg='red')
        raise click.Abort()

    # validate all del_ports before calling breakOutPort
    for intf in del_intf_dict.keys():
        if not interface_name_is_valid(config_db, intf):
            click.secho("[ERROR] Interface name {} is invalid".format(intf))
            raise click.Abort()

    port_dict = {}
    for intf in add_intf_dict:
        if intf in add_ports:
            port_dict[intf] = add_ports[intf]

    # writing JSON object
    with open('new_port_config.json', 'w') as f:
        json.dump(port_dict, f, indent=4)

    # Start Interation with Dy Port BreakOut Config Mgmt
    try:
        """ Load config for the commands which are capable of change in config DB """
        cm = load_ConfigMgmt(verbose)

        """ Delete all ports if forced else print dependencies using ConfigMgmt API """
        final_delPorts = [intf for intf in del_intf_dict]
        """ Warn user if tables without yang models exist and have final_delPorts """
        breakout_warnUser_extraTables(cm, final_delPorts, confirm=True)

        # Create a dictionary containing all the added ports with its capabilities like alias, lanes, speed etc.
        portJson = dict(); portJson['PORT'] = port_dict

        # breakout_Ports will abort operation on failure, So no need to check return
        breakout_Ports(cm, delPorts=final_delPorts, portJson=portJson, force=force_remove_dependencies,
                       loadDefConfig=load_predefined_config, verbose=verbose)

        # Set Current Breakout mode in config DB
        brkout_cfg_keys = config_db.get_keys('BREAKOUT_CFG')
        if interface_name not in  brkout_cfg_keys:
            click.secho("[ERROR] {} is not present in 'BREAKOUT_CFG' Table!".format(interface_name), fg='red')
            raise click.Abort()
        try:
            config_db.set_entry("BREAKOUT_CFG", interface_name, {'brkout_mode': target_brkout_mode})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        click.secho("Breakout process got successfully completed."
                    .format(interface_name), fg="cyan", underline=True)
        click.echo("Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.")

    except Exception as e:
        click.secho("Failed to break out Port. Error: {}".format(str(e)), fg='magenta')

        sys.exit(0)

def _get_all_mgmtinterface_keys():
    """Returns list of strings containing mgmt interface keys
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    return list(config_db.get_table('MGMT_INTERFACE').keys())


#
# 'mtu' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_mtu', metavar='<interface_mtu>', required=True, type=click.IntRange(68, 9216))
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def mtu(ctx, interface_name, interface_mtu, verbose):
    """Set interface mtu"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    portchannel_member_table = config_db.get_table('PORTCHANNEL_MEMBER')
    if interface_is_in_portchannel(portchannel_member_table, interface_name):
        ctx.fail("'interface_name' is in portchannel!")

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -m {}".format(interface_name, interface_mtu)
    else:
        command = "portconfig -p {} -m {} -n {}".format(interface_name, interface_mtu, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'tpid' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_tpid', metavar='<interface_tpid>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def tpid(ctx, interface_name, interface_tpid, verbose):
    """Set interface tpid"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -tp {}".format(interface_name, interface_tpid)
    else:
        command = "portconfig -p {} -tp {} -n {}".format(interface_name, interface_tpid, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)


@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_fec', metavar='<interface_fec>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def fec(ctx, interface_name, interface_fec, verbose):
    """Set interface fec"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -f {}".format(interface_name, interface_fec)
    else:
        command = "portconfig -p {} -f {} -n {}".format(interface_name, interface_fec, ctx.obj['namespace'])

    if verbose:
        command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)

#
# 'ip' subgroup ('config interface ip ...')
#

@interface.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def ip(ctx):
    """Set IP interface attributes"""
    pass

#
# 'add' subcommand
#

@ip.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument("ip_addr", metavar="<ip_addr>", required=True)
@click.argument('gw', metavar='<default gateway IP address>', required=False)
@click.pass_context
def add(ctx, interface_name, ip_addr, gw):
    """Add an IP address towards the interface"""
    # Get the config_db connector
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    # Add a validation to check this interface is not a member in vlan before
    # changing it to a router port
    vlan_member_table = config_db.get_table('VLAN_MEMBER')
    if (interface_is_in_vlan(vlan_member_table, interface_name)):
        click.echo("Interface {} is a member of vlan\nAborting!".format(interface_name))
        return

    portchannel_member_table = config_db.get_table('PORTCHANNEL_MEMBER')

    if interface_is_in_portchannel(portchannel_member_table, interface_name):
        ctx.fail("{} is configured as a member of portchannel."
                .format(interface_name))

    try:
        ip_address = ipaddress.ip_interface(ip_addr)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    if interface_name == 'eth0':

        # Configuring more than 1 IPv4 or more than 1 IPv6 address fails.
        # Allow only one IPv4 and only one IPv6 address to be configured for IPv6.
        # If a row already exist, overwrite it (by doing delete and add).
        mgmtintf_key_list = _get_all_mgmtinterface_keys()

        for key in mgmtintf_key_list:
            # For loop runs for max 2 rows, once for IPv4 and once for IPv6.
            # No need to capture the exception since the ip_addr is already validated earlier
            current_ip = ipaddress.ip_interface(key[1])
            if (ip_address.version == current_ip.version):
                # If user has configured IPv4/v6 address and the already available row is also IPv4/v6, delete it here.
                config_db.set_entry("MGMT_INTERFACE", ("eth0", key[1]), None)

        # Set the new row with new value
        if not gw:
            config_db.set_entry("MGMT_INTERFACE", (interface_name, str(ip_address)), {"NULL": "NULL"})
        else:
            config_db.set_entry("MGMT_INTERFACE", (interface_name, str(ip_address)), {"gwaddr": gw})

        return

    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")
    interface_entry = config_db.get_entry(table_name, interface_name)
    if len(interface_entry) == 0:
        if table_name == "VLAN_SUB_INTERFACE":
            config_db.set_entry(table_name, interface_name, {"admin_status": "up"})
        else:
            config_db.set_entry(table_name, interface_name, {"NULL": "NULL"})
    config_db.set_entry(table_name, (interface_name, str(ip_address)), {"NULL": "NULL"})

#
# 'del' subcommand
#

@ip.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument("ip_addr", metavar="<ip_addr>", required=True)
@click.pass_context
def remove(ctx, interface_name, ip_addr):
    """Remove an IP address from the interface"""
    # Get the config_db connector
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    try:
        ip_address = ipaddress.ip_interface(ip_addr)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    if interface_name == 'eth0':
        config_db.set_entry("MGMT_INTERFACE", (interface_name, str(ip_address)), None)
        return

    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")
    interface_addresses = get_interface_ipaddresses(config_db, interface_name)
    # If we deleting the last IP entry of the interface, check whether a static route present for the RIF
    # before deleting the entry and also the RIF.
    if interface_addresses == {ip_address}:
        # Check both IPv4 and IPv6 routes.
        ip_versions = [ "ip", "ipv6"]
        for ip_ver in ip_versions:
            # Compete the command and ask Zebra to return the routes.
            # Scopes of all VRFs will be checked.
            cmd = "show {} route vrf all static".format(ip_ver)
            if multi_asic.is_multi_asic():
                output = bgp_util.run_bgp_command(cmd, ctx.obj['namespace'])
            else:
                output = bgp_util.run_bgp_command(cmd)
            # If there is output data, check is there a static route,
            # bound to the interface.
            if output != "":
                if any(interface_name in output_line for output_line in output.splitlines()):
                    ctx.fail("Cannot remove the last IP entry of interface {}. A static {} route is still bound to the RIF.".format(interface_name, ip_ver))
    remove_router_interface_ip_address(config_db, interface_name, ip_address)
    interface_addresses = get_interface_ipaddresses(config_db, interface_name)
    if len(interface_addresses) == 0 and is_interface_bind_to_vrf(config_db, interface_name) is False and get_intf_ipv6_link_local_mode(ctx, interface_name, table_name) != "enable":
        if table_name != "VLAN_SUB_INTERFACE":
            config_db.set_entry(table_name, interface_name, None)

    if multi_asic.is_multi_asic():
        command = "sudo ip netns exec {} ip neigh flush dev {} {}".format(ctx.obj['namespace'], interface_name, str(ip_address))
    else:
        command = "ip neigh flush dev {} {}".format(interface_name, str(ip_address))
    clicommon.run_command(command)

#
# 'loopback-action' subcommand
#

@ip.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('action', metavar='<action>', required=True)
@click.pass_context
def loopback_action(ctx, interface_name, action):
    """Set IP interface loopback action"""
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail('Interface {} is invalid'.format(interface_name))

    if not clicommon.is_interface_in_config_db(config_db, interface_name):
        ctx.fail('Interface {} is not an IP interface'.format(interface_name))

    allowed_actions = ['drop', 'forward']
    if action not in allowed_actions:
        ctx.fail('Invalid action')

    table_name = get_interface_table_name(interface_name)
    config_db.mod_entry(table_name, interface_name, {"loopback_action": action})

#
# buffer commands and utilities
#
def buffer_objects_map_check_legality(ctx, db, interface_name, input_map, is_new_id, is_pg):
    """
    Tool function to check whether input_map is legal.
    Three checking performed:
    1. Whether the input_map is legal: pgs are in range [0-7]
    2. Whether the input_map overlaps an existing pg in the port
    """
    def _parse_object_id(idsmap):
        """
        Tool function to parse the idsmap
        Args:
            idsmap: string containing object IDs map, like 3-4 or 7
        Return:
            The upper and lower bound. In case the idsmap is illegal, it returns None, None
        Example:
            3-4 => 3, 4
            7   => 7
            3-  => None, None
        """
        try:
            match = re.search("^([0-9]+)(-[0-9]+)?$", idsmap)
            lower = int(match.group(1))
            if match.group(2):
                upper = int(match.group(2)[1:])
            else:
                upper = lower
        except Exception:
            lower, upper = None, None

        return lower, upper

    config_db = db.cfgdb
    object_name = "priority group" if is_pg else "queue"

    try:
        # Fetch maximum object id from STATE_DB
        state_db = db.db
        field_name = 'max_priority_groups' if is_pg else 'max_queues'

        _hash = 'BUFFER_MAX_PARAM_TABLE|{}'.format(interface_name)
        buffer_max_params = state_db.get_all(state_db.STATE_DB, _hash)
        maximum_id = int(buffer_max_params.get(field_name)) - 1
    except Exception:
        ctx.fail("Unable to fetch {} from {} in STATE_DB".format(field_name, _hash))

    lower, upper = _parse_object_id(input_map)
    if not upper or not lower or upper < lower or lower < 0 or upper > maximum_id:
        ctx.fail("Buffer {} {} is not valid.".format(object_name, input_map))

    # Check overlapping.
    # To configure a new PG which is overlapping an existing one is not allowed
    # For example, to add '5-6' while '3-5' existing is illegal
    existing_object_maps = config_db.get_table("BUFFER_PG" if is_pg else "BUFFER_QUEUE")
    if not is_new_id:
        if not (interface_name, input_map) in existing_object_maps.keys():
            ctx.fail("Buffer {} {} doesn't exist".format(object_name, input_map))
        return

    for k, v in existing_object_maps.items():
        port, existing_object_map = k
        if port == interface_name:
            existing_lower, existing_upper = _parse_object_id(existing_object_map)
            if existing_upper < lower or existing_lower > upper:
                # new and existing pgs disjoint, legal
                pass
            else:
                ctx.fail("Buffer {} {} overlaps with existing {} {}".format(object_name, input_map, object_name, existing_object_map))


def update_buffer_object(db, interface_name, object_map, override_profile, is_pg, add=True):
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    # Check whether port is legal
    ports = config_db.get_entry("PORT", interface_name)
    if not ports:
        ctx.fail("Port {} doesn't exist".format(interface_name))

    buffer_table = "BUFFER_PG" if is_pg else "BUFFER_QUEUE"

    # Check whether object_map is legal
    # Check whether there is other lossless profiles configured on the interface
    buffer_objects_map_check_legality(ctx, db, interface_name, object_map, add, is_pg)

    # All checking passed
    if override_profile:
        profile_dict = config_db.get_entry("BUFFER_PROFILE", override_profile)
        if not profile_dict:
            ctx.fail("Profile {} doesn't exist".format(override_profile))
        pool_name = profile_dict.get("pool")
        if not pool_name:
            ctx.fail("Profile {} is invalid".format(override_profile))
        pool_dict = config_db.get_entry("BUFFER_POOL", pool_name)
        pool_dir = pool_dict.get("type")
        expected_dir = "ingress" if is_pg else "egress"
        if pool_dir != expected_dir:
            ctx.fail("Type of pool {} referenced by profile {} is wrong".format(pool_name, override_profile))
        if is_pg:
            if not 'xoff' in profile_dict.keys() and 'size' in profile_dict.keys():
                ctx.fail("Profile {} doesn't exist or isn't a lossless profile".format(override_profile))
        try:
            config_db.set_entry(buffer_table, (interface_name, object_map), {"profile": override_profile})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        try:
            config_db.set_entry(buffer_table, (interface_name, object_map), {"profile": "NULL"})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    if is_pg:
        adjust_pfc_enable(ctx, db, interface_name, object_map, True)


def remove_buffer_object_on_port(db, interface_name, buffer_object_map, is_pg=True):
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    # Check whether port is legal
    ports = config_db.get_entry("PORT", interface_name)
    if not ports:
        ctx.fail("Port {} doesn't exist".format(interface_name))

    # Remvoe all dynamic lossless PGs on the port
    buffer_table = "BUFFER_PG" if is_pg else "BUFFER_QUEUE"
    existing_buffer_objects = config_db.get_table(buffer_table)
    removed = False
    for k, v in existing_buffer_objects.items():
        port, existing_buffer_object = k
        if port == interface_name and (not buffer_object_map or buffer_object_map == existing_buffer_object):
            referenced_profile = v.get('profile')
            if referenced_profile and referenced_profile == 'ingress_lossy_profile':
                if buffer_object_map:
                    ctx.fail("Lossy PG {} can't be removed".format(buffer_object_map))
                else:
                    continue
            try:
                config_db.set_entry(buffer_table, (interface_name, existing_buffer_object), None)
            except JsonPatchConflict as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
            if is_pg:
                adjust_pfc_enable(ctx, db, interface_name, buffer_object_map, False)
            removed = True
    if not removed:
        object_name = "lossless priority group" if is_pg else "queue"
        if buffer_object_map:
            ctx.fail("No specified {} {} found on port {}".format(object_name, buffer_object_map, interface_name))
        else:
            ctx.fail("No {} found on port {}".format(object_name, interface_name))


def adjust_pfc_enable(ctx, db, interface_name, pg_map, add):
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    # Fetch the original pfc_enable
    qosmap = config_db.get_entry("PORT_QOS_MAP", interface_name)
    pfc_enable = qosmap.get("pfc_enable")

    pfc_set = set()
    if pfc_enable:
        for priority in pfc_enable.split(","):
            pfc_set.add(int(priority))

    if pg_map:
        lower_bound = int(pg_map[0])
        upper_bound = int(pg_map[-1])

        for priority in range(lower_bound, upper_bound + 1):
            if add:
                pfc_set.add(priority)
            elif priority in pfc_set:
                pfc_set.remove(priority)

        empty_set = set()
        pfc_enable = ""
        if not pfc_set.issubset(empty_set):
            for priority in pfc_set:
                pfc_enable += str(priority) + ","
    elif not add:
        # Remove all
        pfc_enable = ""
    else:
        ctx.fail("Try to add empty priorities")

    qosmap["pfc_enable"] = pfc_enable[:-1]
    try:
        config_db.set_entry("PORT_QOS_MAP", interface_name, qosmap)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


#
# 'buffer' subgroup ('config interface buffer ...')
#
@interface.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def buffer(ctx):
    """Set or clear buffer configuration"""
    config_db = ctx.obj["config_db"]
    if not is_dynamic_buffer_enabled(config_db):
        ctx.fail("This command can only be executed on a system with dynamic buffer enabled")


#
# 'priority_group' subgroup ('config interface buffer priority_group ...')
#
@buffer.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def priority_group(ctx):
    """Set or clear buffer configuration"""
    pass


#
# 'lossless' subgroup ('config interface buffer priority_group lossless ...')
#
@priority_group.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def lossless(ctx):
    """Set or clear lossless PGs"""
    pass


#
# 'add' subcommand
#
@lossless.command('add')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('pg_map', metavar='<pg_map>', required=True)
@click.argument('override_profile', metavar='<override_profile>', required=False)
@clicommon.pass_db
def add_pg(db, interface_name, pg_map, override_profile):
    """Set lossless PGs for the interface"""
    update_buffer_object(db, interface_name, pg_map, override_profile, True)


#
# 'set' subcommand
#
@lossless.command('set')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('pg_map', metavar='<pg_map>', required=True)
@click.argument('override_profile', metavar='<override_profile>', required=False)
@clicommon.pass_db
def set_pg(db, interface_name, pg_map, override_profile):
    """Set lossless PGs for the interface"""
    update_buffer_object(db, interface_name, pg_map, override_profile, True, False)


#
# 'remove' subcommand
#
@lossless.command('remove')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('pg_map', metavar='<pg_map', required=False)
@clicommon.pass_db
def remove_pg(db, interface_name, pg_map):
    """Clear lossless PGs for the interface"""
    remove_buffer_object_on_port(db, interface_name, pg_map)


#
# 'queue' subgroup ('config interface buffer queue ...')
#
@buffer.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def queue(ctx):
    """Set or clear buffer configuration"""
    pass


#
# 'add' subcommand
#
@queue.command('add')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('queue_map', metavar='<queue_map>', required=True)
@click.argument('buffer_profile', metavar='<buffer_profile>', required=True)
@clicommon.pass_db
def add_queue(db, interface_name, queue_map, buffer_profile):
    """Set lossless QUEUEs for the interface"""
    update_buffer_object(db, interface_name, queue_map, buffer_profile, False)


#
# 'set' subcommand
#
@queue.command('set')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('queue_map', metavar='<queue_map>', required=True)
@click.argument('buffer_profile', metavar='<buffer_profile>', required=True)
@clicommon.pass_db
def set_queue(db, interface_name, queue_map, buffer_profile):
    """Set lossless QUEUEs for the interface"""
    update_buffer_object(db, interface_name, queue_map, buffer_profile, False, False)


#
# 'remove' subcommand
#
@queue.command('remove')
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('queue_map', metavar='<queue_map>', required=False)
@clicommon.pass_db
def remove_queue(db, interface_name, queue_map):
    """Clear lossless QUEUEs for the interface"""
    remove_buffer_object_on_port(db, interface_name, queue_map, False)


#
# 'cable_length' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('length', metavar='<length>', required=True)
@click.pass_context
def cable_length(ctx, interface_name, length):
    """Set interface cable length"""
    config_db = ValidatedConfigDBConnector(ctx.obj["config_db"])

    if not is_dynamic_buffer_enabled(config_db):
        ctx.fail("This command can only be supported on a system with dynamic buffer enabled")

    if ADHOC_VALIDATION:
        # Check whether port is legal
        ports = config_db.get_entry("PORT", interface_name)
        if not ports:
            ctx.fail("Port {} doesn't exist".format(interface_name))

        try:
            assert "m" == length[-1]
        except Exception:
            ctx.fail("Invalid cable length. Should be in format <num>m, like 300m".format(cable_length))

    keys = config_db.get_keys("CABLE_LENGTH")

    cable_length_set = {}
    cable_length_set[interface_name] = length
    try:
        config_db.mod_entry("CABLE_LENGTH", keys[0], cable_length_set)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'transceiver' subgroup ('config interface transceiver ...')
#

@interface.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def transceiver(ctx):
    """SFP transceiver configuration"""
    pass

#
# 'frequency' subcommand ('config interface transceiver frequency ...')
#
@transceiver.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('frequency', metavar='<frequency>', required=True, type=int)
def frequency(ctx, interface_name, frequency):
    """Set transciever (only for 400G-ZR) frequency"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(config_db, interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    log.log_info("{} Setting transceiver frequency {} GHz".format(interface_name, frequency))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -F {}".format(interface_name, frequency)
    else:
        command = "portconfig -p {} -F {} -n {}".format(interface_name, frequency, ctx.obj['namespace'])

    clicommon.run_command(command)


#
# 'tx_power' subcommand ('config interface transceiver tx_power ...')
# For negative float use:-
# config interface transceiver tx_power Ethernet0 -- -27.4"
#
@transceiver.command('tx_power')
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('tx-power', metavar='<tx-power>', required=True, type=float)
def tx_power(ctx, interface_name, tx_power):
    """Set transciever (only for 400G-ZR) Tx laser power"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(config_db, interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    log.log_info("{} Setting transceiver power {} dBm".format(interface_name, tx_power))

    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        command = "portconfig -p {} -P {}".format(interface_name, tx_power)
    else:
        command = "portconfig -p {} -P {} -n {}".format(interface_name, tx_power, ctx.obj['namespace'])

    clicommon.run_command(command)

#
# 'lpmode' subcommand ('config interface transceiver lpmode ...')
#

@transceiver.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('state', metavar='(enable|disable)', type=click.Choice(['enable', 'disable']))
@click.pass_context
def lpmode(ctx, interface_name, state):
    """Enable/disable low-power mode for SFP transceiver module"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(config_db, interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    cmd = "sudo sfputil lpmode {} {}".format("on" if state == "enable" else "off", interface_name)
    clicommon.run_command(cmd)

#
# 'reset' subcommand ('config interface reset ...')
#

@transceiver.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def reset(ctx, interface_name):
    """Reset SFP transceiver module"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(config_db, interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    cmd = "sudo sfputil reset {}".format(interface_name)
    clicommon.run_command(cmd)

#
# 'mpls' subgroup ('config interface mpls ...')
#

@interface.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def mpls(ctx):
    """Add or remove MPLS"""
    pass

#
# 'add' subcommand
#

@mpls.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def add(ctx, interface_name):
    """Add MPLS operation on the interface"""
    config_db = ctx.obj["config_db"]
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    table_name = get_interface_table_name(interface_name)
    if not clicommon.is_interface_in_config_db(config_db, interface_name):
        ctx.fail('interface {} doesn`t exist'.format(interface_name))
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan]")
    config_db.set_entry(table_name, interface_name, {"mpls": "enable"})

#
# 'remove' subcommand
#

@mpls.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def remove(ctx, interface_name):
    """Remove MPLS operation from the interface"""
    config_db = ctx.obj["config_db"]
    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    table_name = get_interface_table_name(interface_name)
    if not clicommon.is_interface_in_config_db(config_db, interface_name):
        ctx.fail('interface {} doesn`t exist'.format(interface_name))
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan]")
    config_db.set_entry(table_name, interface_name, {"mpls": "disable"})

#
# 'vrf' subgroup ('config interface vrf ...')
#


@interface.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def vrf(ctx):
    """Bind or unbind VRF"""
    pass

#
# 'bind' subcommand
#
@vrf.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('vrf_name', metavar='<vrf_name>', required=True)
@click.pass_context
def bind(ctx, interface_name, vrf_name):
    """Bind the interface to VRF"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if not is_vrf_exists(config_db, vrf_name):
        ctx.fail("VRF %s does not exist!"%(vrf_name))

    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")
    if is_interface_bind_to_vrf(config_db, interface_name) is True and \
        config_db.get_entry(table_name, interface_name).get('vrf_name') == vrf_name:
        return
    # Clean ip addresses if interface configured
    interface_addresses = get_interface_ipaddresses(config_db, interface_name)
    for ipaddress in interface_addresses:
        remove_router_interface_ip_address(config_db, interface_name, ipaddress)
    if table_name == "VLAN_SUB_INTERFACE":
        subintf_entry = config_db.get_entry(table_name, interface_name)
        if 'vrf_name' in subintf_entry:
            subintf_entry.pop('vrf_name')

    config_db.set_entry(table_name, interface_name, None)
    # When config_db del entry and then add entry with same key, the DEL will lost.
    if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
        state_db = SonicV2Connector(use_unix_socket_path=True)
    else:
        state_db = SonicV2Connector(use_unix_socket_path=True, namespace=ctx.obj['namespace'])
    state_db.connect(state_db.STATE_DB, False)
    _hash = '{}{}'.format('INTERFACE_TABLE|', interface_name)
    while state_db.exists(state_db.STATE_DB, _hash):
        time.sleep(0.01)
    state_db.close(state_db.STATE_DB)
    if table_name == "VLAN_SUB_INTERFACE":
        subintf_entry['vrf_name'] = vrf_name
        config_db.set_entry(table_name, interface_name, subintf_entry)
    else:
        config_db.set_entry(table_name, interface_name, {"vrf_name": vrf_name})

    click.echo("Interface {} IP disabled and address(es) removed due to binding VRF {}.".format(interface_name, vrf_name))
#
# 'unbind' subcommand
#

@vrf.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def unbind(ctx, interface_name):
    """Unbind the interface to VRF"""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("interface is None!")

    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")

    if is_interface_bind_to_vrf(config_db, interface_name) is False:
        return
    if table_name == "VLAN_SUB_INTERFACE":
        subintf_entry = config_db.get_entry(table_name, interface_name)
        if 'vrf_name' in subintf_entry:
            subintf_entry.pop('vrf_name')

    interface_ipaddresses = get_interface_ipaddresses(config_db, interface_name)
    for ipaddress in interface_ipaddresses:
        remove_router_interface_ip_address(config_db, interface_name, ipaddress)
    if table_name == "VLAN_SUB_INTERFACE":
        # First delete subinterface, once subinterface deletion successful,
        # recreate same with same config on default vrf
        if 'state_db' not in ctx.obj:
            if ctx.obj['namespace'] is DEFAULT_NAMESPACE:
                state_db = SonicV2Connector(use_unix_socket_path=True)
            else:
                state_db = SonicV2Connector(use_unix_socket_path=True, namespace=ctx.obj['namespace'])
            state_db.connect(state_db.STATE_DB, False)
        else:
            state_db = ctx.obj['state_db']

        config_db.set_entry(table_name, interface_name, None)
        _hash = '{}{}'.format('INTERFACE_TABLE|', interface_name)
        while state_db.exists(state_db.STATE_DB, _hash):
            time.sleep(0.01)
        state_db.close(state_db.STATE_DB)
        config_db.set_entry(table_name, interface_name, subintf_entry)
    else:
        config_db.set_entry(table_name, interface_name, None)

    click.echo("Interface {} IP disabled and address(es) removed due to unbinding VRF.".format(interface_name))
#
# 'ipv6' subgroup ('config interface ipv6 ...')
#

@interface.group()
@click.pass_context
def ipv6(ctx):
    """Enable or Disable IPv6 processing on interface"""
    pass

@ipv6.group('enable')
def enable():
    """Enable IPv6 processing on interface"""
    pass

@ipv6.group('disable')
def disable():
    """Disble IPv6 processing on interface"""
    pass

#
# 'config interface ipv6 enable use-link-local-only <interface-name>'
#

@enable.command('use-link-local-only')
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
def enable_use_link_local_only(ctx, interface_name):
    """Enable IPv6 link local address on interface"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {}
    ctx.obj['config_db'] = config_db
    db = ctx.obj["config_db"]

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name.startswith("Ethernet"):
        interface_type = "INTERFACE"
    elif interface_name.startswith("PortChannel"):
        interface_type = "PORTCHANNEL_INTERFACE"
    elif interface_name.startswith("Vlan"):
        interface_type = "VLAN_INTERFACE"
    else:
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan]")

    if (interface_type == "INTERFACE" ) or (interface_type == "PORTCHANNEL_INTERFACE"):
        if interface_name_is_valid(db, interface_name) is False:
            ctx.fail("Interface name %s is invalid. Please enter a valid interface name!!" %(interface_name))

    if (interface_type == "VLAN_INTERFACE"):
        if not clicommon.is_valid_vlan_interface(db, interface_name):
            ctx.fail("Interface name %s is invalid. Please enter a valid interface name!!" %(interface_name))

    portchannel_member_table = db.get_table('PORTCHANNEL_MEMBER')

    if interface_is_in_portchannel(portchannel_member_table, interface_name):
        ctx.fail("{} is configured as a member of portchannel. Cannot configure the IPv6 link local mode!"
                .format(interface_name))

    vlan_member_table = db.get_table('VLAN_MEMBER')

    if interface_is_in_vlan(vlan_member_table, interface_name):
        ctx.fail("{} is configured as a member of vlan. Cannot configure the IPv6 link local mode!"
                .format(interface_name))

    interface_dict = db.get_table(interface_type)
    set_ipv6_link_local_only_on_interface(db, interface_dict, interface_type, interface_name, "enable")

#
# 'config interface ipv6 disable use-link-local-only <interface-name>'
#

@disable.command('use-link-local-only')
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
def disable_use_link_local_only(ctx, interface_name):
    """Disable IPv6 link local address on interface"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {}
    ctx.obj['config_db'] = config_db
    db = ctx.obj["config_db"]

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    interface_type = ""
    if interface_name.startswith("Ethernet"):
        interface_type = "INTERFACE"
    elif interface_name.startswith("PortChannel"):
        interface_type = "PORTCHANNEL_INTERFACE"
    elif interface_name.startswith("Vlan"):
        interface_type = "VLAN_INTERFACE"
    else:
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan]")

    if (interface_type == "INTERFACE" ) or (interface_type == "PORTCHANNEL_INTERFACE"):
        if interface_name_is_valid(db, interface_name) is False:
            ctx.fail("Interface name %s is invalid. Please enter a valid interface name!!" %(interface_name))

    if (interface_type == "VLAN_INTERFACE"):
        if not clicommon.is_valid_vlan_interface(db, interface_name):
            ctx.fail("Interface name %s is invalid. Please enter a valid interface name!!" %(interface_name))

    portchannel_member_table = db.get_table('PORTCHANNEL_MEMBER')

    if interface_is_in_portchannel(portchannel_member_table, interface_name):
        ctx.fail("{} is configured as a member of portchannel. Cannot configure the IPv6 link local mode!"
                .format(interface_name))

    vlan_member_table = db.get_table('VLAN_MEMBER')
    if interface_is_in_vlan(vlan_member_table, interface_name):
        ctx.fail("{} is configured as a member of vlan. Cannot configure the IPv6 link local mode!"
                .format(interface_name))

    interface_dict = db.get_table(interface_type)
    set_ipv6_link_local_only_on_interface(db, interface_dict, interface_type, interface_name, "disable")

#
# 'vrf' group ('config vrf ...')
#

@config.group(cls=clicommon.AbbreviationGroup, name='vrf')
@click.pass_context
def vrf(ctx):
    """VRF-related configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {}
    ctx.obj['config_db'] = config_db

@vrf.command('add')
@click.argument('vrf_name', metavar='<vrf_name>', required=True)
@click.pass_context
def add_vrf(ctx, vrf_name):
    """Add vrf"""
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])
    if not vrf_name.startswith("Vrf") and not (vrf_name == 'mgmt') and not (vrf_name == 'management'):
        ctx.fail("'vrf_name' must begin with 'Vrf' or named 'mgmt'/'management' in case of ManagementVRF.")
    if len(vrf_name) > 15:
        ctx.fail("'vrf_name' is too long!")
    if is_vrf_exists(config_db, vrf_name):
        ctx.fail("VRF {} already exists!".format(vrf_name))
    elif (vrf_name == 'mgmt' or vrf_name == 'management'):
        vrf_add_management_vrf(config_db)
    else:
        try:
            config_db.set_entry('VRF', vrf_name, {"NULL": "NULL"})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@vrf.command('del')
@click.argument('vrf_name', metavar='<vrf_name>', required=True)
@click.pass_context
def del_vrf(ctx, vrf_name):
    """Del vrf"""
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])
    if not vrf_name.startswith("Vrf") and not (vrf_name == 'mgmt') and not (vrf_name == 'management'):
        ctx.fail("'vrf_name' must begin with 'Vrf' or named 'mgmt'/'management' in case of ManagementVRF.")
    if len(vrf_name) > 15:
        ctx.fail("'vrf_name' is too long!")
    syslog_table = config_db.get_table("SYSLOG_SERVER")
    syslog_vrf_dev = "mgmt" if vrf_name == "management" else vrf_name
    for syslog_entry, syslog_data in syslog_table.items():
        syslog_vrf = syslog_data.get("vrf")
        if syslog_vrf == syslog_vrf_dev:
            ctx.fail("Failed to remove VRF device: {} is in use by SYSLOG_SERVER|{}".format(syslog_vrf, syslog_entry))
    if not is_vrf_exists(config_db, vrf_name):
        ctx.fail("VRF {} does not exist!".format(vrf_name))
    elif (vrf_name == 'mgmt' or vrf_name == 'management'):
        vrf_delete_management_vrf(config_db)
    else:
        del_interface_bind_to_vrf(config_db, vrf_name)
        try:
            config_db.set_entry('VRF', vrf_name, None)
        except JsonPatchConflict as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        click.echo("VRF {} deleted and all associated IP addresses removed.".format(vrf_name))

@vrf.command('add_vrf_vni_map')
@click.argument('vrfname', metavar='<vrf-name>', required=True, type=str)
@click.argument('vni', metavar='<vni>', required=True)
@click.pass_context
def add_vrf_vni_map(ctx, vrfname, vni):
    config_db = ctx.obj['config_db']
    found = 0
    if vrfname not in config_db.get_table('VRF').keys():
        ctx.fail("vrf {} doesnt exists".format(vrfname))
    if not vni.isdigit():
        ctx.fail("Invalid VNI {}. Only valid VNI is accepted".format(vni))

    if clicommon.vni_id_is_valid(int(vni)) is False:
        ctx.fail("Invalid VNI {}. Valid range [1 to 16777215].".format(vni))

    vxlan_table = config_db.get_table('VXLAN_TUNNEL_MAP')
    vxlan_keys = vxlan_table.keys()
    if vxlan_keys is not None:
        for key in vxlan_keys:
            if (vxlan_table[key]['vni'] == vni):
                found = 1
                break

    if (found == 0):
        ctx.fail("VLAN VNI not mapped. Please create VLAN VNI map entry first")

    found = 0
    vrf_table = config_db.get_table('VRF')
    vrf_keys = vrf_table.keys()
    if vrf_keys is not None:
        for vrf_key in vrf_keys:
            if ('vni' in vrf_table[vrf_key] and vrf_table[vrf_key]['vni'] == vni):
                found = 1
                break

    if (found == 1):
        ctx.fail("VNI already mapped to vrf {}".format(vrf_key))

    config_db.mod_entry('VRF', vrfname, {"vni": vni})

@vrf.command('del_vrf_vni_map')
@click.argument('vrfname', metavar='<vrf-name>', required=True, type=str)
@click.pass_context
def del_vrf_vni_map(ctx, vrfname):
    config_db = ctx.obj['config_db']
    if vrfname not in config_db.get_table('VRF').keys():
        ctx.fail("vrf {} doesnt exists".format(vrfname))

    config_db.mod_entry('VRF', vrfname, {"vni": 0})

#
# 'route' group ('config route ...')
#

@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def route(ctx):
    """route-related configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {}
    ctx.obj['config_db'] = config_db

@route.command('add', context_settings={"ignore_unknown_options": True})
@click.argument('command_str', metavar='prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>', nargs=-1, type=click.Path())
@click.pass_context
def add_route(ctx, command_str):
    """Add route command"""
    config_db = ctx.obj['config_db']
    key, route = cli_sroute_to_config(ctx, command_str)

    # If defined intf name, check if it belongs to interface
    if 'ifname' in route:
        if (not route['ifname'] in config_db.get_keys('VLAN_INTERFACE') and
            not route['ifname'] in config_db.get_keys('INTERFACE') and
            not route['ifname'] in config_db.get_keys('PORTCHANNEL_INTERFACE') and
            not route['ifname'] in config_db.get_keys('VLAN_SUB_INTERFACE') and
            not route['ifname'] == 'null'):
            ctx.fail('interface {} doesn`t exist'.format(route['ifname']))

    entry_counter = 1
    if 'nexthop' in route:
        entry_counter = len(route['nexthop'].split(','))

    # Alignment in case the command contains several nexthop ip
    for i in range(entry_counter):
        if 'nexthop-vrf' in route:
            if i > 0:
                vrf = route['nexthop-vrf'].split(',')[0]
                route['nexthop-vrf'] += ',' + vrf
        else:
            route['nexthop-vrf'] = ''

        if not 'nexthop' in route:
            route['nexthop'] = ''

        if 'ifname' in route:
            if i > 0:
                route['ifname'] += ','
        else:
            route['ifname'] = ''

        # Set default values for distance and blackhole because the command doesn't have such an option
        if 'distance' in route:
            route['distance'] += ',0'
        else:
            route['distance'] = '0'

        if 'blackhole' in route:
            route['blackhole'] += ',false'
        else:
            # If the user configure with "ifname" as "null", set 'blackhole' attribute as true.
            if 'ifname' in route and route['ifname'] == 'null':
                route['blackhole'] = 'true'
            else:
                route['blackhole'] = 'false'

    # Check if exist entry with key
    keys = config_db.get_keys('STATIC_ROUTE')
    if tuple(key.split("|")) in keys:
        # If exist update current entry
        current_entry = config_db.get_entry('STATIC_ROUTE', key)

        for entry in ['nexthop', 'nexthop-vrf', 'ifname', 'distance', 'blackhole']:
            if not entry in current_entry:
                current_entry[entry] = ''
            if entry in route:
                current_entry[entry] += ',' + route[entry]
            else:
                current_entry[entry] += ','

        config_db.set_entry("STATIC_ROUTE", key, current_entry)
    else:
        config_db.set_entry("STATIC_ROUTE", key, route)

@route.command('del', context_settings={"ignore_unknown_options": True})
@click.argument('command_str', metavar='prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>', nargs=-1, type=click.Path())
@click.pass_context
def del_route(ctx, command_str):
    """Del route command"""
    config_db = ctx.obj['config_db']
    key, route = cli_sroute_to_config(ctx, command_str, strict_nh=False)
    keys = config_db.get_keys('STATIC_ROUTE')
    prefix_tuple = tuple(key.split('|'))
    if not tuple(key.split("|")) in keys and not prefix_tuple in keys:
        ctx.fail('Route {} doesnt exist'.format(key))
    else:
        # If not defined nexthop or intf name remove entire route
        if not 'nexthop' in route and not 'ifname' in route:
            config_db.set_entry("STATIC_ROUTE", key, None)
            return

        current_entry = config_db.get_entry('STATIC_ROUTE', key)

        nh = ['']
        nh_vrf = ['']
        ifname = ['']
        distance = ['']
        blackhole = ['']
        if 'nexthop' in current_entry:
            nh = current_entry['nexthop'].split(',')
        if 'nexthop-vrf' in current_entry:
            nh_vrf = current_entry['nexthop-vrf'].split(',')
        if 'ifname' in current_entry:
            ifname = current_entry['ifname'].split(',')
        if 'distance' in current_entry:
            distance = current_entry['distance'].split(',')
        if 'blackhole' in current_entry:
            blackhole = current_entry['blackhole'].split(',')

        # Zip data from config_db into tuples
        # {'nexthop': '10.0.0.2,20.0.0.2', 'vrf-nexthop': ',Vrf-RED', 'ifname': ','}
        # [('10.0.0.2', '', ''), ('20.0.0.2', 'Vrf-RED', '')]
        nh_zip = list(itertools.zip_longest(nh, nh_vrf, ifname, fillvalue=''))
        cli_tuple = ()

        # Create tuple from CLI argument
        # config route add prefix 1.4.3.4/32 nexthop vrf Vrf-RED 20.0.0.2
        # ('20.0.0.2', 'Vrf-RED', '')
        for entry in ['nexthop', 'nexthop-vrf', 'ifname']:
            if entry in route:
                cli_tuple += (route[entry],)
            else:
                cli_tuple += ('',)

        if cli_tuple in nh_zip:
            # If cli tuple is in config_db find its index and delete from lists
            idx = nh_zip.index(cli_tuple)
            if len(nh) - 1 >= idx:
                del nh[idx]
            if len(nh_vrf) - 1 >= idx:
                del nh_vrf[idx]
            if len(ifname) - 1 >= idx:
                del ifname[idx]
            if len(distance) - 1 >= idx:
                del distance[idx]
            if len(blackhole) - 1 >= idx:
                del blackhole[idx]
        else:
            ctx.fail('Not found {} in {}'.format(cli_tuple, key))

        if (len(nh) == 0 or (len(nh) == 1 and nh[0] == '')) and \
            (len(ifname) == 0 or (len(ifname) == 1 and ifname[0] == '')):
            # If there are no nexthop and ifname fields in the current record, delete it
            config_db.set_entry("STATIC_ROUTE", key, None)
        else:
            # Otherwise it still has ECMP nexthop or ifname fields, so compose it from the lists into db
            current_entry['nexthop'] = ','.join((str(e)) for e in nh)
            current_entry['nexthop-vrf'] = ','.join((str(e)) for e in nh_vrf)
            current_entry['ifname'] = ','.join((str(e)) for e in ifname)
            current_entry['distance'] = ','.join((str(e)) for e in distance)
            current_entry['blackhole'] = ','.join((str(e)) for e in blackhole)
            config_db.set_entry("STATIC_ROUTE", key, current_entry)

#
# 'acl' group ('config acl ...')
#

@config.group(cls=clicommon.AbbreviationGroup)
def acl():
    """ACL-related configuration tasks"""
    pass

#
# 'add' subgroup ('config acl add ...')
#

@acl.group(cls=clicommon.AbbreviationGroup)
def add():
    """
    Add ACL configuration.
    """
    pass


def get_acl_bound_ports():
    config_db = ConfigDBConnector()
    config_db.connect()

    ports = set()
    portchannel_members = set()

    portchannel_member_dict = config_db.get_table("PORTCHANNEL_MEMBER")
    for key in portchannel_member_dict:
        ports.add(key[0])
        portchannel_members.add(key[1])

    port_dict = config_db.get_table("PORT")
    for key in port_dict:
        if key not in portchannel_members:
            ports.add(key)

    return list(ports)


def expand_vlan_ports(port_name):
    """
    Expands a given VLAN interface into its member ports.

    If the provided interface is a VLAN, then this method will return its member ports.

    If the provided interface is not a VLAN, then this method will return a list with only
    the provided interface in it.
    """
    config_db = ConfigDBConnector()
    config_db.connect()

    if port_name not in config_db.get_keys("VLAN"):
        return [port_name]

    vlan_members = config_db.get_keys("VLAN_MEMBER")

    members = [member for vlan, member in vlan_members if port_name == vlan]

    if not members:
        raise ValueError("Cannot bind empty VLAN {}".format(port_name))

    return members


def parse_acl_table_info(table_name, table_type, description, ports, stage):
    table_info = {"type": table_type}

    if description:
        table_info["policy_desc"] = description
    else:
        table_info["policy_desc"] = table_name

    if not ports and ports != None:
        raise ValueError("Cannot bind empty list of ports")

    port_list = []
    valid_acl_ports = get_acl_bound_ports()
    if ports:
        for port in ports.split(","):
            port_list += expand_vlan_ports(port)
        port_list = list(set(port_list))  # convert to set first to remove duplicate ifaces
    else:
        port_list = valid_acl_ports

    for port in port_list:
        if port not in valid_acl_ports:
            raise ValueError("Cannot bind ACL to specified port {}".format(port))

    table_info["ports"] = port_list

    table_info["stage"] = stage

    return table_info

#
# 'table' subcommand ('config acl add table ...')
#

@add.command()
@click.argument("table_name", metavar="<table_name>")
@click.argument("table_type", metavar="<table_type>")
@click.option("-d", "--description")
@click.option("-p", "--ports")
@click.option("-s", "--stage", type=click.Choice(["ingress", "egress"]), default="ingress")
@click.pass_context
def table(ctx, table_name, table_type, description, ports, stage):
    """
    Add ACL table
    """
    config_db = ConfigDBConnector()
    config_db.connect()

    try:
        table_info = parse_acl_table_info(table_name, table_type, description, ports, stage)
    except ValueError as e:
        ctx.fail("Failed to parse ACL table config: exception={}".format(e))

    config_db.set_entry("ACL_TABLE", table_name, table_info)

#
# 'remove' subgroup ('config acl remove ...')
#

@acl.group(cls=clicommon.AbbreviationGroup)
def remove():
    """
    Remove ACL configuration.
    """
    pass

#
# 'table' subcommand ('config acl remove table ...')
#

@remove.command()
@click.argument("table_name", metavar="<table_name>")
def table(table_name):
    """
    Remove ACL table
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    config_db.set_entry("ACL_TABLE", table_name, None)


#
# 'acl update' group
#

@acl.group(cls=clicommon.AbbreviationGroup)
def update():
    """ACL-related configuration tasks"""
    pass


#
# 'full' subcommand
#

@update.command()
@click.argument('file_name', required=True)
def full(file_name):
    """Full update of ACL rules configuration."""
    log.log_info("'acl update full {}' executing...".format(file_name))
    command = "acl-loader update full {}".format(file_name)
    clicommon.run_command(command)


#
# 'incremental' subcommand
#

@update.command()
@click.argument('file_name', required=True)
def incremental(file_name):
    """Incremental update of ACL rule configuration."""
    log.log_info("'acl update incremental {}' executing...".format(file_name))
    command = "acl-loader update incremental {}".format(file_name)
    clicommon.run_command(command)


#
# 'dropcounters' group ('config dropcounters ...')
#

@config.group(cls=clicommon.AbbreviationGroup)
def dropcounters():
    """Drop counter related configuration tasks"""
    pass


#
# 'install' subcommand ('config dropcounters install')
#
@dropcounters.command()
@click.argument("counter_name", type=str, required=True)
@click.argument("counter_type", type=str, required=True)
@click.argument("reasons",      type=str, required=True)
@click.option("-a", "--alias", type=str, help="Alias for this counter")
@click.option("-g", "--group", type=str, help="Group for this counter")
@click.option("-d", "--desc",  type=str, help="Description for this counter")
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def install(counter_name, alias, group, counter_type, desc, reasons, verbose):
    """Install a new drop counter"""
    command = "dropconfig -c install -n '{}' -t '{}' -r '{}'".format(counter_name, counter_type, reasons)
    if alias:
        command += " -a '{}'".format(alias)
    if group:
        command += " -g '{}'".format(group)
    if desc:
        command += " -d '{}'".format(desc)

    clicommon.run_command(command, display_cmd=verbose)


#
# 'delete' subcommand ('config dropcounters delete')
#
@dropcounters.command()
@click.argument("counter_name", type=str, required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def delete(counter_name, verbose):
    """Delete an existing drop counter"""
    command = "dropconfig -c uninstall -n {}".format(counter_name)
    clicommon.run_command(command, display_cmd=verbose)


#
# 'add_reasons' subcommand ('config dropcounters add_reasons')
#
@dropcounters.command('add-reasons')
@click.argument("counter_name", type=str, required=True)
@click.argument("reasons",      type=str, required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def add_reasons(counter_name, reasons, verbose):
    """Add reasons to an existing drop counter"""
    command = "dropconfig -c add -n {} -r {}".format(counter_name, reasons)
    clicommon.run_command(command, display_cmd=verbose)


#
# 'remove_reasons' subcommand ('config dropcounters remove_reasons')
#
@dropcounters.command('remove-reasons')
@click.argument("counter_name", type=str, required=True)
@click.argument("reasons",      type=str, required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def remove_reasons(counter_name, reasons, verbose):
    """Remove reasons from an existing drop counter"""
    command = "dropconfig -c remove -n {} -r {}".format(counter_name, reasons)
    clicommon.run_command(command, display_cmd=verbose)


#
# 'ecn' command ('config ecn ...')
#
@config.command()
@click.option('-profile', metavar='<profile_name>', type=str, required=True, help="Profile name")
@click.option('-rmax', metavar='<red threshold max>', type=int, help="Set red max threshold")
@click.option('-rmin', metavar='<red threshold min>', type=int, help="Set red min threshold")
@click.option('-ymax', metavar='<yellow threshold max>', type=int, help="Set yellow max threshold")
@click.option('-ymin', metavar='<yellow threshold min>', type=int, help="Set yellow min threshold")
@click.option('-gmax', metavar='<green threshold max>', type=int, help="Set green max threshold")
@click.option('-gmin', metavar='<green threshold min>', type=int, help="Set green min threshold")
@click.option('-rdrop', metavar='<red drop probability>', type=click.IntRange(0, 100), help="Set red drop probability")
@click.option('-ydrop', metavar='<yellow drop probability>', type=click.IntRange(0, 100), help="Set yellow drop probability")
@click.option('-gdrop', metavar='<green drop probability>', type=click.IntRange(0, 100), help="Set green drop probability")
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def ecn(profile, rmax, rmin, ymax, ymin, gmax, gmin, rdrop, ydrop, gdrop, verbose):
    """ECN-related configuration tasks"""
    log.log_info("'ecn -profile {}' executing...".format(profile))
    command = "ecnconfig -p %s" % profile
    if rmax is not None: command += " -rmax %d" % rmax
    if rmin is not None: command += " -rmin %d" % rmin
    if ymax is not None: command += " -ymax %d" % ymax
    if ymin is not None: command += " -ymin %d" % ymin
    if gmax is not None: command += " -gmax %d" % gmax
    if gmin is not None: command += " -gmin %d" % gmin
    if rdrop is not None: command += " -rdrop %d" % rdrop
    if ydrop is not None: command += " -ydrop %d" % ydrop
    if gdrop is not None: command += " -gdrop %d" % gdrop
    if verbose: command += " -vv"
    clicommon.run_command(command, display_cmd=verbose)


#
# 'pfc' group ('config interface pfc ...')
#

@interface.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def pfc(ctx):
    """Set PFC configuration."""
    pass


#
# 'pfc asymmetric' ('config interface pfc asymmetric ...')
#

@pfc.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('status', type=click.Choice(['on', 'off']))
@click.pass_context
def asymmetric(ctx, interface_name, status):
    """Set asymmetric PFC configuration."""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    clicommon.run_command("pfc config asymmetric {0} {1}".format(status, interface_name))

#
# 'pfc priority' command ('config interface pfc priority ...')
#

@pfc.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('priority', type=click.Choice([str(x) for x in range(8)]))
@click.argument('status', type=click.Choice(['on', 'off']))
@click.pass_context
def priority(ctx, interface_name, priority, status):
    """Set PFC priority configuration."""
    # Get the config_db connector
    config_db = ctx.obj['config_db']

    if clicommon.get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(config_db, interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    clicommon.run_command("pfc config priority {0} {1} {2}".format(status, interface_name, priority))

#
# 'buffer' group ('config buffer ...')
#

@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def buffer(ctx):
    """Configure buffer_profile"""
    config_db = ConfigDBConnector()
    config_db.connect()

    if not is_dynamic_buffer_enabled(config_db):
        ctx.fail("This command can only be supported on a system with dynamic buffer enabled")


@buffer.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def profile(ctx):
    """Configure buffer profile"""
    pass


@profile.command('add')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--xon', metavar='<xon>', type=int, help="Set xon threshold")
@click.option('--xoff', metavar='<xoff>', type=int, help="Set xoff threshold")
@click.option('--size', metavar='<size>', type=int, help="Set reserved size size")
@click.option('--dynamic_th', metavar='<dynamic_th>', type=str, help="Set dynamic threshold")
@click.option('--pool', metavar='<pool>', type=str, help="Buffer pool")
@clicommon.pass_db
def add_profile(db, profile, xon, xoff, size, dynamic_th, pool):
    """Add or modify a buffer profile"""
    config_db = db.cfgdb
    ctx = click.get_current_context()

    profile_entry = config_db.get_entry('BUFFER_PROFILE', profile)
    if profile_entry:
        ctx.fail("Profile {} already exist".format(profile))

    update_profile(ctx, config_db, profile, xon, xoff, size, dynamic_th, pool)


@profile.command('set')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--xon', metavar='<xon>', type=int, help="Set xon threshold")
@click.option('--xoff', metavar='<xoff>', type=int, help="Set xoff threshold")
@click.option('--size', metavar='<size>', type=int, help="Set reserved size size")
@click.option('--dynamic_th', metavar='<dynamic_th>', type=str, help="Set dynamic threshold")
@click.option('--pool', metavar='<pool>', type=str, help="Buffer pool")
@clicommon.pass_db
def set_profile(db, profile, xon, xoff, size, dynamic_th, pool):
    """Add or modify a buffer profile"""
    config_db = db.cfgdb
    ctx = click.get_current_context()

    profile_entry = config_db.get_entry('BUFFER_PROFILE', profile)
    if not profile_entry:
        ctx.fail("Profile {} doesn't exist".format(profile))

    if not 'xoff' in profile_entry.keys() and xoff:
        ctx.fail("Can't change profile {} from dynamically calculating headroom to non-dynamically one".format(profile))

    update_profile(ctx, config_db, profile, xon, xoff, size, dynamic_th, pool, profile_entry)


def _is_shared_headroom_pool_enabled(ctx, config_db):
    ingress_lossless_pool = config_db.get_entry('BUFFER_POOL', 'ingress_lossless_pool')
    if 'xoff' in ingress_lossless_pool:
        return True

    default_lossless_param_table = config_db.get_table('DEFAULT_LOSSLESS_BUFFER_PARAMETER')
    if not default_lossless_param_table:
        ctx.fail("Dynamic buffer calculation is enabled while no entry found in DEFAULT_LOSSLESS_BUFFER_PARAMETER table")
    default_lossless_param = list(default_lossless_param_table.values())[0]
    over_subscribe_ratio = default_lossless_param.get('over_subscribe_ratio')
    if over_subscribe_ratio and over_subscribe_ratio != '0':
        return True

    return False


def update_profile(ctx, config_db, profile_name, xon, xoff, size, dynamic_th, pool, profile_entry = None):
    config_db = ValidatedConfigDBConnector(config_db)
    params = {}
    if profile_entry:
        params = profile_entry

    shp_enabled = _is_shared_headroom_pool_enabled(ctx, config_db)

    if not pool:
        pool = 'ingress_lossless_pool'
    params['pool'] = pool
    if not config_db.get_entry('BUFFER_POOL', pool):
        ctx.fail("Pool {} doesn't exist".format(pool))

    if xon:
        params['xon'] = xon
    else:
        xon = params.get('xon')

    if xoff:
        params['xoff'] = xoff
    else:
        xoff = params.get('xoff')

    if size:
        params['size'] = size
    else:
        size = params.get('size')

    dynamic_calculate = False if (xon or xoff or size) else True

    if dynamic_calculate:
        params['headroom_type'] = 'dynamic'
        if not dynamic_th:
            ctx.fail("Either size information (xon, xoff, size) or dynamic_th needs to be provided")
        params['dynamic_th'] = dynamic_th
    else:
        if not xon:
            ctx.fail("Xon is mandatory for non-dynamic profile")

        if not xoff:
            if shp_enabled:
                ctx.fail("Shared headroom pool is enabled, xoff is mandatory for non-dynamic profile")
            elif not size:
                ctx.fail("Neither xoff nor size is provided")
            else:
                xoff_number = int(size) - int(xon)
                if xoff_number <= 0:
                    ctx.fail("The xoff must be greater than 0 while we got {} (calculated by: size {} - xon {})".format(xoff_number, size, xon))
                params['xoff'] = str(xoff_number)

        if not size:
            if shp_enabled:
                size = int(xon)
            else:
                size = int(xon) + int(xoff)
            params['size'] = size

        if dynamic_th:
            params['dynamic_th'] = dynamic_th
        elif not params.get('dynamic_th'):
            # Fetch all the keys of default_lossless_buffer_parameter table
            # and then get the default_dynamic_th from that entry (should be only one)
            keys = config_db.get_keys('DEFAULT_LOSSLESS_BUFFER_PARAMETER')
            if len(keys) != 1:
                ctx.fail("Multiple entries are found in DEFAULT_LOSSLESS_BUFFER_PARAMETER while no dynamic_th specified")

            default_lossless_param = config_db.get_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', keys[0])
            if 'default_dynamic_th' in default_lossless_param:
                params['dynamic_th'] = default_lossless_param['default_dynamic_th']
            else:
                ctx.fail("No dynamic_th defined in DEFAULT_LOSSLESS_BUFFER_PARAMETER")

    try:
        config_db.set_entry("BUFFER_PROFILE", (profile_name), params)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

@profile.command('remove')
@click.argument('profile', metavar='<profile>', required=True)
@clicommon.pass_db
def remove_profile(db, profile):
    """Delete a buffer profile"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    existing_pgs = config_db.get_table("BUFFER_PG")
    for k, v in existing_pgs.items():
        port, pg = k
        referenced_profile = v.get('profile')
        if referenced_profile and referenced_profile == profile:
            ctx.fail("Profile {} is referenced by {}|{} and can't be removed".format(profile, port, pg))

    entry = config_db.get_entry("BUFFER_PROFILE", profile)
    if entry:
        try:
            config_db.set_entry("BUFFER_PROFILE", profile, None)
        except JsonPatchConflict as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        ctx.fail("Profile {} doesn't exist".format(profile))

@buffer.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def shared_headroom_pool(ctx):
    """Configure buffer shared headroom pool"""
    pass


@shared_headroom_pool.command()
@click.argument('ratio', metavar='<ratio>', type=int, required=True)
@clicommon.pass_db
def over_subscribe_ratio(db, ratio):
    """Configure over subscribe ratio"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    port_number = len(config_db.get_table('PORT'))
    if ratio < 0 or ratio > port_number:
        ctx.fail("Invalid over-subscribe-ratio value {}. It should be in range [0, {}]".format(ratio, port_number))

    default_lossless_param = config_db.get_table("DEFAULT_LOSSLESS_BUFFER_PARAMETER")
    first_item = True
    for k, v in default_lossless_param.items():
        if not first_item:
            ctx.fail("More than one item in DEFAULT_LOSSLESS_BUFFER_PARAMETER table. Only the first one is updated")
        first_item = False

        if ratio == 0:
            if "over_subscribe_ratio" in v.keys():
                v.pop("over_subscribe_ratio")
        else:
            v["over_subscribe_ratio"] = ratio

        try:
            config_db.set_entry("DEFAULT_LOSSLESS_BUFFER_PARAMETER", k, v)
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))


@shared_headroom_pool.command()
@click.argument('size', metavar='<size>', type=int, required=True)
@clicommon.pass_db
def size(db, size):
    """Configure shared headroom pool size"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    state_db = db.db
    ctx = click.get_current_context()

    _hash = 'BUFFER_MAX_PARAM_TABLE|global'
    buffer_max_params = state_db.get_all(state_db.STATE_DB, _hash)
    if buffer_max_params:
        mmu_size = buffer_max_params.get('mmu_size')
        if mmu_size and int(mmu_size) < size:
            ctx.fail("Shared headroom pool must be less than mmu size ({})".format(mmu_size))

    ingress_lossless_pool = config_db.get_entry("BUFFER_POOL", "ingress_lossless_pool")

    if size == 0:
        if "xoff" in ingress_lossless_pool:
            ingress_lossless_pool.pop("xoff")
    else:
        ingress_lossless_pool["xoff"] = size

    try:
        config_db.set_entry("BUFFER_POOL", "ingress_lossless_pool", ingress_lossless_pool)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


#
# 'platform' group ('config platform ...')
#

@config.group(cls=clicommon.AbbreviationGroup)
def platform():
    """Platform-related configuration tasks"""

# 'firmware' subgroup ("config platform firmware ...")
@platform.group(cls=clicommon.AbbreviationGroup)
def firmware():
    """Firmware configuration tasks"""
    pass

# 'install' subcommand ("config platform firmware install")
@firmware.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True
    ),
    add_help_option=False
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def install(args):
    """Install platform firmware"""
    cmd = ["fwutil", "install"] + list(args)

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

# 'update' subcommand ("config platform firmware update")
@firmware.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True
    ),
    add_help_option=False
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def update(args):
    """Update platform firmware"""
    cmd = ["fwutil", "update"] + list(args)

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

#
# 'watermark' group ("show watermark telemetry interval")
#

@config.group(cls=clicommon.AbbreviationGroup)
def watermark():
    """Configure watermark """
    pass

@watermark.group(cls=clicommon.AbbreviationGroup)
def telemetry():
    """Configure watermark telemetry"""
    pass

@telemetry.command()
@click.argument('interval', required=True)
def interval(interval):
    """Configure watermark telemetry interval"""
    command = 'watermarkcfg --config-interval ' + interval
    clicommon.run_command(command)


#
# 'interface_naming_mode' subgroup ('config interface_naming_mode ...')
#

@config.group(cls=clicommon.AbbreviationGroup, name='interface_naming_mode')
def interface_naming_mode():
    """Modify interface naming mode for interacting with SONiC CLI"""
    pass

@interface_naming_mode.command('default')
def naming_mode_default():
    """Set CLI interface naming mode to DEFAULT (SONiC port name)"""
    set_interface_naming_mode('default')

@interface_naming_mode.command('alias')
def naming_mode_alias():
    """Set CLI interface naming mode to ALIAS (Vendor port alias)"""
    set_interface_naming_mode('alias')

@interface.group('storm-control')
@click.pass_context
def storm_control(ctx):
    """ Configure storm-control"""
    pass

@storm_control.command('add')
@click.argument('port_name',metavar='<port_name>', required=True)
@click.argument('storm_type',metavar='<storm_type>', required=True, type=click.Choice(["broadcast", "unknown-unicast", "unknown-multicast"]))
@click.argument('kbps',metavar='<kbps_value>', required=True, type=click.IntRange(0,100000000))
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
@click.pass_context
def add_interface_storm(ctx, port_name,storm_type, kbps, namespace):
    if storm_control_set_entry(port_name, kbps, storm_type, namespace) is False:
        ctx.fail("Unable to add {} storm-control to interface {}".format(storm_type, port_name))

@storm_control.command('del')
@click.argument('port_name',metavar='<port_name>', required=True)
@click.argument('storm_type',metavar='<storm_type>', required=True, type=click.Choice(["broadcast", "unknown-unicast", "unknown-multicast"]))
@click.option('--namespace',
              '-n',
              'namespace',
              default=None,
              type=str,
              show_default=True,
              help='Namespace name or all',
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
@click.pass_context
def del_interface_storm(ctx,port_name,storm_type, namespace):
    if storm_control_delete_entry(port_name, storm_type) is False:
        ctx.fail("Unable to delete {} storm-control from interface {}".format(storm_type, port_name))

def is_loopback_name_valid(loopback_name):
    """Loopback name validation
    """

    if loopback_name[:CFG_LOOPBACK_PREFIX_LEN] != CFG_LOOPBACK_PREFIX :
        return False
    if (loopback_name[CFG_LOOPBACK_PREFIX_LEN:].isdigit() is False or
          int(loopback_name[CFG_LOOPBACK_PREFIX_LEN:]) > CFG_LOOPBACK_ID_MAX_VAL) :
        return False
    if len(loopback_name) > CFG_LOOPBACK_NAME_TOTAL_LEN_MAX:
        return False
    return True

#
# 'loopback' group ('config loopback ...')
#
@config.group()
@click.pass_context
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def loopback(ctx, redis_unix_socket_path):
    """Loopback-related configuration tasks"""
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path
    config_db = ConfigDBConnector(**kwargs)
    config_db.connect(wait_for_init=False)
    ctx.obj = {'db': config_db}

@loopback.command('add')
@click.argument('loopback_name', metavar='<loopback_name>', required=True)
@click.pass_context
def add_loopback(ctx, loopback_name):
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if is_loopback_name_valid(loopback_name) is False:
            ctx.fail("{} is invalid, name should have prefix '{}' and suffix '{}' "
                    .format(loopback_name, CFG_LOOPBACK_PREFIX, CFG_LOOPBACK_NO))

        lo_intfs = [k for k, v in config_db.get_table('LOOPBACK_INTERFACE').items() if type(k) != tuple]
        if loopback_name in lo_intfs:
            ctx.fail("{} already exists".format(loopback_name)) # TODO: MISSING CONSTRAINT IN YANG VALIDATION

    try:
        config_db.set_entry('LOOPBACK_INTERFACE', loopback_name, {"NULL" : "NULL"})
    except ValueError:
        ctx.fail("{} is invalid, name should have prefix '{}' and suffix '{}' ".format(loopback_name, CFG_LOOPBACK_PREFIX, CFG_LOOPBACK_NO))

@loopback.command('del')
@click.argument('loopback_name', metavar='<loopback_name>', required=True)
@click.pass_context
def del_loopback(ctx, loopback_name):
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    lo_config_db = config_db.get_table('LOOPBACK_INTERFACE')

    if ADHOC_VALIDATION:
        if is_loopback_name_valid(loopback_name) is False:
            ctx.fail("{} is invalid, name should have prefix '{}' and suffix '{}' "
                    .format(loopback_name, CFG_LOOPBACK_PREFIX, CFG_LOOPBACK_NO))
        lo_intfs = [k for k, v in lo_config_db.items() if type(k) != tuple]
        if loopback_name not in lo_intfs:
            ctx.fail("{} does not exist".format(loopback_name))

    ips = [ k[1] for k in lo_config_db if type(k) == tuple and k[0] == loopback_name ]
    for ip in ips:
        config_db.set_entry('LOOPBACK_INTERFACE', (loopback_name, ip), None)

    try:
        config_db.set_entry('LOOPBACK_INTERFACE', loopback_name, None)
    except JsonPatchConflict:
        ctx.fail("{} does not exist".format(loopback_name))


@config.group(cls=clicommon.AbbreviationGroup)
def ztp():
    """ Configure Zero Touch Provisioning """
    if os.path.isfile('/usr/bin/ztp') is False:
        sys.exit("ZTP feature unavailable in this image version")

    if os.geteuid() != 0:
        sys.exit("Root privileges are required for this operation")

@ztp.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='ZTP will be restarted. You may lose switch data and connectivity, continue?')
@click.argument('run', required=False, type=click.Choice(["run"]))
def run(run):
    """Restart ZTP of the device."""
    command = "ztp run -y"
    clicommon.run_command(command, display_cmd=True)

@ztp.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Active ZTP session will be stopped and disabled, continue?')
@click.argument('disable', required=False, type=click.Choice(["disable"]))
def disable(disable):
    """Administratively Disable ZTP."""
    command = "ztp disable -y"
    clicommon.run_command(command, display_cmd=True)

@ztp.command()
@click.argument('enable', required=False, type=click.Choice(["enable"]))
def enable(enable):
    """Administratively Enable ZTP."""
    command = "ztp enable"
    clicommon.run_command(command, display_cmd=True)

#
# 'ntp' group ('config ntp ...')
#
@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def ntp(ctx):
    """NTP server configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

@ntp.command('add')
@click.argument('ntp_ip_address', metavar='<ntp_ip_address>', required=True)
@click.pass_context
def add_ntp_server(ctx, ntp_ip_address):
    """ Add NTP server IP """
    if ADHOC_VALIDATION:
        if not clicommon.is_ipaddress(ntp_ip_address):
            ctx.fail('Invalid IP address')
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    ntp_servers = db.get_table("NTP_SERVER")
    if ntp_ip_address in ntp_servers:
        click.echo("NTP server {} is already configured".format(ntp_ip_address))
        return
    else:
        try:
            db.set_entry('NTP_SERVER', ntp_ip_address, {'NULL': 'NULL'})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        click.echo("NTP server {} added to configuration".format(ntp_ip_address))
        try:
            click.echo("Restarting ntp-config service...")
            clicommon.run_command("systemctl restart ntp-config", display_cmd=False)
        except SystemExit as e:
            ctx.fail("Restart service ntp-config failed with error {}".format(e))

@ntp.command('del')
@click.argument('ntp_ip_address', metavar='<ntp_ip_address>', required=True)
@click.pass_context
def del_ntp_server(ctx, ntp_ip_address):
    """ Delete NTP server IP """
    if ADHOC_VALIDATION:
        if not clicommon.is_ipaddress(ntp_ip_address):
            ctx.fail('Invalid IP address')
    db = ValidatedConfigDBConnector(ctx.obj['db'])
    ntp_servers = db.get_table("NTP_SERVER")
    if ntp_ip_address in ntp_servers:
        try:
            db.set_entry('NTP_SERVER', '{}'.format(ntp_ip_address), None)
        except JsonPatchConflict as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        click.echo("NTP server {} removed from configuration".format(ntp_ip_address))
    else:
        ctx.fail("NTP server {} is not configured.".format(ntp_ip_address))
    try:
        click.echo("Restarting ntp-config service...")
        clicommon.run_command("systemctl restart ntp-config", display_cmd=False)
    except SystemExit as e:
        ctx.fail("Restart service ntp-config failed with error {}".format(e))

#
# 'sflow' group ('config sflow ...')
#
@config.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def sflow(ctx):
    """sFlow-related configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

#
# 'sflow' command ('config sflow enable')
#
@sflow.command()
@click.pass_context
def enable(ctx):
    """Enable sFlow"""
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'up'}}
    else:
        sflow_tbl['global']['admin_state'] = 'up'

    try:
        config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    try:
        proc = subprocess.Popen(['systemctl', 'is-active', 'sflow'], text=True, stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
    except SystemExit as e:
        ctx.fail("Unable to check sflow status {}".format(e))

    if out != "active":
        log.log_info("sflow service is not enabled. Starting sflow docker...")
        clicommon.run_command("sudo systemctl enable sflow")
        clicommon.run_command("sudo systemctl start sflow")

#
# 'sflow' command ('config sflow disable')
#
@sflow.command()
@click.pass_context
def disable(ctx):
    """Disable sFlow"""
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}
    else:
        sflow_tbl['global']['admin_state'] = 'down'

    try:
        config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'sflow' command ('config sflow polling-interval ...')
#
@sflow.command('polling-interval')
@click.argument('interval',  metavar='<polling_interval>', required=True,
                type=int)
@click.pass_context
def polling_int(ctx, interval):
    """Set polling-interval for counter-sampling (0 to disable)"""
    if ADHOC_VALIDATION:
        if interval not in range(5, 301) and interval != 0:
            click.echo("Polling interval must be between 5-300 (0 to disable)")

    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}

    sflow_tbl['global']['polling_interval'] = interval
    try:
        config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

def is_valid_sample_rate(rate):
    return rate.isdigit() and int(rate) in range(256, 8388608 + 1)


#
# 'sflow interface' group
#
@sflow.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def interface(ctx):
    """Configure sFlow settings for an interface"""
    pass

#
# 'sflow' command ('config sflow interface enable  ...')
#
@interface.command()
@click.argument('ifname', metavar='<interface_name>', required=True, type=str)
@click.pass_context
def enable(ctx, ifname):
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if not interface_name_is_valid(config_db, ifname) and ifname != 'all':
            click.echo("Invalid interface name")
            return

    intf_dict = config_db.get_table('SFLOW_SESSION')

    if intf_dict and ifname in intf_dict:
        intf_dict[ifname]['admin_state'] = 'up'
        try:
            config_db.mod_entry('SFLOW_SESSION', ifname, intf_dict[ifname])
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        try:
            config_db.mod_entry('SFLOW_SESSION', ifname, {'admin_state': 'up'})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'sflow' command ('config sflow interface disable  ...')
#
@interface.command()
@click.argument('ifname', metavar='<interface_name>', required=True, type=str)
@click.pass_context
def disable(ctx, ifname):
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if not interface_name_is_valid(config_db, ifname) and ifname != 'all':
            click.echo("Invalid interface name")
            return

    intf_dict = config_db.get_table('SFLOW_SESSION')

    if intf_dict and ifname in intf_dict:
        intf_dict[ifname]['admin_state'] = 'down'
        try:
            config_db.mod_entry('SFLOW_SESSION', ifname, intf_dict[ifname])
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        try:
            config_db.mod_entry('SFLOW_SESSION', ifname,
                                {'admin_state': 'down'})
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'sflow' command ('config sflow interface sample-rate  ...')
#
@interface.command('sample-rate')
@click.argument('ifname', metavar='<interface_name>', required=True, type=str)
@click.argument('rate', metavar='<sample_rate>', required=True, type=str)
@click.pass_context
def sample_rate(ctx, ifname, rate):
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        if not interface_name_is_valid(config_db, ifname) and ifname != 'all':
            click.echo('Invalid interface name')
            return
        if not is_valid_sample_rate(rate) and rate != 'default':
            click.echo('Error: Sample rate must be between 256 and 8388608 or default')
            return

    sess_dict = config_db.get_table('SFLOW_SESSION')

    if sess_dict and ifname in sess_dict.keys():
        if rate == 'default':
            if 'sample_rate' not in sess_dict[ifname]:
                return
            del sess_dict[ifname]['sample_rate']
            try:
                config_db.set_entry('SFLOW_SESSION', ifname, sess_dict[ifname])
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
            return
        sess_dict[ifname]['sample_rate'] = rate
        try:
            config_db.mod_entry('SFLOW_SESSION', ifname, sess_dict[ifname])
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        if rate != 'default':
            try:
                config_db.mod_entry('SFLOW_SESSION', ifname, {'sample_rate': rate})
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))


#
# 'sflow collector' group
#
@sflow.group(cls=clicommon.AbbreviationGroup)
@click.pass_context
def collector(ctx):
    """Add/Delete a sFlow collector"""
    pass

def is_valid_collector_info(name, ip, port, vrf_name):
    if len(name) > 16:
        click.echo("Collector name must not exceed 16 characters")
        return False

    if port not in range(0, 65535 + 1):
        click.echo("Collector port number must be between 0 and 65535")
        return False

    if not clicommon.is_ipaddress(ip):
        click.echo("Invalid IP address")
        return False

    if vrf_name != 'default' and vrf_name != 'mgmt':
        click.echo("Only 'default' and 'mgmt' VRF are supported")
        return False

    return True

#
# 'sflow' command ('config sflow collector add ...')
#
@collector.command()
@click.option('--port', required=False, type=int, default=6343,
              help='Collector port number')
@click.option('--vrf', required=False, type=str, default='default',
              help='Collector VRF')
@click.argument('name', metavar='<collector_name>', required=True)
@click.argument('ipaddr', metavar='<IPv4/v6_address>', required=True)
@click.pass_context
def add(ctx, name, ipaddr, port, vrf):
    """Add a sFlow collector"""
    ipaddr = ipaddr.lower()

    if not is_valid_collector_info(name, ipaddr, port, vrf):
        return

    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    collector_tbl = config_db.get_table('SFLOW_COLLECTOR')

    if (collector_tbl and name not in collector_tbl and len(collector_tbl) == 2):
        click.echo("Only 2 collectors can be configured, please delete one")
        return

    try:
        config_db.mod_entry('SFLOW_COLLECTOR', name,
                            {"collector_ip": ipaddr,  "collector_port": port,
                             "collector_vrf": vrf})
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    return

#
# 'sflow' command ('config sflow collector del ...')
#
@collector.command('del')
@click.argument('name', metavar='<collector_name>', required=True)
@click.pass_context
def del_collector(ctx, name):
    """Delete a sFlow collector"""
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    if ADHOC_VALIDATION:
        collector_tbl = config_db.get_table('SFLOW_COLLECTOR')

        if name not in collector_tbl:
            click.echo("Collector: {} not configured".format(name))
            return

    try:
        config_db.set_entry('SFLOW_COLLECTOR', name, None)
    except (JsonPatchConflict, JsonPointerException) as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'sflow agent-id' group
#
@sflow.group(cls=clicommon.AbbreviationGroup, name='agent-id')
@click.pass_context
def agent_id(ctx):
    """Add/Delete a sFlow agent"""
    pass

#
# 'sflow' command ('config sflow agent-id add ...')
#
@agent_id.command()
@click.argument('ifname', metavar='<interface_name>', required=True)
@click.pass_context
def add(ctx, ifname):
    """Add sFlow agent information"""
    if ADHOC_VALIDATION:
        if ifname not in netifaces.interfaces():
            click.echo("Invalid interface name")
            return

    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}

    if 'agent_id' in sflow_tbl['global']:
        click.echo("Agent already configured. Please delete it first.")
        return

    sflow_tbl['global']['agent_id'] = ifname
    try:
        config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'sflow' command ('config sflow agent-id del')
#
@agent_id.command('del')
@click.pass_context
def delete(ctx):
    """Delete sFlow agent information"""
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}

    if 'agent_id' not in sflow_tbl['global']:
        click.echo("sFlow agent not configured.")
        return

    sflow_tbl['global'].pop('agent_id')
    try:
        config_db.set_entry('SFLOW', 'global', sflow_tbl['global'])
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# set ipv6 link local mode on a given interface
#
def set_ipv6_link_local_only_on_interface(config_db, interface_dict, interface_type, interface_name, mode):

    curr_mode = config_db.get_entry(interface_type, interface_name).get('ipv6_use_link_local_only')
    if curr_mode is not None:
        if curr_mode == mode:
            return
    else:
        if mode == "disable":
            return

    if mode == "enable":
        config_db.mod_entry(interface_type, interface_name, {"ipv6_use_link_local_only": mode})
        return

    # If we are disabling the ipv6 link local on an interface, and if no other interface
    # attributes/ip addresses are configured on the interface, delete the interface from the interface table
    exists = False
    for key in interface_dict.keys():
        if not isinstance(key, tuple):
            if interface_name == key:
                #Interface bound to non-default-vrf do not delete the entry
                if 'vrf_name' in interface_dict[key]:
                    if len(interface_dict[key]['vrf_name']) > 0:
                        exists = True
                        break
            continue
        if interface_name in key:
            exists = True
            break

    if exists:
        config_db.mod_entry(interface_type, interface_name, {"ipv6_use_link_local_only": mode})
    else:
        config_db.set_entry(interface_type, interface_name, None)

#
# 'ipv6' group ('config ipv6 ...')
#

@config.group()
@click.pass_context
def ipv6(ctx):
    """IPv6 configuration"""

#
# 'enable' command ('config ipv6 enable ...')
#
@ipv6.group()
@click.pass_context
def enable(ctx):
    """Enable IPv6 on all interfaces """

#
# 'link-local' command ('config ipv6 enable link-local')
#
@enable.command('link-local')
@click.pass_context
def enable_link_local(ctx):
    """Enable IPv6 link-local on all interfaces """
    config_db = ConfigDBConnector()
    config_db.connect()
    vlan_member_table = config_db.get_table('VLAN_MEMBER')
    portchannel_member_table = config_db.get_table('PORTCHANNEL_MEMBER')

    mode = "enable"

    # Enable ipv6 link local on VLANs
    vlan_dict = config_db.get_table('VLAN')
    for key in vlan_dict.keys():
        set_ipv6_link_local_only_on_interface(config_db, vlan_dict, 'VLAN_INTERFACE', key, mode)

    # Enable ipv6 link local on PortChannels
    portchannel_dict = config_db.get_table('PORTCHANNEL')
    for key in portchannel_dict.keys():
        if interface_is_in_vlan(vlan_member_table, key):
            continue
        set_ipv6_link_local_only_on_interface(config_db, portchannel_dict, 'PORTCHANNEL_INTERFACE', key, mode)

    port_dict = config_db.get_table('PORT')
    for key in port_dict.keys():
        if interface_is_in_portchannel(portchannel_member_table, key) or interface_is_in_vlan(vlan_member_table, key):
            continue
        set_ipv6_link_local_only_on_interface(config_db, port_dict, 'INTERFACE', key, mode)

#
# 'disable' command ('config ipv6 disable ...')
#
@ipv6.group()
@click.pass_context
def disable(ctx):
    """Disable IPv6 on all interfaces """

#
# 'link-local' command ('config ipv6 disable link-local')
#
@disable.command('link-local')
@click.pass_context
def disable_link_local(ctx):
    """Disable IPv6 link local on all interfaces """
    config_db = ConfigDBConnector()
    config_db.connect()

    mode = "disable"

    tables = ['INTERFACE', 'VLAN_INTERFACE', 'PORTCHANNEL_INTERFACE']

    for table_type in tables:
        table_dict = config_db.get_table(table_type)
        if table_dict:
            for key in table_dict.keys():
                if isinstance(key, str) is False:
                    continue
                set_ipv6_link_local_only_on_interface(config_db, table_dict, table_type, key, mode)


#
# 'rate' group ('config rate ...')
#

@config.group()
def rate():
    """Set port rates configuration."""
    pass


@rate.command()
@click.argument('interval', metavar='<interval>', type=click.IntRange(min=1, max=1000), required=True)
@click.argument('rates_type', type=click.Choice(['all', 'port', 'rif', 'flowcnt-trap']), default='all')
def smoothing_interval(interval, rates_type):
    """Set rates smoothing interval """
    counters_db = SonicV2Connector()
    counters_db.connect('COUNTERS_DB')

    alpha = 2.0/(interval + 1)

    if rates_type in ['port', 'all']:
        counters_db.set('COUNTERS_DB', 'RATES:PORT', 'PORT_SMOOTH_INTERVAL', interval)
        counters_db.set('COUNTERS_DB', 'RATES:PORT', 'PORT_ALPHA', alpha)
    if rates_type in ['rif', 'all']:
        counters_db.set('COUNTERS_DB', 'RATES:RIF', 'RIF_SMOOTH_INTERVAL', interval)
        counters_db.set('COUNTERS_DB', 'RATES:RIF', 'RIF_ALPHA', alpha)
    if rates_type in ['flowcnt-trap', 'all']:
        counters_db.set('COUNTERS_DB', 'RATES:TRAP', 'TRAP_SMOOTH_INTERVAL', interval)
        counters_db.set('COUNTERS_DB', 'RATES:TRAP', 'TRAP_ALPHA', alpha)


# Load plugins and register them
helper = util_base.UtilHelper()
helper.load_and_register_plugins(plugins, config)

#
# 'subinterface' group ('config subinterface ...')
#
@config.group()
@click.pass_context
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def subinterface(ctx, redis_unix_socket_path):
    """subinterface-related configuration tasks"""
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path
    config_db = ConfigDBConnector(**kwargs)
    config_db.connect(wait_for_init=False)
    ctx.obj = {'db': config_db}

def subintf_vlan_check(config_db, parent_intf, vlan):
    subintf_db = config_db.get_table('VLAN_SUB_INTERFACE')
    subintf_names = [k for k in subintf_db if type(k) != tuple]
    for subintf in subintf_names:
        sub_intf_sep_idx = subintf.find(VLAN_SUB_INTERFACE_SEPARATOR)
        if sub_intf_sep_idx == -1:
            continue
        if parent_intf == subintf[:sub_intf_sep_idx]:
            if 'vlan' in subintf_db[subintf]:
                if str(vlan) == subintf_db[subintf]['vlan']:
                    return True
            else:
                vlan_id = subintf[sub_intf_sep_idx + 1:]
                if str(vlan) == vlan_id:
                    return True
    return False

def is_subintf_shortname(intf):
    if VLAN_SUB_INTERFACE_SEPARATOR in intf:
        if intf.startswith("Ethernet") or intf.startswith("PortChannel"):
            return False
        return True
    return False

@subinterface.command('add')
@click.argument('subinterface_name', metavar='<subinterface_name>', required=True)
@click.argument('vid', metavar='<vid>', required=False, type=click.IntRange(1,4094))
@click.pass_context
def add_subinterface(ctx, subinterface_name, vid):
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])
    sub_intf_sep_idx = subinterface_name.find(VLAN_SUB_INTERFACE_SEPARATOR)
    interface_alias = subinterface_name[:sub_intf_sep_idx]
    if ADHOC_VALIDATION:
        if sub_intf_sep_idx == -1:
            ctx.fail("{} is invalid vlan subinterface".format(subinterface_name))

        if interface_alias is None:
            ctx.fail("{} invalid subinterface".format(interface_alias))

        if interface_alias.startswith("Po") is True:
            intf_table_name = CFG_PORTCHANNEL_PREFIX
        elif interface_alias.startswith("Eth") is True:
            intf_table_name = 'PORT'
        else:
            ctx.fail("{} is invalid vlan subinterface".format(subinterface_name))

        port_dict = config_db.get_table(intf_table_name)
        parent_intf = get_intf_longname(interface_alias)
        if interface_alias is not None:
            if not port_dict:
                ctx.fail("{} parent interface not found. {} table none".format(interface_alias, intf_table_name))
            if parent_intf not in port_dict.keys():
                ctx.fail("{} parent interface not found".format(subinterface_name))

        # Validate if parent is portchannel member
        portchannel_member_table = config_db.get_table('PORTCHANNEL_MEMBER')
        if interface_is_in_portchannel(portchannel_member_table, parent_intf): # TODO: MISSING CONSTRAINT IN YANG MODEL
            ctx.fail("{} is configured as a member of portchannel. Cannot configure subinterface"
                    .format(parent_intf))

        # Validate if parent is vlan member
        vlan_member_table = config_db.get_table('VLAN_MEMBER')
        if interface_is_in_vlan(vlan_member_table, parent_intf): # TODO: MISSING CONSTRAINT IN YANG MODEL
            ctx.fail("{} is configured as a member of vlan. Cannot configure subinterface"
                    .format(parent_intf))

        sub_intfs = [k for k,v in config_db.get_table('VLAN_SUB_INTERFACE').items() if type(k) != tuple]
        if subinterface_name in sub_intfs:
            ctx.fail("{} already exists".format(subinterface_name)) # TODO: MISSING CONSTRAINT IN YANG MODEL

        if subintf_vlan_check(config_db, get_intf_longname(interface_alias), vid) is True:
            ctx.fail("Vlan {} encap already configured on other subinterface on {}".format(vid, interface_alias)) # TODO: MISSING CONSTRAINT IN YANG MODEL

        if vid is None and is_subintf_shortname(subinterface_name):
            ctx.fail("{} Encap vlan is mandatory or short name subinterfaces".format(subinterface_name)) # TODO: MISSING CONSTRAINT IN YANG MODEL

    subintf_dict = {}
    if vid is not None:
        subintf_dict.update({"vlan" : vid})
    subintf_dict.update({"admin_status" : "up"})

    try:
        config_db.set_entry('VLAN_SUB_INTERFACE', subinterface_name, subintf_dict)
    except ValueError as e:
        ctx.fail("Invalid vlan subinterface. Error: {}".format(e))

@subinterface.command('del')
@click.argument('subinterface_name', metavar='<subinterface_name>', required=True)
@click.pass_context
def del_subinterface(ctx, subinterface_name):
    config_db = ValidatedConfigDBConnector(ctx.obj['db'])

    if ADHOC_VALIDATION:
        sub_intf_sep_idx = subinterface_name.find(VLAN_SUB_INTERFACE_SEPARATOR)
        if sub_intf_sep_idx == -1:
            ctx.fail("{} is invalid vlan subinterface".format(subinterface_name))

        #subinterface_name = subintf_get_shortname(subinterface_name)
        if interface_name_is_valid(config_db, subinterface_name) is False:
            ctx.fail("{} is invalid ".format(subinterface_name))

        subintf_config_db = config_db.get_table('VLAN_SUB_INTERFACE')
        sub_intfs = [k for k,v in subintf_config_db.items() if type(k) != tuple]
        if subinterface_name not in sub_intfs:
            ctx.fail("{} does not exists".format(subinterface_name))

    ips = {}
    ips = [ k[1] for k in config_db.get_table('VLAN_SUB_INTERFACE') if type(k) == tuple and k[0] == subinterface_name ]
    for ip in ips:
        try:
            ipaddress.ip_network(ip, strict=False)
            config_db.set_entry('VLAN_SUB_INTERFACE', (subinterface_name, ip), None)
        except ValueError:
            ctx.fail("Invalid ip {} found on interface {}".format(ip, subinterface_name))

    subintf_config_db = config_db.get_table('INTERFACE')
    ips = [ k[1] for k in subintf_config_db if type(k) == tuple and k[0] == subinterface_name ]
    for ip in ips:
        config_db.set_entry('INTERFACE', (subinterface_name, ip), None)

    try:
        config_db.set_entry('VLAN_SUB_INTERFACE', subinterface_name, None)
    except JsonPatchConflict as e:
        ctx.fail("{} is invalid vlan subinterface. Error: {}".format(subinterface_name, e))

if __name__ == '__main__':
    config()
