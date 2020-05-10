#!/usr/sbin/env python

import sys
import os
import click
import subprocess
import netaddr
import re
import syslog
import time
import netifaces

import sonic_device_util
import ipaddress
from swsssdk import ConfigDBConnector, SonicV2Connector, SonicDBConfig
from minigraph import parse_device_desc_xml

import aaa
import mlnx
import nat

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

SONIC_GENERATED_SERVICE_PATH = '/etc/sonic/generated_services.conf'
SONIC_CFGGEN_PATH = '/usr/local/bin/sonic-cfggen'
SYSLOG_IDENTIFIER = "config"
VLAN_SUB_INTERFACE_SEPARATOR = '.'
ASIC_CONF_FILENAME = 'asic.conf'
DEFAULT_CONFIG_DB_FILE = '/etc/sonic/config_db.json'
NAMESPACE_PREFIX = 'asic'

INIT_CFG_FILE = '/etc/sonic/init_cfg.json'

SYSTEMCTL_ACTION_STOP="stop"
SYSTEMCTL_ACTION_RESTART="restart"
SYSTEMCTL_ACTION_RESET_FAILED="reset-failed"

DEFAULT_NAMESPACE = ''
# ========================== Syslog wrappers ==========================

def log_debug(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_DEBUG, msg)
    syslog.closelog()


def log_info(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()


def log_warning(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_WARNING, msg)
    syslog.closelog()


def log_error(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()


class AbbreviationGroup(click.Group):
    """This subclass of click.Group supports abbreviated subgroup/subcommand names
    """

    def get_command(self, ctx, cmd_name):
        # Try to get builtin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # Allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        # If there are multiple matches and the shortest one is the common prefix of all the matches, return
        # the shortest one
        matches = []
        shortest = None
        for x in self.list_commands(ctx):
            if x.lower().startswith(cmd_name.lower()):
                matches.append(x)
                if not shortest:
                    shortest = x
                elif len(shortest) > len(x):
                    shortest = x

        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        else:
            for x in matches:
                if not x.startswith(shortest):
                    break
            else:
                return click.Group.get_command(self, ctx, shortest)

            ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


#
# Load asic_type for further use
#

try:
    version_info = sonic_device_util.get_sonic_version_info()
    asic_type = version_info['asic_type']
except KeyError, TypeError:
    raise click.Abort()

#
# Helper functions
#

# Execute action on list of systemd services
def execute_systemctl(list_of_services, action):
    num_asic = _get_num_asic()
    generated_services_list, generated_multi_instance_services = _get_sonic_generated_services(num_asic)
    if ((generated_services_list == []) and
        (generated_multi_instance_services == [])):
        log_error("Failed to get generated services")
        return

    for service in list_of_services:
        if (service + '.service' in generated_services_list):
            try:
                click.echo("Executing {} of service {}...".format(action, service))
                run_command("systemctl {} {}".format(action, service))
            except SystemExit as e:
                log_error("Failed to execute {} of service {} with error {}".format(action, service, e))
                raise
        if (service + '.service' in generated_multi_instance_services):
            for inst in range(num_asic):
                try:
                    click.echo("Executing {} of service {}@{}...".format(action, service, inst))
                    run_command("systemctl {} {}@{}.service".format(action, service, inst))
                except SystemExit as e:
                    log_error("Failed to execute {} of service {}@{} with error {}".format(action, service, inst, e))
                    raise

def run_command(command, display_cmd=False, ignore_error=False):
    """Run bash command and print output to stdout
    """
    if display_cmd == True:
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    (out, err) = proc.communicate()

    if len(out) > 0:
        click.echo(out)

    if proc.returncode != 0 and not ignore_error:
        sys.exit(proc.returncode)

# API to check if this is a multi-asic device or not.
def is_multi_asic():
    num_asics = _get_num_asic()

    if num_asics > 1:
        return True
    else:
        return False

"""In case of Multi-Asic platform, Each ASIC will have a linux network namespace created.
   So we loop through the databases in different namespaces and depending on the sub_role
   decide whether this is a front end ASIC/namespace or a back end one.
"""
def get_all_namespaces():
    front_ns = []
    back_ns = []
    num_asics = _get_num_asic()

    if is_multi_asic():
        for asic in range(num_asics):
            namespace = "{}{}".format(NAMESPACE_PREFIX, asic)
            config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
            config_db.connect()

            metadata = config_db.get_table('DEVICE_METADATA')
            if metadata['localhost']['sub_role'] == 'FrontEnd':
                front_ns.append(namespace)
            elif metadata['localhost']['sub_role'] == 'BackEnd':
                back_ns.append(namespace)

    return {'front_ns': front_ns, 'back_ns': back_ns}

# Validate whether a given namespace name is valid in the device.
def validate_namespace(namespace):
    if not is_multi_asic():
        return True

    namespaces = get_all_namespaces()
    if namespace in namespaces['front_ns'] + namespaces['back_ns']:
        return True
    else:
        return False

def interface_alias_to_name(interface_alias):
    """Return default interface name if alias name is given as argument
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    port_dict = config_db.get_table('PORT')

    vlan_id = ""
    sub_intf_sep_idx = -1
    if interface_alias is not None:
        sub_intf_sep_idx = interface_alias.find(VLAN_SUB_INTERFACE_SEPARATOR)
        if sub_intf_sep_idx != -1:
            vlan_id = interface_alias[sub_intf_sep_idx + 1:]
            # interface_alias holds the parent port name so the subsequent logic still applies
            interface_alias = interface_alias[:sub_intf_sep_idx]

    if interface_alias is not None:
        if not port_dict:
            click.echo("port_dict is None!")
            raise click.Abort()
        for port_name in port_dict.keys():
            if interface_alias == port_dict[port_name]['alias']:
                return port_name if sub_intf_sep_idx == -1 else port_name + VLAN_SUB_INTERFACE_SEPARATOR + vlan_id

    # Interface alias not in port_dict, just return interface_alias, e.g.,
    # portchannel is passed in as argument, which does not have an alias
    return interface_alias if sub_intf_sep_idx == -1 else interface_alias + VLAN_SUB_INTERFACE_SEPARATOR + vlan_id


def interface_name_is_valid(interface_name):
    """Check if the interface name is valid
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    port_dict = config_db.get_table('PORT')
    port_channel_dict = config_db.get_table('PORTCHANNEL')
    sub_port_intf_dict = config_db.get_table('VLAN_SUB_INTERFACE')

    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)

    if interface_name is not None:
        if not port_dict:
            click.echo("port_dict is None!")
            raise click.Abort()
        for port_name in port_dict.keys():
            if interface_name == port_name:
                return True
        if port_channel_dict:
            for port_channel_name in port_channel_dict.keys():
                if interface_name == port_channel_name:
                    return True
        if sub_port_intf_dict:
            for sub_port_intf_name in sub_port_intf_dict.keys():
                if interface_name == sub_port_intf_name:
                    return True
    return False

def interface_name_to_alias(interface_name):
    """Return alias interface name if default name is given as argument
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    port_dict = config_db.get_table('PORT')

    if interface_name is not None:
        if not port_dict:
            click.echo("port_dict is None!")
            raise click.Abort()
        for port_name in port_dict.keys():
            if interface_name == port_name:
                return port_dict[port_name]['alias']

    return None

def get_interface_table_name(interface_name):
    """Get table name by interface_name prefix
    """
    if interface_name.startswith("Ethernet"):
        if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
            return "VLAN_SUB_INTERFACE"
        return "INTERFACE"
    elif interface_name.startswith("PortChannel"):
        if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
            return "VLAN_SUB_INTERFACE"
        return "PORTCHANNEL_INTERFACE"
    elif interface_name.startswith("Vlan"):
        return "VLAN_INTERFACE"
    elif interface_name.startswith("Loopback"):
        return "LOOPBACK_INTERFACE"
    else:
        return ""

def interface_ipaddr_dependent_on_interface(config_db, interface_name):
    """Get table keys including ipaddress
    """
    data = []
    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        return data
    keys = config_db.get_keys(table_name)
    for key in keys:
        if interface_name in key and len(key) == 2:
            data.append(key)
    return data

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

def del_interface_bind_to_vrf(config_db, vrf_name):
    """del interface bind to vrf
    """
    tables = ['INTERFACE', 'PORTCHANNEL_INTERFACE', 'VLAN_INTERFACE', 'LOOPBACK_INTERFACE']
    for table_name in tables:
        interface_dict = config_db.get_table(table_name)
        if interface_dict:
            for interface_name in interface_dict.keys():
                if interface_dict[interface_name].has_key('vrf_name') and vrf_name == interface_dict[interface_name]['vrf_name']:
                    interface_dependent = interface_ipaddr_dependent_on_interface(config_db, interface_name)
                    for interface_del in interface_dependent:
                        config_db.set_entry(table_name, interface_del, None)
                    config_db.set_entry(table_name, interface_name, None)

def set_interface_naming_mode(mode):
    """Modify SONIC_CLI_IFACE_MODE env variable in user .bashrc
    """
    user = os.getenv('SUDO_USER')
    bashrc_ifacemode_line = "export SONIC_CLI_IFACE_MODE={}".format(mode)

    # Ensure all interfaces have an 'alias' key in PORT dict
    config_db = ConfigDBConnector()
    config_db.connect()
    port_dict = config_db.get_table('PORT')

    if not port_dict:
        click.echo("port_dict is None!")
        raise click.Abort()

    for port_name in port_dict.keys():
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


def get_interface_naming_mode():
    mode = os.getenv('SONIC_CLI_IFACE_MODE')
    if mode is None:
        mode = "default"
    return mode

def _is_neighbor_ipaddress(ipaddress):
    """Returns True if a neighbor has the IP address <ipaddress>, False if not
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    entry = config_db.get_entry('BGP_NEIGHBOR', ipaddress)
    return True if entry else False

def _get_all_neighbor_ipaddresses():
    """Returns list of strings containing IP addresses of all BGP neighbors
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    return config_db.get_table('BGP_NEIGHBOR').keys()

def _get_neighbor_ipaddress_list_by_hostname(hostname):
    """Returns list of strings, each containing an IP address of neighbor with
       hostname <hostname>. Returns empty list if <hostname> not a neighbor
    """
    addrs = []
    config_db = ConfigDBConnector()
    config_db.connect()
    bgp_sessions = config_db.get_table('BGP_NEIGHBOR')
    for addr, session in bgp_sessions.iteritems():
        if session.has_key('name') and session['name'] == hostname:
            addrs.append(addr)
    return addrs

def _change_bgp_session_status_by_addr(ipaddress, status, verbose):
    """Start up or shut down BGP session by IP address
    """
    verb = 'Starting' if status == 'up' else 'Shutting'
    click.echo("{} {} BGP session with neighbor {}...".format(verb, status, ipaddress))
    config_db = ConfigDBConnector()
    config_db.connect()

    config_db.mod_entry('bgp_neighbor', ipaddress, {'admin_status': status})

def _change_bgp_session_status(ipaddr_or_hostname, status, verbose):
    """Start up or shut down BGP session by IP address or hostname
    """
    ip_addrs = []

    # If we were passed an IP address, convert it to lowercase because IPv6 addresses were
    # stored in ConfigDB with all lowercase alphabet characters during minigraph parsing
    if _is_neighbor_ipaddress(ipaddr_or_hostname.lower()):
        ip_addrs.append(ipaddr_or_hostname.lower())
    else:
        # If <ipaddr_or_hostname> is not the IP address of a neighbor, check to see if it's a hostname
        ip_addrs = _get_neighbor_ipaddress_list_by_hostname(ipaddr_or_hostname)

    if not ip_addrs:
        click.get_current_context().fail("Could not locate neighbor '{}'".format(ipaddr_or_hostname))

    for ip_addr in ip_addrs:
        _change_bgp_session_status_by_addr(ip_addr, status, verbose)

def _validate_bgp_neighbor(neighbor_ip_or_hostname):
    """validates whether the given ip or host name is a BGP neighbor
    """
    ip_addrs = []
    if _is_neighbor_ipaddress(neighbor_ip_or_hostname.lower()):
        ip_addrs.append(neighbor_ip_or_hostname.lower())
    else:
        ip_addrs = _get_neighbor_ipaddress_list_by_hostname(neighbor_ip_or_hostname.upper())

    if not ip_addrs:
        click.get_current_context().fail("Could not locate neighbor '{}'".format(neighbor_ip_or_hostname))

    return ip_addrs

def _remove_bgp_neighbor_config(neighbor_ip_or_hostname):
    """Removes BGP configuration of the given neighbor
    """
    ip_addrs = _validate_bgp_neighbor(neighbor_ip_or_hostname)
    config_db = ConfigDBConnector()
    config_db.connect()

    for ip_addr in ip_addrs:
        config_db.mod_entry('bgp_neighbor', ip_addr, None)
        click.echo("Removed configuration of BGP neighbor {}".format(ip_addr))

def _change_hostname(hostname):
    current_hostname = os.uname()[1]
    if current_hostname != hostname:
        run_command('echo {} > /etc/hostname'.format(hostname), display_cmd=True)
        run_command('hostname -F /etc/hostname', display_cmd=True)
        run_command('sed -i "/\s{}$/d" /etc/hosts'.format(current_hostname), display_cmd=True)
        run_command('echo "127.0.0.1 {}" >> /etc/hosts'.format(hostname), display_cmd=True)

def _clear_qos():
    QOS_TABLE_NAMES = [
            'TC_TO_PRIORITY_GROUP_MAP',
            'MAP_PFC_PRIORITY_TO_QUEUE',
            'TC_TO_QUEUE_MAP',
            'DSCP_TO_TC_MAP',
            'SCHEDULER',
            'PFC_PRIORITY_TO_PRIORITY_GROUP_MAP',
            'PORT_QOS_MAP',
            'WRED_PROFILE',
            'QUEUE',
            'CABLE_LENGTH',
            'BUFFER_POOL',
            'BUFFER_PROFILE',
            'BUFFER_PG',
            'BUFFER_QUEUE']
    config_db = ConfigDBConnector()
    config_db.connect()
    for qos_table in QOS_TABLE_NAMES:
        config_db.delete_table(qos_table)

def _get_hwsku():
    config_db = ConfigDBConnector()
    config_db.connect()
    metadata = config_db.get_table('DEVICE_METADATA')
    return metadata['localhost']['hwsku']

def _get_platform():
    with open('/host/machine.conf') as machine_conf:
        for line in machine_conf:
            tokens = line.split('=')
            if tokens[0].strip() == 'onie_platform' or tokens[0].strip() == 'aboot_platform':
                return tokens[1].strip()
    return ''

def _get_num_asic():
    platform = _get_platform()
    num_asic = 1
    asic_conf_file = os.path.join('/usr/share/sonic/device/', platform, ASIC_CONF_FILENAME)
    if os.path.isfile(asic_conf_file):
        with open(asic_conf_file) as conf_file:
            for line in conf_file:
                line_info = line.split('=')
                if line_info[0].lower() == "num_asic":
                    num_asic = int(line_info[1])
    return num_asic

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

def _stop_services():
    # on Mellanox platform pmon is stopped by syncd
    services_to_stop = [
        'swss',
        'lldp',
        'pmon',
        'bgp',
        'hostcfgd',
        'nat'
    ]

    if asic_type == 'mellanox' and 'pmon' in services_to_stop:
        services_to_stop.remove('pmon')

    execute_systemctl(services_to_stop, SYSTEMCTL_ACTION_STOP)

def _reset_failed_services():
    services_to_reset = [
        'bgp',
        'dhcp_relay',
        'hostcfgd',
        'hostname-config',
        'interfaces-config',
        'lldp',
        'ntp-config',
        'pmon',
        'radv',
        'rsyslog-config',
        'snmp',
        'swss',
        'syncd',
        'teamd',
        'nat',
        'sflow'
    ]
    execute_systemctl(services_to_reset, SYSTEMCTL_ACTION_RESET_FAILED)



def _restart_services():
    # on Mellanox platform pmon is started by syncd
    services_to_restart = [
        'hostname-config',
        'interfaces-config',
        'ntp-config',
        'rsyslog-config',
        'swss',
        'bgp',
        'pmon',
        'lldp',
        'hostcfgd',
        'nat',
        'sflow',
    ]

    if asic_type == 'mellanox' and 'pmon' in services_to_restart:
        services_to_restart.remove('pmon')

    execute_systemctl(services_to_restart, SYSTEMCTL_ACTION_RESTART)


def is_ipaddress(val):
    """ Validate if an entry is a valid IP """
    if not val:
        return False
    try:
        netaddr.IPAddress(str(val))
    except ValueError:
        return False
    return True


# This is our main entrypoint - the main 'config' command
@click.group(cls=AbbreviationGroup, context_settings=CONTEXT_SETTINGS)
def config():
    """SONiC command line - 'config' command"""

    # Load the global config file database_global.json once.
    SonicDBConfig.load_sonic_global_db_config()

    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

    SonicDBConfig.load_sonic_global_db_config()


config.add_command(aaa.aaa)
config.add_command(aaa.tacacs)
# === Add NAT Configuration ==========
config.add_command(nat.nat)

@config.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Existing files will be overwritten, continue?')
@click.argument('filename', required=False)
def save(filename):
    """Export current config DB to a file on disk.\n
       <filename> : Names of configuration file(s) to save, separated by comma with no spaces in between
    """
    num_asic = _get_num_asic()
    cfg_files = []

    num_cfg_file = 1
    if is_multi_asic():
        num_cfg_file += num_asic

    # If the user give the filename[s], extract the file names.
    if filename is not None:
        cfg_files = filename.split(',')

        if len(cfg_files) != num_cfg_file:
            click.echo("Input {} config file(s) separated by comma for multiple files ".format(num_cfg_file))
            return

    """In case of multi-asic mode we have additional config_db{NS}.json files for
       various namespaces created per ASIC. {NS} is the namespace index.
    """
    for inst in range(-1, num_cfg_file-1):
        #inst = -1, refers to the linux host where there is no namespace.
        if inst is -1:
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

        log_info("'save' executing...")
        run_command(command, display_cmd=True)

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

    num_asic = _get_num_asic()
    cfg_files = []

    num_cfg_file = 1
    if is_multi_asic():
        num_cfg_file += num_asic

    # If the user give the filename[s], extract the file names.
    if filename is not None:
        cfg_files = filename.split(',')

        if len(cfg_files) != num_cfg_file:
            click.echo("Input {} config file(s) separated by comma for multiple files ".format(num_cfg_file))
            return

    """In case of multi-asic mode we have additional config_db{NS}.json files for
       various namespaces created per ASIC. {NS} is the namespace index.
    """
    for inst in range(-1, num_cfg_file-1):
        #inst = -1, refers to the linux host where there is no namespace.
        if inst is -1:
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
        if not os.path.isfile(file):
            click.echo("The config_db file {} doesn't exist".format(file))
            return 

        if namespace is None:
            command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, file)
        else:
            command = "{} -n {} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, namespace, file)

        log_info("'load' executing...")
        run_command(command, display_cmd=True)


@config.command()
@click.option('-y', '--yes', is_flag=True)
@click.option('-l', '--load-sysinfo', is_flag=True, help='load system default information (mac, portmap etc) first.')
@click.argument('filename', required=False)
def reload(filename, yes, load_sysinfo):
    """Clear current configuration and import a previous saved config DB dump file.
       <filename> : Names of configuration file(s) to load, separated by comma with no spaces in between
    """
    if filename is None:
        message = 'Clear current config and reload config from the default config file(s) ?'
    else:
        message = 'Clear current config and reload config from the file(s) {} ?'.format(filename)

    if not yes:
        click.confirm(message, abort=True)

    log_info("'reload' executing...")

    num_asic = _get_num_asic()
    cfg_files = []

    num_cfg_file = 1
    if is_multi_asic():
        num_cfg_file += num_asic

    # If the user give the filename[s], extract the file names.
    if filename is not None:
        cfg_files = filename.split(',')

        if len(cfg_files) != num_cfg_file:
            click.echo("Input {} config file(s) separated by comma for multiple files ".format(num_cfg_file))
            return

    if load_sysinfo:
        command = "{} -j {} -v DEVICE_METADATA.localhost.hwsku".format(SONIC_CFGGEN_PATH, filename)
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        cfg_hwsku, err = proc.communicate()
        if err:
            click.echo("Could not get the HWSKU from config file, exiting")
            sys.exit(1)
        else:
            cfg_hwsku = cfg_hwsku.strip()

    #Stop services before config push
    log_info("'reload' stopping services...")
    _stop_services()

    """ In Single AISC platforms we have single DB service. In multi-ASIC platforms we have a global DB
        service running in the host + DB services running in each ASIC namespace created per ASIC.
        In the below logic, we get all namespaces in this platform and add an empty namespace ''
        denoting the current namespace which we are in ( the linux host )
    """
    for inst in range(-1, num_cfg_file-1):
        # Get the namespace name, for linux host it is None
        if inst is -1:
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

        #Check the file exists before proceeding.
        if not os.path.isfile(file):
            click.echo("The config_db file {} doesn't exist".format(file))
            continue

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
            run_command(command, display_cmd=True)

        # For the database service running in linux host we use the file user gives as input
        # or by default DEFAULT_CONFIG_DB_FILE. In the case of database service running in namespace,
        # the default config_db<namespaceID>.json format is used.

        if namespace is None:
            if os.path.isfile(INIT_CFG_FILE):
                command = "{} -j {} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, INIT_CFG_FILE, file)
            else:
                command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, file)
        else:
            if os.path.isfile(INIT_CFG_FILE):
                command = "{} -j {} -j {} -n {} --write-to-db".format(SONIC_CFGGEN_PATH, INIT_CFG_FILE, file, namespace)
            else:
                command = "{} -j {} -n {} --write-to-db".format(SONIC_CFGGEN_PATH, file, namespace)

        run_command(command, display_cmd=True)
        client.set(config_db.INIT_INDICATOR, 1)

        # Migrate DB contents to latest version
        db_migrator='/usr/bin/db_migrator.py'
        if os.path.isfile(db_migrator) and os.access(db_migrator, os.X_OK):
            if namespace is None:
                command = "{} -o migrate".format(db_migrator)
            else:
                command = "{} -o migrate -n {}".format(db_migrator, namespace)
            run_command(command, display_cmd=True)

    # We first run "systemctl reset-failed" to remove the "failed"
    # status from all services before we attempt to restart them
    _reset_failed_services()
    log_info("'reload' restarting services...")
    _restart_services()

@config.command("load_mgmt_config")
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload mgmt config?')
@click.argument('filename', default='/etc/sonic/device_desc.xml', type=click.Path(exists=True))
def load_mgmt_config(filename):
    """Reconfigure hostname and mgmt interface based on device description file."""
    log_info("'load_mgmt_config' executing...")
    command = "{} -M {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)
    #FIXME: After config DB daemon for hostname and mgmt interface is implemented, we'll no longer need to do manual configuration here
    config_data = parse_device_desc_xml(filename)
    hostname = config_data['DEVICE_METADATA']['localhost']['hostname']
    _change_hostname(hostname)
    mgmt_conf = netaddr.IPNetwork(config_data['MGMT_INTERFACE'].keys()[0][1])
    gw_addr = config_data['MGMT_INTERFACE'].values()[0]['gwaddr']
    command = "ifconfig eth0 {} netmask {}".format(str(mgmt_conf.ip), str(mgmt_conf.netmask))
    run_command(command, display_cmd=True)
    command = "ip route add default via {} dev eth0 table default".format(gw_addr)
    run_command(command, display_cmd=True, ignore_error=True)
    command = "ip rule add from {} table default".format(str(mgmt_conf.ip))
    run_command(command, display_cmd=True, ignore_error=True)
    command = "[ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid"
    run_command(command, display_cmd=True, ignore_error=True)
    click.echo("Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.")

@config.command("load_minigraph")
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload config from minigraph?')
def load_minigraph():
    """Reconfigure based on minigraph."""
    log_info("'load_minigraph' executing...")

    # get the device type
    command = "{} -m -v DEVICE_METADATA.localhost.type".format(SONIC_CFGGEN_PATH)
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    device_type, err = proc.communicate()
    if err:
        click.echo("Could not get the device type from minigraph, setting device type to Unknown")
        device_type = 'Unknown'
    else:
        device_type = device_type.strip()

    #Stop services before config push
    log_info("'load_minigraph' stopping services...")
    _stop_services()

    # For Single Asic platform the namespace list has the empty string
    # for mulit Asic platform the empty string to generate the config
    # for host
    namespace_list = [DEFAULT_NAMESPACE]
    num_npus = sonic_device_util.get_num_npus()
    if num_npus > 1:
        namespace_list += sonic_device_util.get_namespaces()

    for namespace in namespace_list:
        if namespace is DEFAULT_NAMESPACE:
            config_db = ConfigDBConnector()
            cfggen_namespace_option = " "
            ns_cmd_prefix = " "
        else:
            config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
            cfggen_namespace_option = " -n {}".format(namespace)
            ns_cmd_prefix = "sudo ip netns exec {}".format(namespace)
        config_db.connect()
        client = config_db.get_redis_client(config_db.CONFIG_DB)
        client.flushdb()
        if os.path.isfile('/etc/sonic/init_cfg.json'):
            command = "{} -H -m -j /etc/sonic/init_cfg.json {} --write-to-db".format(SONIC_CFGGEN_PATH, cfggen_namespace_option)
        else:
            command = "{} -H -m --write-to-db {} ".format(SONIC_CFGGEN_PATH,cfggen_namespace_option)
        run_command(command, display_cmd=True)
        client.set(config_db.INIT_INDICATOR, 1)

        # These commands are not run for host on multi asic platform
        if num_npus == 1 or namespace is not DEFAULT_NAMESPACE:
            if device_type != 'MgmtToRRouter':
                run_command('{} pfcwd start_default'.format(ns_cmd_prefix), display_cmd=True)
            run_command("{} config qos reload".format(ns_cmd_prefix), display_cmd=True)

        # Write latest db version string into db
        db_migrator='/usr/bin/db_migrator.py'
        if os.path.isfile(db_migrator) and os.access(db_migrator, os.X_OK):
            run_command(db_migrator + ' -o set_version' + cfggen_namespace_option)

    if os.path.isfile('/etc/sonic/acl.json'):
        run_command("acl-loader update full /etc/sonic/acl.json", display_cmd=True)

    # We first run "systemctl reset-failed" to remove the "failed"
    # status from all services before we attempt to restart them
    _reset_failed_services()
    #FIXME: After config DB daemon is implemented, we'll no longer need to restart every service.
    log_info("'load_minigraph' restarting services...")
    _restart_services()
    click.echo("Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.")


#
# 'hostname' command
#
@config.command('hostname')
@click.argument('new_hostname', metavar='<new_hostname>', required=True)
def hostname(new_hostname):
    """Change device hostname without impacting the traffic."""

    config_db = ConfigDBConnector()
    config_db.connect()
    config_db.mod_entry('DEVICE_METADATA' , 'localhost', {"hostname" : new_hostname})
    try:
        command = "service hostname-config restart"
        run_command(command, display_cmd=True)
    except SystemExit as e:
        click.echo("Restarting hostname-config  service failed with error {}".format(e))
        raise
    click.echo("Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.")

#
# 'portchannel' group ('config portchannel ...')
#
@config.group(cls=AbbreviationGroup)
@click.pass_context
def portchannel(ctx):
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

@portchannel.command('add')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.option('--min-links', default=0, type=int)
@click.option('--fallback', default='false')
@click.pass_context
def add_portchannel(ctx, portchannel_name, min_links, fallback):
    """Add port channel"""
    db = ctx.obj['db']
    fvs = {'admin_status': 'up',
           'mtu': '9100'}
    if min_links != 0:
        fvs['min_links'] = str(min_links)
    if fallback != 'false':
        fvs['fallback'] = 'true'
    db.set_entry('PORTCHANNEL', portchannel_name, fvs)

@portchannel.command('del')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.pass_context
def remove_portchannel(ctx, portchannel_name):
    """Remove port channel"""
    db = ctx.obj['db']
    db.set_entry('PORTCHANNEL', portchannel_name, None)

@portchannel.group(cls=AbbreviationGroup, name='member')
@click.pass_context
def portchannel_member(ctx):
    pass

@portchannel_member.command('add')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.argument('port_name', metavar='<port_name>', required=True)
@click.pass_context
def add_portchannel_member(ctx, portchannel_name, port_name):
    """Add member to port channel"""
    db = ctx.obj['db']
    db.set_entry('PORTCHANNEL_MEMBER', (portchannel_name, port_name),
            {'NULL': 'NULL'})

@portchannel_member.command('del')
@click.argument('portchannel_name', metavar='<portchannel_name>', required=True)
@click.argument('port_name', metavar='<port_name>', required=True)
@click.pass_context
def del_portchannel_member(ctx, portchannel_name, port_name):
    """Remove member from portchannel"""
    db = ctx.obj['db']
    db.set_entry('PORTCHANNEL_MEMBER', (portchannel_name, port_name), None)
    db.set_entry('PORTCHANNEL_MEMBER', portchannel_name + '|' + port_name, None)


#
# 'mirror_session' group ('config mirror_session ...')
#
@config.group(cls=AbbreviationGroup, name='mirror_session')
def mirror_session():
    pass

@mirror_session.command()
@click.argument('session_name', metavar='<session_name>', required=True)
@click.argument('src_ip', metavar='<src_ip>', required=True)
@click.argument('dst_ip', metavar='<dst_ip>', required=True)
@click.argument('dscp', metavar='<dscp>', required=True)
@click.argument('ttl', metavar='<ttl>', required=True)
@click.argument('gre_type', metavar='[gre_type]', required=False)
@click.argument('queue', metavar='[queue]', required=False)
@click.option('--policer')
def add(session_name, src_ip, dst_ip, dscp, ttl, gre_type, queue, policer):
    """
    Add mirror session
    """
    config_db = ConfigDBConnector()
    config_db.connect()

    session_info = {
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "dscp": dscp,
            "ttl": ttl
            }

    if policer is not None:
        session_info['policer'] = policer

    if gre_type is not None:
        session_info['gre_type'] = gre_type

    if queue is not None:
        session_info['queue'] = queue

    config_db.set_entry("MIRROR_SESSION", session_name, session_info)

@mirror_session.command()
@click.argument('session_name', metavar='<session_name>', required=True)
def remove(session_name):
    """
    Delete mirror session
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    config_db.set_entry("MIRROR_SESSION", session_name, None)

#
# 'pfcwd' group ('config pfcwd ...')
#
@config.group(cls=AbbreviationGroup)
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
        config pfcwd start --action drop ports all detection-time 400 --restoration-time 400
    """
    cmd = "pfcwd start"

    if action:
        cmd += " --action {}".format(action)

    if ports:
        ports = set(ports) - set(['ports', 'detection-time'])
        cmd += " ports {}".format(' '.join(ports))

    if detection_time:
        cmd += " detection-time {}".format(detection_time)

    if restoration_time:
        cmd += " --restoration-time {}".format(restoration_time)

    run_command(cmd, display_cmd=verbose)

@pfcwd.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def stop(verbose):
    """ Stop PFC watchdog """

    cmd = "pfcwd stop"

    run_command(cmd, display_cmd=verbose)

@pfcwd.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('poll_interval', type=click.IntRange(100, 3000))
def interval(poll_interval, verbose):
    """ Set PFC watchdog counter polling interval (ms) """

    cmd = "pfcwd interval {}".format(poll_interval)

    run_command(cmd, display_cmd=verbose)

@pfcwd.command('counter_poll')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('counter_poll', type=click.Choice(['enable', 'disable']))
def counter_poll(counter_poll, verbose):
    """ Enable/disable counter polling """

    cmd = "pfcwd counter_poll {}".format(counter_poll)

    run_command(cmd, display_cmd=verbose)

@pfcwd.command('big_red_switch')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.argument('big_red_switch', type=click.Choice(['enable', 'disable']))
def big_red_switch(big_red_switch, verbose):
    """ Enable/disable BIG_RED_SWITCH mode """

    cmd = "pfcwd big_red_switch {}".format(big_red_switch)

    run_command(cmd, display_cmd=verbose)

@pfcwd.command('start_default')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def start_default(verbose):
    """ Start PFC WD by default configurations  """

    cmd = "pfcwd start_default"

    run_command(cmd, display_cmd=verbose)

#
# 'qos' group ('config qos ...')
#
@config.group(cls=AbbreviationGroup)
@click.pass_context
def qos(ctx):
    """QoS-related configuration tasks"""
    pass

@qos.command('clear')
def clear():
    """Clear QoS configuration"""
    log_info("'qos clear' executing...")
    _clear_qos()

@qos.command('reload')
def reload():
    """Reload QoS configuration"""
    log_info("'qos reload' executing...")
    _clear_qos()
    platform = _get_platform()
    hwsku = _get_hwsku()
    buffer_template_file = os.path.join('/usr/share/sonic/device/', platform, hwsku, 'buffers.json.j2')
    if os.path.isfile(buffer_template_file):
        command = "{} -d -t {} >/tmp/buffers.json".format(SONIC_CFGGEN_PATH, buffer_template_file)
        run_command(command, display_cmd=True)

        qos_template_file = os.path.join('/usr/share/sonic/device/', platform, hwsku, 'qos.json.j2')
        sonic_version_file = os.path.join('/etc/sonic/', 'sonic_version.yml')
        if os.path.isfile(qos_template_file):
            command = "{} -d -t {} -y {} >/tmp/qos.json".format(SONIC_CFGGEN_PATH, qos_template_file, sonic_version_file)
            run_command(command, display_cmd=True)

            # Apply the configurations only when both buffer and qos configuration files are presented
            command = "{} -j /tmp/buffers.json --write-to-db".format(SONIC_CFGGEN_PATH)
            run_command(command, display_cmd=True)
            command = "{} -j /tmp/qos.json --write-to-db".format(SONIC_CFGGEN_PATH)
            run_command(command, display_cmd=True)
        else:
            click.secho('QoS definition template not found at {}'.format(qos_template_file), fg='yellow')
    else:
        click.secho('Buffer definition template not found at {}'.format(buffer_template_file), fg='yellow')

#
# 'warm_restart' group ('config warm_restart ...')
#
@config.group(cls=AbbreviationGroup, name='warm_restart')
@click.pass_context
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def warm_restart(ctx, redis_unix_socket_path):
    """warm_restart-related configuration tasks"""
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path
    config_db = ConfigDBConnector(**kwargs)
    config_db.connect(wait_for_init=False)

    # warm restart enable/disable config is put in stateDB, not persistent across cold reboot, not saved to config_DB.json file
    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)
    TABLE_NAME_SEPARATOR = '|'
    prefix = 'WARM_RESTART_ENABLE_TABLE' + TABLE_NAME_SEPARATOR
    ctx.obj = {'db': config_db, 'state_db': state_db, 'prefix': prefix}

@warm_restart.command('enable')
@click.argument('module', metavar='<module>', default='system', required=False, type=click.Choice(["system", "swss", "bgp", "teamd"]))
@click.pass_context
def warm_restart_enable(ctx, module):
    state_db = ctx.obj['state_db']
    prefix = ctx.obj['prefix']
    _hash = '{}{}'.format(prefix, module)
    state_db.set(state_db.STATE_DB, _hash, 'enable', 'true')
    state_db.close(state_db.STATE_DB)

@warm_restart.command('disable')
@click.argument('module', metavar='<module>', default='system', required=False, type=click.Choice(["system", "swss", "bgp", "teamd"]))
@click.pass_context
def warm_restart_enable(ctx, module):
    state_db = ctx.obj['state_db']
    prefix = ctx.obj['prefix']
    _hash = '{}{}'.format(prefix, module)
    state_db.set(state_db.STATE_DB, _hash, 'enable', 'false')
    state_db.close(state_db.STATE_DB)

@warm_restart.command('neighsyncd_timer')
@click.argument('seconds', metavar='<seconds>', required=True, type=int)
@click.pass_context
def warm_restart_neighsyncd_timer(ctx, seconds):
    db = ctx.obj['db']
    if seconds not in range(1,9999):
        ctx.fail("neighsyncd warm restart timer must be in range 1-9999")
    db.mod_entry('WARM_RESTART', 'swss', {'neighsyncd_timer': seconds})

@warm_restart.command('bgp_timer')
@click.argument('seconds', metavar='<seconds>', required=True, type=int)
@click.pass_context
def warm_restart_bgp_timer(ctx, seconds):
    db = ctx.obj['db']
    if seconds not in range(1,3600):
        ctx.fail("bgp warm restart timer must be in range 1-3600")
    db.mod_entry('WARM_RESTART', 'bgp', {'bgp_timer': seconds})

@warm_restart.command('teamsyncd_timer')
@click.argument('seconds', metavar='<seconds>', required=True, type=int)
@click.pass_context
def warm_restart_teamsyncd_timer(ctx, seconds):
    db = ctx.obj['db']
    if seconds not in range(1,3600):
        ctx.fail("teamsyncd warm restart timer must be in range 1-3600")
    db.mod_entry('WARM_RESTART', 'teamd', {'teamsyncd_timer': seconds})

@warm_restart.command('bgp_eoiu')
@click.argument('enable', metavar='<enable>', default='true', required=False, type=click.Choice(["true", "false"]))
@click.pass_context
def warm_restart_bgp_eoiu(ctx, enable):
    db = ctx.obj['db']
    db.mod_entry('WARM_RESTART', 'bgp', {'bgp_eoiu': enable})

#
# 'vlan' group ('config vlan ...')
#
@config.group(cls=AbbreviationGroup)
@click.pass_context
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def vlan(ctx, redis_unix_socket_path):
    """VLAN-related configuration tasks"""
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path
    config_db = ConfigDBConnector(**kwargs)
    config_db.connect(wait_for_init=False)
    ctx.obj = {'db': config_db}

@vlan.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.pass_context
def add_vlan(ctx, vid):
    if vid >= 1 and vid <= 4094:
        db = ctx.obj['db']
        vlan = 'Vlan{}'.format(vid)
        if len(db.get_entry('VLAN', vlan)) != 0:
            ctx.fail("{} already exists".format(vlan))
        db.set_entry('VLAN', vlan, {'vlanid': vid})
    else :
        ctx.fail("Invalid VLAN ID {} (1-4094)".format(vid))

@vlan.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.pass_context
def del_vlan(ctx, vid):
    """Delete VLAN"""
    log_info("'vlan del {}' executing...".format(vid))
    db = ctx.obj['db']
    keys = [ (k, v) for k, v in db.get_table('VLAN_MEMBER') if k == 'Vlan{}'.format(vid) ]
    for k in keys:
        db.set_entry('VLAN_MEMBER', k, None)
    db.set_entry('VLAN', 'Vlan{}'.format(vid), None)


#
# 'member' group ('config vlan member ...')
#
@vlan.group(cls=AbbreviationGroup, name='member')
@click.pass_context
def vlan_member(ctx):
    pass


@vlan_member.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('-u', '--untagged', is_flag=True)
@click.pass_context
def add_vlan_member(ctx, vid, interface_name, untagged):
    """Add VLAN member"""
    log_info("'vlan member add {} {}' executing...".format(vid, interface_name))
    db = ctx.obj['db']
    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.get_entry('VLAN', vlan_name)
    interface_table = db.get_table('INTERFACE')

    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if len(vlan) == 0:
        ctx.fail("{} doesn't exist".format(vlan_name))
    members = vlan.get('members', [])
    if interface_name in members:
        if get_interface_naming_mode() == "alias":
            interface_name = interface_name_to_alias(interface_name)
            if interface_name is None:
                ctx.fail("'interface_name' is None!")
            ctx.fail("{} is already a member of {}".format(interface_name,
                                                        vlan_name))
        else:
            ctx.fail("{} is already a member of {}".format(interface_name,
                                                        vlan_name))
    for entry in interface_table:
        if (interface_name == entry[0]):
            ctx.fail("{} is a L3 interface!".format(interface_name))
            
    members.append(interface_name)
    vlan['members'] = members
    db.set_entry('VLAN', vlan_name, vlan)
    db.set_entry('VLAN_MEMBER', (vlan_name, interface_name), {'tagging_mode': "untagged" if untagged else "tagged" })


@vlan_member.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def del_vlan_member(ctx, vid, interface_name):
    """Delete VLAN member"""
    log_info("'vlan member del {} {}' executing...".format(vid, interface_name))
    db = ctx.obj['db']
    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.get_entry('VLAN', vlan_name)

    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if len(vlan) == 0:
        ctx.fail("{} doesn't exist".format(vlan_name))
    members = vlan.get('members', [])
    if interface_name not in members:
        if get_interface_naming_mode() == "alias":
            interface_name = interface_name_to_alias(interface_name)
            if interface_name is None:
                ctx.fail("'interface_name' is None!")
            ctx.fail("{} is not a member of {}".format(interface_name, vlan_name))
        else:
            ctx.fail("{} is not a member of {}".format(interface_name, vlan_name))
    members.remove(interface_name)
    if len(members) == 0:
        del vlan['members']
    else:
        vlan['members'] = members
    db.set_entry('VLAN', vlan_name, vlan)
    db.set_entry('VLAN_MEMBER', (vlan_name, interface_name), None)

def mvrf_restart_services():
    """Restart interfaces-config service and NTP service when mvrf is changed"""
    """
    When mvrf is enabled, eth0 should be moved to mvrf; when it is disabled,
    move it back to default vrf. Restarting the "interfaces-config" service
    will recreate the /etc/network/interfaces file and restart the
    "networking" service that takes care of the eth0 movement.
    NTP service should also be restarted to rerun the NTP service with or
    without "cgexec" accordingly.
    """
    cmd="service ntp stop"
    os.system (cmd)
    cmd="systemctl restart interfaces-config"
    os.system (cmd)
    cmd="service ntp start"
    os.system (cmd)

def vrf_add_management_vrf(config_db):
    """Enable management vrf in config DB"""

    entry = config_db.get_entry('MGMT_VRF_CONFIG', "vrf_global")
    if entry and entry['mgmtVrfEnabled'] == 'true' :
        click.echo("ManagementVRF is already Enabled.")
        return None
    config_db.mod_entry('MGMT_VRF_CONFIG',"vrf_global",{"mgmtVrfEnabled": "true"})
    mvrf_restart_services()

def vrf_delete_management_vrf(config_db):
    """Disable management vrf in config DB"""

    entry = config_db.get_entry('MGMT_VRF_CONFIG', "vrf_global")
    if not entry or entry['mgmtVrfEnabled'] == 'false' :
        click.echo("ManagementVRF is already Disabled.")
        return None
    config_db.mod_entry('MGMT_VRF_CONFIG',"vrf_global",{"mgmtVrfEnabled": "false"})
    mvrf_restart_services()

@config.group(cls=AbbreviationGroup)
@click.pass_context
def snmpagentaddress(ctx):
    """SNMP agent listening IP address, port, vrf configuration"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

@snmpagentaddress.command('add')
@click.argument('agentip', metavar='<SNMP AGENT LISTENING IP Address>', required=True)
@click.option('-p', '--port', help="SNMP AGENT LISTENING PORT")
@click.option('-v', '--vrf', help="VRF Name mgmt/DataVrfName/None")
@click.pass_context
def add_snmp_agent_address(ctx, agentip, port, vrf):
    """Add the SNMP agent listening IP:Port%Vrf configuration"""

    #Construct SNMP_AGENT_ADDRESS_CONFIG table key in the format ip|<port>|<vrf>
    key = agentip+'|'
    if port:
        key = key+port   
    key = key+'|'
    if vrf:
        key = key+vrf
    config_db = ctx.obj['db']
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

@config.group(cls=AbbreviationGroup)
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
        config_db.mod_entry('SNMP_TRAP_CONFIG',"v1TrapDest",{"DestIp": serverip, "DestPort": port, "vrf": vrf, "Community": comm})
    elif ver == "2":
        config_db.mod_entry('SNMP_TRAP_CONFIG',"v2TrapDest",{"DestIp": serverip, "DestPort": port, "vrf": vrf, "Community": comm})
    else:
        config_db.mod_entry('SNMP_TRAP_CONFIG',"v3TrapDest",{"DestIp": serverip, "DestPort": port, "vrf": vrf, "Community": comm})

    cmd="systemctl restart snmp"
    os.system (cmd)

@snmptrap.command('del')
@click.argument('ver', metavar='<SNMP Version>', type=click.Choice(['1', '2', '3']), required=True)
@click.pass_context
def delete_snmptrap_server(ctx, ver):
    """Delete the SNMP Trap server configuration"""

    config_db = ctx.obj['db']
    if ver == "1":
        config_db.mod_entry('SNMP_TRAP_CONFIG',"v1TrapDest",None)
    elif ver == "2":
        config_db.mod_entry('SNMP_TRAP_CONFIG',"v2TrapDest",None)
    else:
        config_db.mod_entry('SNMP_TRAP_CONFIG',"v3TrapDest",None)
    cmd="systemctl restart snmp"
    os.system (cmd)

@vlan.group(cls=AbbreviationGroup, name='dhcp_relay')
@click.pass_context
def vlan_dhcp_relay(ctx):
    pass

@vlan_dhcp_relay.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('dhcp_relay_destination_ip', metavar='<dhcp_relay_destination_ip>', required=True)
@click.pass_context
def add_vlan_dhcp_relay_destination(ctx, vid, dhcp_relay_destination_ip):
    """ Add a destination IP address to the VLAN's DHCP relay """
    if not is_ipaddress(dhcp_relay_destination_ip):
        ctx.fail('Invalid IP address')
    db = ctx.obj['db']
    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.get_entry('VLAN', vlan_name)

    if len(vlan) == 0:
        ctx.fail("{} doesn't exist".format(vlan_name))
    dhcp_relay_dests = vlan.get('dhcp_servers', [])
    if dhcp_relay_destination_ip in dhcp_relay_dests:
        click.echo("{} is already a DHCP relay destination for {}".format(dhcp_relay_destination_ip, vlan_name))
        return
    else:
        dhcp_relay_dests.append(dhcp_relay_destination_ip)
        vlan['dhcp_servers'] = dhcp_relay_dests
        db.set_entry('VLAN', vlan_name, vlan)
        click.echo("Added DHCP relay destination address {} to {}".format(dhcp_relay_destination_ip, vlan_name))
        try:
            click.echo("Restarting DHCP relay service...")
            run_command("systemctl restart dhcp_relay", display_cmd=False)
        except SystemExit as e:
            ctx.fail("Restart service dhcp_relay failed with error {}".format(e))

@vlan_dhcp_relay.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('dhcp_relay_destination_ip', metavar='<dhcp_relay_destination_ip>', required=True)
@click.pass_context
def del_vlan_dhcp_relay_destination(ctx, vid, dhcp_relay_destination_ip):
    """ Remove a destination IP address from the VLAN's DHCP relay """
    if not is_ipaddress(dhcp_relay_destination_ip):
        ctx.fail('Invalid IP address')
    db = ctx.obj['db']
    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.get_entry('VLAN', vlan_name)

    if len(vlan) == 0:
        ctx.fail("{} doesn't exist".format(vlan_name))
    dhcp_relay_dests = vlan.get('dhcp_servers', [])
    if dhcp_relay_destination_ip in dhcp_relay_dests:
        dhcp_relay_dests.remove(dhcp_relay_destination_ip)
        if len(dhcp_relay_dests) == 0:
            del vlan['dhcp_servers']
        else:
            vlan['dhcp_servers'] = dhcp_relay_dests
        db.set_entry('VLAN', vlan_name, vlan)
        click.echo("Removed DHCP relay destination address {} from {}".format(dhcp_relay_destination_ip, vlan_name))
        try:
            click.echo("Restarting DHCP relay service...")
            run_command("systemctl restart dhcp_relay", display_cmd=False)
        except SystemExit as e:
            ctx.fail("Restart service dhcp_relay failed with error {}".format(e))
    else:
        ctx.fail("{} is not a DHCP relay destination for {}".format(dhcp_relay_destination_ip, vlan_name))

#
# 'bgp' group ('config bgp ...')
#

@config.group(cls=AbbreviationGroup)
def bgp():
    """BGP-related configuration tasks"""
    pass

#
# 'shutdown' subgroup ('config bgp shutdown ...')
#

@bgp.group(cls=AbbreviationGroup)
def shutdown():
    """Shut down BGP session(s)"""
    pass

@config.group(cls=AbbreviationGroup)
def kdump():
    """ Configure kdump """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

@kdump.command()
def disable():
    """Disable kdump operation"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"enabled": "false"})
        run_command("sonic-kdump-config --disable")

@kdump.command()
def enable():
    """Enable kdump operation"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"enabled": "true"})
        run_command("sonic-kdump-config --enable")

@kdump.command()
@click.argument('kdump_memory', metavar='<kdump_memory>', required=True)
def memory(kdump_memory):
    """Set memory allocated for kdump capture kernel"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"memory": kdump_memory})
        run_command("sonic-kdump-config --memory %s" % kdump_memory)

@kdump.command('num-dumps')
@click.argument('kdump_num_dumps', metavar='<kdump_num_dumps>', required=True, type=int)
def num_dumps(kdump_num_dumps):
    """Set max number of dump files for kdump"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"num_dumps": kdump_num_dumps})
        run_command("sonic-kdump-config --num_dumps %d" % kdump_num_dumps)

# 'all' subcommand
@shutdown.command()
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Shut down all BGP sessions"""
    log_info("'bgp shutdown all' executing...")
    bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses()
    for ipaddress in bgp_neighbor_ip_list:
        _change_bgp_session_status_by_addr(ipaddress, 'down', verbose)

# 'neighbor' subcommand
@shutdown.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Shut down BGP session by neighbor IP address or hostname"""
    log_info("'bgp shutdown neighbor {}' executing...".format(ipaddr_or_hostname))
    _change_bgp_session_status(ipaddr_or_hostname, 'down', verbose)

@bgp.group(cls=AbbreviationGroup)
def startup():
    """Start up BGP session(s)"""
    pass

# 'all' subcommand
@startup.command()
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Start up all BGP sessions"""
    log_info("'bgp startup all' executing...")
    bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses()
    for ipaddress in bgp_neighbor_ip_list:
        _change_bgp_session_status(ipaddress, 'up', verbose)

# 'neighbor' subcommand
@startup.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Start up BGP session by neighbor IP address or hostname"""
    log_info("'bgp startup neighbor {}' executing...".format(ipaddr_or_hostname))
    _change_bgp_session_status(ipaddr_or_hostname, 'up', verbose)

#
# 'remove' subgroup ('config bgp remove ...')
#

@bgp.group(cls=AbbreviationGroup)
def remove():
    "Remove BGP neighbor configuration from the device"
    pass

@remove.command('neighbor')
@click.argument('neighbor_ip_or_hostname', metavar='<neighbor_ip_or_hostname>', required=True)
def remove_neighbor(neighbor_ip_or_hostname):
    """Deletes BGP neighbor configuration of given hostname or ip from devices"""
    _remove_bgp_neighbor_config(neighbor_ip_or_hostname)

#
# 'interface' group ('config interface ...')
#

@config.group(cls=AbbreviationGroup)
@click.pass_context
def interface(ctx):
    """Interface-related configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {}
    ctx.obj['config_db'] = config_db

#
# 'startup' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def startup(ctx, interface_name):
    """Start up interface"""

    config_db = ctx.obj['config_db']
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    log_info("'interface startup {}' executing...".format(interface_name))

    if interface_name.startswith("Ethernet"):
        if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
            config_db.mod_entry("VLAN_SUB_INTERFACE", interface_name, {"admin_status": "up"})
        else:
            config_db.mod_entry("PORT", interface_name, {"admin_status": "up"})
    elif interface_name.startswith("PortChannel"):
        if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
            config_db.mod_entry("VLAN_SUB_INTERFACE", interface_name, {"admin_status": "up"})
        else:
            config_db.mod_entry("PORTCHANNEL", interface_name, {"admin_status": "up"})
#
# 'shutdown' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def shutdown(ctx, interface_name):
    """Shut down interface"""
    log_info("'interface shutdown {}' executing...".format(interface_name))
    config_db = ctx.obj['config_db']
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    if interface_name.startswith("Ethernet"):
        if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
            config_db.mod_entry("VLAN_SUB_INTERFACE", interface_name, {"admin_status": "down"})
        else:
            config_db.mod_entry("PORT", interface_name, {"admin_status": "down"})
    elif interface_name.startswith("PortChannel"):
        if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
            config_db.mod_entry("VLAN_SUB_INTERFACE", interface_name, {"admin_status": "down"})
        else:
            config_db.mod_entry("PORTCHANNEL", interface_name, {"admin_status": "down"})

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
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    log_info("'interface speed {} {}' executing...".format(interface_name, interface_speed))

    command = "portconfig -p {} -s {}".format(interface_name, interface_speed)
    if verbose:
        command += " -vv"
    run_command(command, display_cmd=verbose)

def _get_all_mgmtinterface_keys():
    """Returns list of strings containing mgmt interface keys 
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    return config_db.get_table('MGMT_INTERFACE').keys()

def mgmt_ip_restart_services():
    """Restart the required services when mgmt inteface IP address is changed"""
    """
    Whenever the eth0 IP address is changed, restart the "interfaces-config"
    service which regenerates the /etc/network/interfaces file and restarts
    the networking service to make the new/null IP address effective for eth0.
    "ntp-config" service should also be restarted based on the new
    eth0 IP address since the ntp.conf (generated from ntp.conf.j2) is
    made to listen on that particular eth0 IP address or reset it back.
    """
    cmd="systemctl restart interfaces-config"
    os.system (cmd)
    cmd="systemctl restart ntp-config"
    os.system (cmd)

#
# 'mtu' subcommand
#

@interface.command()
@click.pass_context
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_mtu', metavar='<interface_mtu>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def mtu(ctx, interface_name, interface_mtu, verbose):
    """Set interface mtu"""
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    command = "portconfig -p {} -m {}".format(interface_name, interface_mtu)
    if verbose:
        command += " -vv"
    run_command(command, display_cmd=verbose)

#
# 'ip' subgroup ('config interface ip ...')
#

@interface.group(cls=AbbreviationGroup)
@click.pass_context
def ip(ctx):
    """Add or remove IP address"""
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
    config_db = ctx.obj["config_db"]
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    try:
        ipaddress.ip_network(unicode(ip_addr), strict=False)

        if interface_name == 'eth0':

            # Configuring more than 1 IPv4 or more than 1 IPv6 address fails.
            # Allow only one IPv4 and only one IPv6 address to be configured for IPv6.
            # If a row already exist, overwrite it (by doing delete and add).
            mgmtintf_key_list = _get_all_mgmtinterface_keys()

            for key in mgmtintf_key_list:
                # For loop runs for max 2 rows, once for IPv4 and once for IPv6.
                # No need to capture the exception since the ip_addr is already validated earlier
                ip_input = ipaddress.ip_interface(ip_addr)
                current_ip = ipaddress.ip_interface(key[1])
                if (ip_input.version == current_ip.version):
                    # If user has configured IPv4/v6 address and the already available row is also IPv4/v6, delete it here.
                    config_db.set_entry("MGMT_INTERFACE", ("eth0", key[1]), None)

            # Set the new row with new value
            if not gw:
                config_db.set_entry("MGMT_INTERFACE", (interface_name, ip_addr), {"NULL": "NULL"})
            else:
                config_db.set_entry("MGMT_INTERFACE", (interface_name, ip_addr), {"gwaddr": gw})
            mgmt_ip_restart_services()

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
        config_db.set_entry(table_name, (interface_name, ip_addr), {"NULL": "NULL"})
    except ValueError:
        ctx.fail("'ip_addr' is not valid.")

#
# 'del' subcommand
#

@ip.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument("ip_addr", metavar="<ip_addr>", required=True)
@click.pass_context
def remove(ctx, interface_name, ip_addr):
    """Remove an IP address from the interface"""
    config_db = ctx.obj["config_db"]
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    try:
        ipaddress.ip_network(unicode(ip_addr), strict=False)

        if interface_name == 'eth0':
            config_db.set_entry("MGMT_INTERFACE", (interface_name, ip_addr), None)
            mgmt_ip_restart_services()
            return

        table_name = get_interface_table_name(interface_name)
        if table_name == "":
            ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")
        config_db.set_entry(table_name, (interface_name, ip_addr), None)
        interface_dependent = interface_ipaddr_dependent_on_interface(config_db, interface_name)
        if len(interface_dependent) == 0 and is_interface_bind_to_vrf(config_db, interface_name) is False:
            config_db.set_entry(table_name, interface_name, None)

        command = "ip neigh flush dev {} {}".format(interface_name, ip_addr)
        run_command(command)
    except ValueError:
        ctx.fail("'ip_addr' is not valid.")

#
# 'transceiver' subgroup ('config interface transceiver ...')
#

@interface.group(cls=AbbreviationGroup)
@click.pass_context
def transceiver(ctx):
    """SFP transceiver configuration"""
    pass

#
# 'lpmode' subcommand ('config interface transceiver lpmode ...')
#

@transceiver.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('state', metavar='(enable|disable)', type=click.Choice(['enable', 'disable']))
@click.pass_context
def lpmode(ctx, interface_name, state):
    """Enable/disable low-power mode for SFP transceiver module"""
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    cmd = "sudo sfputil lpmode {} {}".format("on" if state == "enable" else "off", interface_name)
    run_command(cmd)

#
# 'reset' subcommand ('config interface reset ...')
#

@transceiver.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def reset(ctx, interface_name):
    """Reset SFP transceiver module"""
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    if interface_name_is_valid(interface_name) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    cmd = "sudo sfputil reset {}".format(interface_name)
    run_command(cmd)

#
# 'vrf' subgroup ('config interface vrf ...')
#


@interface.group(cls=AbbreviationGroup)
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
    config_db = ctx.obj["config_db"]
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")
    if is_interface_bind_to_vrf(config_db, interface_name) is True and \
        config_db.get_entry(table_name, interface_name).get('vrf_name') == vrf_name:
        return
    # Clean ip addresses if interface configured
    interface_dependent = interface_ipaddr_dependent_on_interface(config_db, interface_name)
    for interface_del in interface_dependent:
        config_db.set_entry(table_name, interface_del, None)
    config_db.set_entry(table_name, interface_name, None)
    # When config_db del entry and then add entry with same key, the DEL will lost.
    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)
    _hash = '{}{}'.format('INTERFACE_TABLE|', interface_name)
    while state_db.get(state_db.STATE_DB, _hash, "state") == "ok":
        time.sleep(0.01)
    state_db.close(state_db.STATE_DB)
    config_db.set_entry(table_name, interface_name, {"vrf_name": vrf_name})

#
# 'unbind' subcommand
#

@vrf.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def unbind(ctx, interface_name):
    """Unbind the interface to VRF"""
    config_db = ctx.obj["config_db"]
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("interface is None!")

    table_name = get_interface_table_name(interface_name)
    if table_name == "":
        ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")
    if is_interface_bind_to_vrf(config_db, interface_name) is False:
        return
    interface_dependent = interface_ipaddr_dependent_on_interface(config_db, interface_name)
    for interface_del in interface_dependent:
        config_db.set_entry(table_name, interface_del, None)
    config_db.set_entry(table_name, interface_name, None)


#
# 'vrf' group ('config vrf ...')
#

@config.group(cls=AbbreviationGroup, name='vrf')
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
    config_db = ctx.obj['config_db']
    if not vrf_name.startswith("Vrf") and not (vrf_name == 'mgmt') and not (vrf_name == 'management'):
        ctx.fail("'vrf_name' is not start with Vrf, mgmt or management!")
    if len(vrf_name) > 15:
        ctx.fail("'vrf_name' is too long!")
    if (vrf_name == 'mgmt' or vrf_name == 'management'):
        vrf_add_management_vrf(config_db)
    else:
        config_db.set_entry('VRF', vrf_name, {"NULL": "NULL"})

@vrf.command('del')
@click.argument('vrf_name', metavar='<vrf_name>', required=True)
@click.pass_context
def del_vrf(ctx, vrf_name):
    """Del vrf"""
    config_db = ctx.obj['config_db']
    if not vrf_name.startswith("Vrf") and not (vrf_name == 'mgmt') and not (vrf_name == 'management'):
        ctx.fail("'vrf_name' is not start with Vrf, mgmt or management!")
    if len(vrf_name) > 15:
        ctx.fail("'vrf_name' is too long!")
    if (vrf_name == 'mgmt' or vrf_name == 'management'):
        vrf_delete_management_vrf(config_db)
    else:
        del_interface_bind_to_vrf(config_db, vrf_name)
        config_db.set_entry('VRF', vrf_name, None)


#
# 'route' group ('config route ...')
#

@config.group(cls=AbbreviationGroup)
@click.pass_context
def route(ctx):
    """route-related configuration tasks"""
    pass

@route.command('add',context_settings={"ignore_unknown_options":True})
@click.argument('command_str', metavar='prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>', nargs=-1, type=click.Path())
@click.pass_context
def add_route(ctx, command_str):
    """Add route command"""
    if len(command_str) < 4 or len(command_str) > 9:
        ctx.fail("argument is not in pattern prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>!")
    if "prefix" not in command_str:
        ctx.fail("argument is incomplete, prefix not found!")
    if "nexthop" not in command_str:
        ctx.fail("argument is incomplete, nexthop not found!")
    for i in range(0,len(command_str)):
        if "nexthop" == command_str[i]:
            prefix_str = command_str[:i]
            nexthop_str = command_str[i:]
    vrf_name = ""
    cmd = 'sudo vtysh -c "configure terminal" -c "ip route'
    if prefix_str:
        if len(prefix_str) == 2:
            prefix_mask = prefix_str[1]
            cmd += ' {}'.format(prefix_mask)
        elif len(prefix_str) == 4:
            vrf_name = prefix_str[2]
            prefix_mask = prefix_str[3]
            cmd += ' {}'.format(prefix_mask)
        else:
            ctx.fail("prefix is not in pattern!")
    if nexthop_str:
        if len(nexthop_str) == 2:
            ip = nexthop_str[1]
            if vrf_name == "":
                cmd += ' {}'.format(ip)
            else:
                cmd += ' {} vrf {}'.format(ip, vrf_name)
        elif len(nexthop_str) == 3:
            dev_name = nexthop_str[2]
            if vrf_name == "":
                cmd += ' {}'.format(dev_name)
            else:
                cmd += ' {} vrf {}'.format(dev_name, vrf_name)
        elif len(nexthop_str) == 4:
            vrf_name_dst = nexthop_str[2]
            ip = nexthop_str[3]
            if vrf_name == "":
                cmd += ' {} nexthop-vrf {}'.format(ip, vrf_name_dst)
            else:
                cmd += ' {} vrf {} nexthop-vrf {}'.format(ip, vrf_name, vrf_name_dst)
        else:
            ctx.fail("nexthop is not in pattern!")
    cmd += '"'
    run_command(cmd)

@route.command('del',context_settings={"ignore_unknown_options":True})
@click.argument('command_str', metavar='prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>', nargs=-1, type=click.Path())
@click.pass_context
def del_route(ctx, command_str):
    """Del route command"""
    if len(command_str) < 4 or len(command_str) > 9:
        ctx.fail("argument is not in pattern prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>!")
    if "prefix" not in command_str:
        ctx.fail("argument is incomplete, prefix not found!")
    if "nexthop" not in command_str:
        ctx.fail("argument is incomplete, nexthop not found!")
    for i in range(0,len(command_str)):
        if "nexthop" == command_str[i]:
            prefix_str = command_str[:i]
            nexthop_str = command_str[i:]
    vrf_name = ""
    cmd = 'sudo vtysh -c "configure terminal" -c "no ip route'
    if prefix_str:
        if len(prefix_str) == 2:
            prefix_mask = prefix_str[1]
            cmd += ' {}'.format(prefix_mask)
        elif len(prefix_str) == 4:
            vrf_name = prefix_str[2]
            prefix_mask = prefix_str[3]
            cmd += ' {}'.format(prefix_mask)
        else:
            ctx.fail("prefix is not in pattern!")
    if nexthop_str:
        if len(nexthop_str) == 2:
            ip = nexthop_str[1]
            if vrf_name == "":
                cmd += ' {}'.format(ip)
            else:
                cmd += ' {} vrf {}'.format(ip, vrf_name)
        elif len(nexthop_str) == 3:
            dev_name = nexthop_str[2]
            if vrf_name == "":
                cmd += ' {}'.format(dev_name)
            else:
                cmd += ' {} vrf {}'.format(dev_name, vrf_name)
        elif len(nexthop_str) == 4:
            vrf_name_dst = nexthop_str[2]
            ip = nexthop_str[3]
            if vrf_name == "":
                cmd += ' {} nexthop-vrf {}'.format(ip, vrf_name_dst)
            else:
                cmd += ' {} vrf {} nexthop-vrf {}'.format(ip, vrf_name, vrf_name_dst)
        else:
            ctx.fail("nexthop is not in pattern!")
    cmd += '"'
    run_command(cmd)

#
# 'acl' group ('config acl ...')
#

@config.group(cls=AbbreviationGroup)
def acl():
    """ACL-related configuration tasks"""
    pass

#
# 'add' subgroup ('config acl add ...')
#

@acl.group(cls=AbbreviationGroup)
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

#
# 'table' subcommand ('config acl add table ...')
#

@add.command()
@click.argument("table_name", metavar="<table_name>")
@click.argument("table_type", metavar="<table_type>")
@click.option("-d", "--description")
@click.option("-p", "--ports")
@click.option("-s", "--stage", type=click.Choice(["ingress", "egress"]), default="ingress")
def table(table_name, table_type, description, ports, stage):
    """
    Add ACL table
    """
    config_db = ConfigDBConnector()
    config_db.connect()

    table_info = {"type": table_type}

    if description:
        table_info["policy_desc"] = description
    else:
        table_info["policy_desc"] = table_name

    if ports:
        table_info["ports@"] = ports
    else:
        table_info["ports@"] = ",".join(get_acl_bound_ports())

    table_info["stage"] = stage

    config_db.set_entry("ACL_TABLE", table_name, table_info)

#
# 'remove' subgroup ('config acl remove ...')
#

@acl.group(cls=AbbreviationGroup)
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

@acl.group(cls=AbbreviationGroup)
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
    log_info("'acl update full {}' executing...".format(file_name))
    command = "acl-loader update full {}".format(file_name)
    run_command(command)


#
# 'incremental' subcommand
#

@update.command()
@click.argument('file_name', required=True)
def incremental(file_name):
    """Incremental update of ACL rule configuration."""
    log_info("'acl update incremental {}' executing...".format(file_name))
    command = "acl-loader update incremental {}".format(file_name)
    run_command(command)


#
# 'dropcounters' group ('config dropcounters ...')
#

@config.group(cls=AbbreviationGroup)
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

    run_command(command, display_cmd=verbose)


#
# 'delete' subcommand ('config dropcounters delete')
#
@dropcounters.command()
@click.argument("counter_name", type=str, required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def delete(counter_name, verbose):
    """Delete an existing drop counter"""
    command = "dropconfig -c uninstall -n {}".format(counter_name)
    run_command(command, display_cmd=verbose)


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
    run_command(command, display_cmd=verbose)


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
    run_command(command, display_cmd=verbose)


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
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def ecn(profile, rmax, rmin, ymax, ymin, gmax, gmin, verbose):
    """ECN-related configuration tasks"""
    log_info("'ecn -profile {}' executing...".format(profile))
    command = "ecnconfig -p %s" % profile
    if rmax is not None: command += " -rmax %d" % rmax
    if rmin is not None: command += " -rmin %d" % rmin
    if ymax is not None: command += " -ymax %d" % ymax
    if ymin is not None: command += " -ymin %d" % ymin
    if gmax is not None: command += " -gmax %d" % gmax
    if gmin is not None: command += " -gmin %d" % gmin
    if verbose: command += " -vv"
    run_command(command, display_cmd=verbose)


#
# 'pfc' group ('config interface pfc ...')
#

@interface.group(cls=AbbreviationGroup)
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
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")

    run_command("pfc config asymmetric {0} {1}".format(status, interface_name))

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
    if get_interface_naming_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            ctx.fail("'interface_name' is None!")
    
    run_command("pfc config priority {0} {1} {2}".format(status, interface_name, priority))
    
#
# 'platform' group ('config platform ...')
#

@config.group(cls=AbbreviationGroup)
def platform():
    """Platform-related configuration tasks"""

if asic_type == 'mellanox':
    platform.add_command(mlnx.mlnx)

# 'firmware' subgroup ("config platform firmware ...")
@platform.group(cls=AbbreviationGroup)
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
    cmd = "fwutil install {}".format(" ".join(args))

    try:
        subprocess.check_call(cmd, shell=True)
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
    cmd = "fwutil update {}".format(" ".join(args))

    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

#
# 'watermark' group ("show watermark telemetry interval")
#

@config.group(cls=AbbreviationGroup)
def watermark():
    """Configure watermark """
    pass

@watermark.group(cls=AbbreviationGroup)
def telemetry():
    """Configure watermark telemetry"""
    pass

@telemetry.command()
@click.argument('interval', required=True)
def interval(interval):
    """Configure watermark telemetry interval"""
    command = 'watermarkcfg --config-interval ' + interval
    run_command(command)


#
# 'interface_naming_mode' subgroup ('config interface_naming_mode ...')
#

@config.group(cls=AbbreviationGroup, name='interface_naming_mode')
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

@config.group(cls=AbbreviationGroup)
def ztp():
    """ Configure Zero Touch Provisioning """
    if os.path.isfile('/usr/bin/ztp') is False:
        exit("ZTP feature unavailable in this image version")

    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

@ztp.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='ZTP will be restarted. You may lose switch data and connectivity, continue?')
@click.argument('run', required=False, type=click.Choice(["run"]))
def run(run):
    """Restart ZTP of the device."""
    command = "ztp run -y"
    run_command(command, display_cmd=True)

@ztp.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Active ZTP session will be stopped and disabled, continue?')
@click.argument('disable', required=False, type=click.Choice(["disable"]))
def disable(disable):
    """Administratively Disable ZTP."""
    command = "ztp disable -y"
    run_command(command, display_cmd=True)

@ztp.command()
@click.argument('enable', required=False, type=click.Choice(["enable"]))
def enable(enable):
    """Administratively Enable ZTP."""
    command = "ztp enable"
    run_command(command, display_cmd=True)

#
# 'syslog' group ('config syslog ...')
#
@config.group(cls=AbbreviationGroup, name='syslog')
@click.pass_context
def syslog_group(ctx):
    """Syslog server configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

@syslog_group.command('add')
@click.argument('syslog_ip_address', metavar='<syslog_ip_address>', required=True)
@click.pass_context
def add_syslog_server(ctx, syslog_ip_address):
    """ Add syslog server IP """
    if not is_ipaddress(syslog_ip_address):
        ctx.fail('Invalid ip address')
    db = ctx.obj['db']
    syslog_servers = db.get_table("SYSLOG_SERVER")
    if syslog_ip_address in syslog_servers:
        click.echo("Syslog server {} is already configured".format(syslog_ip_address))
        return
    else:
        db.set_entry('SYSLOG_SERVER', syslog_ip_address, {'NULL': 'NULL'})
        click.echo("Syslog server {} added to configuration".format(syslog_ip_address))
        try:
            click.echo("Restarting rsyslog-config service...")
            run_command("systemctl restart rsyslog-config", display_cmd=False)
        except SystemExit as e:
            ctx.fail("Restart service rsyslog-config failed with error {}".format(e))

@syslog_group.command('del')
@click.argument('syslog_ip_address', metavar='<syslog_ip_address>', required=True)
@click.pass_context
def del_syslog_server(ctx, syslog_ip_address):
    """ Delete syslog server IP """
    if not is_ipaddress(syslog_ip_address):
        ctx.fail('Invalid IP address')
    db = ctx.obj['db']
    syslog_servers = db.get_table("SYSLOG_SERVER")
    if syslog_ip_address in syslog_servers:
        db.set_entry('SYSLOG_SERVER', '{}'.format(syslog_ip_address), None)
        click.echo("Syslog server {} removed from configuration".format(syslog_ip_address))
    else:
        ctx.fail("Syslog server {} is not configured.".format(syslog_ip_address))
    try:
        click.echo("Restarting rsyslog-config service...")
        run_command("systemctl restart rsyslog-config", display_cmd=False)
    except SystemExit as e:
        ctx.fail("Restart service rsyslog-config failed with error {}".format(e))

#
# 'ntp' group ('config ntp ...')
#
@config.group(cls=AbbreviationGroup)
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
    if not is_ipaddress(ntp_ip_address):
        ctx.fail('Invalid ip address')
    db = ctx.obj['db']
    ntp_servers = db.get_table("NTP_SERVER")
    if ntp_ip_address in ntp_servers:
        click.echo("NTP server {} is already configured".format(ntp_ip_address))
        return
    else: 
        db.set_entry('NTP_SERVER', ntp_ip_address, {'NULL': 'NULL'})
        click.echo("NTP server {} added to configuration".format(ntp_ip_address))
        try:
            click.echo("Restarting ntp-config service...")
            run_command("systemctl restart ntp-config", display_cmd=False)
        except SystemExit as e:
            ctx.fail("Restart service ntp-config failed with error {}".format(e))

@ntp.command('del')
@click.argument('ntp_ip_address', metavar='<ntp_ip_address>', required=True)
@click.pass_context
def del_ntp_server(ctx, ntp_ip_address):
    """ Delete NTP server IP """
    if not is_ipaddress(ntp_ip_address):
        ctx.fail('Invalid IP address')
    db = ctx.obj['db']
    ntp_servers = db.get_table("NTP_SERVER")
    if ntp_ip_address in ntp_servers:
        db.set_entry('NTP_SERVER', '{}'.format(ntp_ip_address), None)
        click.echo("NTP server {} removed from configuration".format(ntp_ip_address))
    else: 
        ctx.fail("NTP server {} is not configured.".format(ntp_ip_address))
    try:
        click.echo("Restarting ntp-config service...")
        run_command("systemctl restart ntp-config", display_cmd=False)
    except SystemExit as e:
        ctx.fail("Restart service ntp-config failed with error {}".format(e))

#
# 'sflow' group ('config sflow ...')
#
@config.group(cls=AbbreviationGroup)
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
    config_db = ctx.obj['db']
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'up'}}
    else:
        sflow_tbl['global']['admin_state'] = 'up'

    config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])

    try:
        proc = subprocess.Popen("systemctl is-active sflow", shell=True, stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
    except SystemExit as e:
        ctx.fail("Unable to check sflow status {}".format(e))

    if out != "active":
        log_info("sflow service is not enabled. Starting sflow docker...")
        run_command("sudo systemctl enable sflow")
        run_command("sudo systemctl start sflow")

#
# 'sflow' command ('config sflow disable')
#
@sflow.command()
@click.pass_context
def disable(ctx):
    """Disable sFlow"""
    config_db = ctx.obj['db']
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}
    else:
        sflow_tbl['global']['admin_state'] = 'down'

    config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])

#
# 'sflow' command ('config sflow polling-interval ...')
#
@sflow.command('polling-interval')
@click.argument('interval',  metavar='<polling_interval>', required=True,
                type=int)
@click.pass_context
def polling_int(ctx, interval):
    """Set polling-interval for counter-sampling (0 to disable)"""
    if interval not in range(5, 301) and interval != 0:
        click.echo("Polling interval must be between 5-300 (0 to disable)")

    config_db = ctx.obj['db']
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}

    sflow_tbl['global']['polling_interval'] = interval
    config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])

def is_valid_sample_rate(rate):
    return rate in range(256, 8388608 + 1)


#
# 'sflow interface' group
#
@sflow.group(cls=AbbreviationGroup)
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
    if not interface_name_is_valid(ifname) and ifname != 'all':
        click.echo("Invalid interface name")
        return

    config_db = ctx.obj['db']
    intf_dict = config_db.get_table('SFLOW_SESSION')

    if intf_dict and ifname in intf_dict.keys():
        intf_dict[ifname]['admin_state'] = 'up'
        config_db.mod_entry('SFLOW_SESSION', ifname, intf_dict[ifname])
    else:
        config_db.mod_entry('SFLOW_SESSION', ifname, {'admin_state': 'up'})

#
# 'sflow' command ('config sflow interface disable  ...')
#
@interface.command()
@click.argument('ifname', metavar='<interface_name>', required=True, type=str)
@click.pass_context
def disable(ctx, ifname):
    if not interface_name_is_valid(ifname) and ifname != 'all':
        click.echo("Invalid interface name")
        return

    config_db = ctx.obj['db']
    intf_dict = config_db.get_table('SFLOW_SESSION')

    if intf_dict and ifname in intf_dict.keys():
        intf_dict[ifname]['admin_state'] = 'down'
        config_db.mod_entry('SFLOW_SESSION', ifname, intf_dict[ifname])
    else:
        config_db.mod_entry('SFLOW_SESSION', ifname,
                            {'admin_state': 'down'})

#
# 'sflow' command ('config sflow interface sample-rate  ...')
#
@interface.command('sample-rate')
@click.argument('ifname', metavar='<interface_name>', required=True, type=str)
@click.argument('rate', metavar='<sample_rate>', required=True, type=int)
@click.pass_context
def sample_rate(ctx, ifname, rate):
    if not interface_name_is_valid(ifname) and ifname != 'all':
        click.echo('Invalid interface name')
        return
    if not is_valid_sample_rate(rate):
        click.echo('Error: Sample rate must be between 256 and 8388608')
        return

    config_db = ctx.obj['db']
    sess_dict = config_db.get_table('SFLOW_SESSION')

    if sess_dict and ifname in sess_dict.keys():
        sess_dict[ifname]['sample_rate'] = rate
        config_db.mod_entry('SFLOW_SESSION', ifname, sess_dict[ifname])
    else:
        config_db.mod_entry('SFLOW_SESSION', ifname, {'sample_rate': rate})


#
# 'sflow collector' group
#
@sflow.group(cls=AbbreviationGroup)
@click.pass_context
def collector(ctx):
    """Add/Delete a sFlow collector"""
    pass

def is_valid_collector_info(name, ip, port):
    if len(name) > 16:
        click.echo("Collector name must not exceed 16 characters")
        return False

    if port not in range(0, 65535 + 1):
        click.echo("Collector port number must be between 0 and 65535")
        return False

    if not is_ipaddress(ip):
        click.echo("Invalid IP address")
        return False

    return True

#
# 'sflow' command ('config sflow collector add ...')
#
@collector.command()
@click.option('--port', required=False, type=int, default=6343,
              help='Collector port number')
@click.argument('name', metavar='<collector_name>', required=True)
@click.argument('ipaddr', metavar='<IPv4/v6_address>', required=True)
@click.pass_context
def add(ctx, name, ipaddr, port):
    """Add a sFlow collector"""
    ipaddr = ipaddr.lower()

    if not is_valid_collector_info(name, ipaddr, port):
        return

    config_db = ctx.obj['db']
    collector_tbl = config_db.get_table('SFLOW_COLLECTOR')

    if (collector_tbl and name not in collector_tbl.keys() and len(collector_tbl) == 2):
        click.echo("Only 2 collectors can be configured, please delete one")
        return

    config_db.mod_entry('SFLOW_COLLECTOR', name,
                        {"collector_ip": ipaddr,  "collector_port": port})
    return

#
# 'sflow' command ('config sflow collector del ...')
#
@collector.command('del')
@click.argument('name', metavar='<collector_name>', required=True)
@click.pass_context
def del_collector(ctx, name):
    """Delete a sFlow collector"""
    config_db = ctx.obj['db']
    collector_tbl = config_db.get_table('SFLOW_COLLECTOR')

    if name not in collector_tbl.keys():
        click.echo("Collector: {} not configured".format(name))
        return

    config_db.mod_entry('SFLOW_COLLECTOR', name, None)

#
# 'sflow agent-id' group
#
@sflow.group(cls=AbbreviationGroup, name='agent-id')
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
    if ifname not in netifaces.interfaces():
        click.echo("Invalid interface name")
        return

    config_db = ctx.obj['db']
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}

    if 'agent_id' in sflow_tbl['global'].keys():
        click.echo("Agent already configured. Please delete it first.")
        return

    sflow_tbl['global']['agent_id'] = ifname
    config_db.mod_entry('SFLOW', 'global', sflow_tbl['global'])

#
# 'sflow' command ('config sflow agent-id del')
#
@agent_id.command('del')
@click.pass_context
def delete(ctx):
    """Delete sFlow agent information"""
    config_db = ctx.obj['db']
    sflow_tbl = config_db.get_table('SFLOW')

    if not sflow_tbl:
        sflow_tbl = {'global': {'admin_state': 'down'}}

    if 'agent_id' not in sflow_tbl['global'].keys():
        click.echo("sFlow agent not configured.")
        return

    sflow_tbl['global'].pop('agent_id')
    config_db.set_entry('SFLOW', 'global', sflow_tbl['global'])

#
# 'feature' command ('config feature name state')
# 
@config.command('feature')
@click.argument('name', metavar='<feature-name>', required=True)
@click.argument('state', metavar='<feature-state>', required=True, type=click.Choice(["enabled", "disabled"]))
def feature_status(name, state):
    """ Configure status of feature"""
    config_db = ConfigDBConnector()
    config_db.connect()
    status_data = config_db.get_entry('FEATURE', name)

    if not status_data:
        click.echo(" Feature '{}' doesn't exist".format(name))
        return

    config_db.mod_entry('FEATURE', name, {'status': state})

#
# 'container' group ('config container ...')
#
@config.group(cls=AbbreviationGroup, name='container', invoke_without_command=False)
def container():
    """Modify configuration of containers"""
    pass

#
# 'feature' group ('config container feature ...')
#
@container.group(cls=AbbreviationGroup, name='feature', invoke_without_command=False)
def feature():
    """Modify configuration of container features"""
    pass

#
# 'autorestart' subcommand ('config container feature autorestart ...')
#
@feature.command(name='autorestart', short_help="Configure the status of autorestart feature for specific container")
@click.argument('container_name', metavar='<container_name>', required=True)
@click.argument('autorestart_status', metavar='<autorestart_status>', required=True, type=click.Choice(["enabled", "disabled"]))
def autorestart(container_name, autorestart_status):
    config_db = ConfigDBConnector()
    config_db.connect()
    container_feature_table = config_db.get_table('CONTAINER_FEATURE')
    if not container_feature_table:
        click.echo("Unable to retrieve container feature table from Config DB.")
        return

    if not container_feature_table.has_key(container_name):
        click.echo("Unable to retrieve features for container '{}'".format(container_name))
        return

    config_db.mod_entry('CONTAINER_FEATURE', container_name, {'auto_restart': autorestart_status})

if __name__ == '__main__':
    config()
