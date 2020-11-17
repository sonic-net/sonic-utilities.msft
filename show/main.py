import json
import netaddr
import os
import subprocess
import sys

import click
import netifaces
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from natsort import natsorted
from pkg_resources import parse_version
from sonic_py_common import device_info, multi_asic
from swsssdk import ConfigDBConnector
from swsscommon.swsscommon import SonicV2Connector
from tabulate import tabulate
from utilities_common.db import Db

from . import chassis_modules
from . import feature
from . import fgnhg
from . import interfaces
from . import kube
from . import mlnx
from . import vlan
from . import system_health


# Global Variables
PLATFORM_JSON = 'platform.json'
HWSKU_JSON = 'hwsku.json'
PORT_STR = "Ethernet"

VLAN_SUB_INTERFACE_SEPARATOR = '.'

# To be enhanced. Routing-stack information should be collected from a global
# location (configdb?), so that we prevent the continous execution of this
# bash oneliner. To be revisited once routing-stack info is tracked somewhere.
def get_routing_stack():
    command = "sudo docker ps | grep bgp | awk '{print$2}' | cut -d'-' -f3 | cut -d':' -f1 | head -n 1"

    try:
        proc = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                shell=True,
                                text=True,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        result = stdout.rstrip('\n')

    except OSError as e:
        raise OSError("Cannot detect routing-stack")

    return (result)


# Global Routing-Stack variable
routing_stack = get_routing_stack()

# Read given JSON file
def readJsonFile(fileName):
    try:
        with open(fileName) as f:
            result = json.load(f)
    except Exception as e:
        click.echo(str(e))
        raise click.Abort()
    return result

def run_command(command, display_cmd=False, return_cmd=False):
    if display_cmd:
        click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))

    # No conversion needed for intfutil commands as it already displays
    # both SONiC interface name and alias name for all interfaces.
    if clicommon.get_interface_naming_mode() == "alias" and not command.startswith("intfutil"):
        clicommon.run_command_in_alias_mode(command)
        raise sys.exit(0)

    proc = subprocess.Popen(command, shell=True, text=True, stdout=subprocess.PIPE)

    while True:
        if return_cmd:
            output = proc.communicate()[0].decode("utf-8")
            return output
        output = proc.stdout.readline()
        if output == "" and proc.poll() is not None:
            break
        if output:
            click.echo(output.rstrip('\n'))

    rc = proc.poll()
    if rc != 0:
        sys.exit(rc)

# Global class instance for SONiC interface name to alias conversion
iface_alias_converter = clicommon.InterfaceAliasConverter()



def connect_config_db():
    """
    Connects to config_db
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    return config_db



CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

#
# 'cli' group (root group)
#

# This is our entrypoint - the main "show" command
# TODO: Consider changing function name to 'show' for better understandability
@click.group(cls=clicommon.AliasedGroup, context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cli(ctx):
    """SONiC command line - 'show' command"""

    ctx.obj = Db()


# Add groups from other modules
cli.add_command(chassis_modules.chassis_modules)
cli.add_command(feature.feature)
cli.add_command(fgnhg.fgnhg)
cli.add_command(interfaces.interfaces)
cli.add_command(kube.kubernetes)
cli.add_command(vlan.vlan)
cli.add_command(system_health.system_health)

#
# 'vrf' command ("show vrf")
#

def get_interface_bind_to_vrf(config_db, vrf_name):
    """Get interfaces belong to vrf
    """
    tables = ['INTERFACE', 'PORTCHANNEL_INTERFACE', 'VLAN_INTERFACE', 'LOOPBACK_INTERFACE']
    data = []
    for table_name in tables:
        interface_dict = config_db.get_table(table_name)
        if interface_dict:
            for interface in interface_dict:
                if 'vrf_name' in interface_dict[interface] and vrf_name == interface_dict[interface]['vrf_name']:
                    data.append(interface)
    return data

@cli.command()
@click.argument('vrf_name', required=False)
def vrf(vrf_name):
    """Show vrf config"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['VRF', 'Interfaces']
    body = []
    vrf_dict = config_db.get_table('VRF')
    if vrf_dict:
        vrfs = []
        if vrf_name is None:
            vrfs = list(vrf_dict.keys())
        elif vrf_name in vrf_dict:
            vrfs = [vrf_name]
        for vrf in vrfs:
            intfs = get_interface_bind_to_vrf(config_db, vrf)
            if len(intfs) == 0:
                body.append([vrf, ""])
            else:
                body.append([vrf, intfs[0]])
                for intf in intfs[1:]:
                    body.append(["", intf])
    click.echo(tabulate(body, header))

#
# 'arp' command ("show arp")
#

@cli.command()
@click.argument('ipaddress', required=False)
@click.option('-if', '--iface')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def arp(ipaddress, iface, verbose):
    """Show IP ARP table"""
    cmd = "nbrshow -4"

    if ipaddress is not None:
        cmd += " -ip {}".format(ipaddress)

    if iface is not None:
        if clicommon.get_interface_naming_mode() == "alias":
            if not ((iface.startswith("PortChannel")) or
                    (iface.startswith("eth"))):
                iface = iface_alias_converter.alias_to_name(iface)

        cmd += " -if {}".format(iface)

    run_command(cmd, display_cmd=verbose)

#
# 'ndp' command ("show ndp")
#

@cli.command()
@click.argument('ip6address', required=False)
@click.option('-if', '--iface')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def ndp(ip6address, iface, verbose):
    """Show IPv6 Neighbour table"""
    cmd = "nbrshow -6"

    if ip6address is not None:
        cmd += " -ip {}".format(ip6address)

    if iface is not None:
        cmd += " -if {}".format(iface)

    run_command(cmd, display_cmd=verbose)

def is_mgmt_vrf_enabled(ctx):
    """Check if management VRF is enabled"""
    if ctx.invoked_subcommand is None:
        cmd = 'sonic-cfggen -d --var-json "MGMT_VRF_CONFIG"'

        p = subprocess.Popen(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try :
            mvrf_dict = json.loads(p.stdout.read())
        except ValueError:
            print("MGMT_VRF_CONFIG is not present.")
            return False

        # if the mgmtVrfEnabled attribute is configured, check the value
        # and return True accordingly.
        if 'mgmtVrfEnabled' in mvrf_dict['vrf_global']:
            if (mvrf_dict['vrf_global']['mgmtVrfEnabled'] == "true"):
                #ManagementVRF is enabled. Return True.
                return True

    return False

#
# 'mgmt-vrf' group ("show mgmt-vrf ...")
#

@cli.group('mgmt-vrf', invoke_without_command=True)
@click.argument('routes', required=False)
@click.pass_context
def mgmt_vrf(ctx,routes):
    """Show management VRF attributes"""

    if is_mgmt_vrf_enabled(ctx) is False:
        click.echo("\nManagementVRF : Disabled")
        return
    else:
        if routes is None:
            click.echo("\nManagementVRF : Enabled")
            click.echo("\nManagement VRF interfaces in Linux:")
            cmd = "ip -d link show mgmt"
            run_command(cmd)
            cmd = "ip link show vrf mgmt"
            run_command(cmd)
        else:
            click.echo("\nRoutes in Management VRF Routing Table:")
            cmd = "ip route show table 5000"
            run_command(cmd)

#
# 'management_interface' group ("show management_interface ...")
#

@cli.group(name='management_interface', cls=clicommon.AliasedGroup)
def management_interface():
    """Show management interface parameters"""
    pass

# 'address' subcommand ("show management_interface address")
@management_interface.command()
def address ():
    """Show IP address configured for management interface"""

    config_db = ConfigDBConnector()
    config_db.connect()

    # Fetching data from config_db for MGMT_INTERFACE
    mgmt_ip_data = config_db.get_table('MGMT_INTERFACE')
    for key in natsorted(list(mgmt_ip_data.keys())):
        click.echo("Management IP address = {0}".format(key[1]))
        click.echo("Management Network Default Gateway = {0}".format(mgmt_ip_data[key]['gwaddr']))

#
# 'snmpagentaddress' group ("show snmpagentaddress ...")
#

@cli.group('snmpagentaddress', invoke_without_command=True)
@click.pass_context
def snmpagentaddress (ctx):
    """Show SNMP agent listening IP address configuration"""
    config_db = ConfigDBConnector()
    config_db.connect()
    agenttable = config_db.get_table('SNMP_AGENT_ADDRESS_CONFIG')

    header = ['ListenIP', 'ListenPort', 'ListenVrf']
    body = []
    for agent in agenttable:
        body.append([agent[0], agent[1], agent[2]])
    click.echo(tabulate(body, header))

#
# 'snmptrap' group ("show snmptrap ...")
#

@cli.group('snmptrap', invoke_without_command=True)
@click.pass_context
def snmptrap (ctx):
    """Show SNMP agent Trap server configuration"""
    config_db = ConfigDBConnector()
    config_db.connect()
    traptable = config_db.get_table('SNMP_TRAP_CONFIG')

    header = ['Version', 'TrapReceiverIP', 'Port', 'VRF', 'Community']
    body = []
    for row in traptable:
        if row == "v1TrapDest":
            ver=1
        elif row == "v2TrapDest":
            ver=2
        else:
            ver=3
        body.append([ver, traptable[row]['DestIp'], traptable[row]['DestPort'], traptable[row]['vrf'], traptable[row]['Community']])
    click.echo(tabulate(body, header))

#
# 'subinterfaces' group ("show subinterfaces ...")
#

@cli.group(cls=clicommon.AliasedGroup)
def subinterfaces():
    """Show details of the sub port interfaces"""
    pass

# 'subinterfaces' subcommand ("show subinterfaces status")
@subinterfaces.command()
@click.argument('subinterfacename', type=str, required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def status(subinterfacename, verbose):
    """Show sub port interface status information"""
    cmd = "intfutil -c status"

    if subinterfacename is not None:
        sub_intf_sep_idx = subinterfacename.find(VLAN_SUB_INTERFACE_SEPARATOR)
        if sub_intf_sep_idx == -1:
            print("Invalid sub port interface name")
            return

        if clicommon.get_interface_naming_mode() == "alias":
            subinterfacename = iface_alias_converter.alias_to_name(subinterfacename)

        cmd += " -i {}".format(subinterfacename)
    else:
        cmd += " -i subport"
    run_command(cmd, display_cmd=verbose)

#
# 'pfc' group ("show pfc ...")
#

@cli.group(cls=clicommon.AliasedGroup)
def pfc():
    """Show details of the priority-flow-control (pfc) """
    pass

# 'counters' subcommand ("show interfaces pfccounters")
@pfc.command()
@multi_asic_util.multi_asic_click_options
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counters(namespace, display, verbose):
    """Show pfc counters"""

    cmd = "pfcstat -s {}".format(display)
    if namespace is not None:
        cmd += " -n {}".format(namespace)

    run_command(cmd, display_cmd=verbose)

@pfc.command()
@click.argument('interface', type=click.STRING, required=False)
def priority(interface):
    """Show pfc priority"""
    cmd = 'pfc show priority'
    if interface is not None and clicommon.get_interface_naming_mode() == "alias":
        interface = iface_alias_converter.alias_to_name(interface)

    if interface is not None:
        cmd += ' {0}'.format(interface)

    run_command(cmd)

@pfc.command()
@click.argument('interface', type=click.STRING, required=False)
def asymmetric(interface):
    """Show asymmetric pfc"""
    cmd = 'pfc show asymmetric'
    if interface is not None and clicommon.get_interface_naming_mode() == "alias":
        interface = iface_alias_converter.alias_to_name(interface)

    if interface is not None:
        cmd += ' {0}'.format(interface)

    run_command(cmd)

# 'pfcwd' subcommand ("show pfcwd...")
@cli.group(cls=clicommon.AliasedGroup)
def pfcwd():
    """Show details of the pfc watchdog """
    pass

@pfcwd.command()
@multi_asic_util.multi_asic_click_options
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def config(namespace, display, verbose):
    """Show pfc watchdog config"""

    cmd = "pfcwd show config -d {}".format(display)
    if namespace is not None:
        cmd += " -n {}".format(namespace)

    run_command(cmd, display_cmd=verbose)

@pfcwd.command()
@multi_asic_util.multi_asic_click_options
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def stats(namespace, display, verbose):
    """Show pfc watchdog stats"""

    cmd = "pfcwd show stats -d {}".format(display)
    if namespace is not None:
        cmd += " -n {}".format(namespace)

    run_command(cmd, display_cmd=verbose)

#
# 'watermark' group ("show watermark telemetry interval")
#

@cli.group(cls=clicommon.AliasedGroup)
def watermark():
    """Show details of watermark """
    pass

@watermark.group()
def telemetry():
    """Show watermark telemetry info"""
    pass

@telemetry.command('interval')
def show_tm_interval():
    """Show telemetry interval"""
    command = 'watermarkcfg --show-interval'
    run_command(command)


#
# 'queue' group ("show queue ...")
#

@cli.group(cls=clicommon.AliasedGroup)
def queue():
    """Show details of the queues """
    pass

# 'counters' subcommand ("show queue counters")
@queue.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counters(interfacename, verbose):
    """Show queue counters"""

    cmd = "queuestat"

    if interfacename is not None:
        if clicommon.get_interface_naming_mode() == "alias":
            interfacename = iface_alias_converter.alias_to_name(interfacename)

    if interfacename is not None:
        cmd += " -p {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)

#
# 'watermarks' subgroup ("show queue watermarks ...")
#

@queue.group()
def watermark():
    """Show user WM for queues"""
    pass

# 'unicast' subcommand ("show queue watermarks unicast")
@watermark.command('unicast')
def wm_q_uni():
    """Show user WM for unicast queues"""
    command = 'watermarkstat -t q_shared_uni'
    run_command(command)

# 'multicast' subcommand ("show queue watermarks multicast")
@watermark.command('multicast')
def wm_q_multi():
    """Show user WM for multicast queues"""
    command = 'watermarkstat -t q_shared_multi'
    run_command(command)

#
# 'persistent-watermarks' subgroup ("show queue persistent-watermarks ...")
#

@queue.group(name='persistent-watermark')
def persistent_watermark():
    """Show persistent WM for queues"""
    pass

# 'unicast' subcommand ("show queue persistent-watermarks unicast")
@persistent_watermark.command('unicast')
def pwm_q_uni():
    """Show persistent WM for unicast queues"""
    command = 'watermarkstat -p -t q_shared_uni'
    run_command(command)

# 'multicast' subcommand ("show queue persistent-watermarks multicast")
@persistent_watermark.command('multicast')
def pwm_q_multi():
    """Show persistent WM for multicast queues"""
    command = 'watermarkstat -p -t q_shared_multi'
    run_command(command)


#
# 'priority-group' group ("show priority-group ...")
#

@cli.group(name='priority-group', cls=clicommon.AliasedGroup)
def priority_group():
    """Show details of the PGs """

@priority_group.group()
def watermark():
    """Show priority-group user WM"""
    pass

@watermark.command('headroom')
def wm_pg_headroom():
    """Show user headroom WM for pg"""
    command = 'watermarkstat -t pg_headroom'
    run_command(command)

@watermark.command('shared')
def wm_pg_shared():
    """Show user shared WM for pg"""
    command = 'watermarkstat -t pg_shared'
    run_command(command)

@priority_group.group(name='persistent-watermark')
def persistent_watermark():
    """Show priority-group persistent WM"""
    pass

@persistent_watermark.command('headroom')
def pwm_pg_headroom():
    """Show persistent headroom WM for pg"""
    command = 'watermarkstat -p -t pg_headroom'
    run_command(command)

@persistent_watermark.command('shared')
def pwm_pg_shared():
    """Show persistent shared WM for pg"""
    command = 'watermarkstat -p -t pg_shared'
    run_command(command)


#
# 'buffer_pool' group ("show buffer_pool ...")
#

@cli.group(name='buffer_pool', cls=clicommon.AliasedGroup)
def buffer_pool():
    """Show details of the buffer pools"""

@buffer_pool.command('watermark')
def wm_buffer_pool():
    """Show user WM for buffer pools"""
    command = 'watermarkstat -t buffer_pool'
    run_command(command)

@buffer_pool.command('persistent-watermark')
def pwm_buffer_pool():
    """Show persistent WM for buffer pools"""
    command = 'watermarkstat -p -t buffer_pool'
    run_command(command)


#
# 'mac' command ("show mac ...")
#

@cli.command()
@click.option('-v', '--vlan')
@click.option('-p', '--port')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def mac(vlan, port, verbose):
    """Show MAC (FDB) entries"""

    cmd = "fdbshow"

    if vlan is not None:
        cmd += " -v {}".format(vlan)

    if port is not None:
        cmd += " -p {}".format(port)

    run_command(cmd, display_cmd=verbose)

#
# 'show route-map' command ("show route-map")
#

@cli.command('route-map')
@click.argument('route_map_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def route_map(route_map_name, verbose):
    """show route-map"""
    cmd = 'sudo vtysh -c "show route-map'
    if route_map_name is not None:
        cmd += ' {}'.format(route_map_name)
    cmd += '"'
    run_command(cmd, display_cmd=verbose)

#
# 'ip' group ("show ip ...")
#

# This group houses IP (i.e., IPv4) commands and subgroups
@cli.group(cls=clicommon.AliasedGroup)
def ip():
    """Show IP (IPv4) commands"""
    pass


#
# get_if_admin_state
#
# Given an interface name, return its admin state reported by the kernel.
#
def get_if_admin_state(iface):
    admin_file = "/sys/class/net/{0}/flags"

    try:
        state_file = open(admin_file.format(iface), "r")
    except IOError as e:
        print("Error: unable to open file: %s" % str(e))
        return "error"

    content = state_file.readline().rstrip()
    flags = int(content, 16)

    if flags & 0x1:
        return "up"
    else:
        return "down"


#
# get_if_oper_state
#
# Given an interface name, return its oper state reported by the kernel.
#
def get_if_oper_state(iface):
    oper_file = "/sys/class/net/{0}/carrier"

    try:
        state_file = open(oper_file.format(iface), "r")
    except IOError as e:
        print("Error: unable to open file: %s" % str(e))
        return "error"

    oper_state = state_file.readline().rstrip()
    if oper_state == "1":
        return "up"
    else:
        return "down"


#
# get_if_master
#
# Given an interface name, return its master reported by the kernel.
#
def get_if_master(iface):
    oper_file = "/sys/class/net/{0}/master"

    if os.path.exists(oper_file.format(iface)):
        real_path = os.path.realpath(oper_file.format(iface))
        return os.path.basename(real_path)
    else:
        return ""


#
# 'show ip interfaces' command
#
# Display all interfaces with master, an IPv4 address, admin/oper states, their BGP neighbor name and peer ip.
# Addresses from all scopes are included. Interfaces with no addresses are
# excluded.
#
@ip.command()
def interfaces():
    """Show interfaces IPv4 address"""
    header = ['Interface', 'Master', 'IPv4 address/mask', 'Admin/Oper', 'BGP Neighbor', 'Neighbor IP']
    data = []
    bgp_peer = get_bgp_peer()

    interfaces = natsorted(netifaces.interfaces())

    for iface in interfaces:
        ipaddresses = netifaces.ifaddresses(iface)

        if netifaces.AF_INET in ipaddresses:
            ifaddresses = []
            neighbor_info = []
            for ipaddr in ipaddresses[netifaces.AF_INET]:
                neighbor_name = 'N/A'
                neighbor_ip = 'N/A'
                local_ip = str(ipaddr['addr'])
                netmask = netaddr.IPAddress(ipaddr['netmask']).netmask_bits()
                ifaddresses.append(["", local_ip + "/" + str(netmask)])
                try:
                    neighbor_name = bgp_peer[local_ip][0]
                    neighbor_ip = bgp_peer[local_ip][1]
                except Exception:
                    pass
                neighbor_info.append([neighbor_name, neighbor_ip])

            if len(ifaddresses) > 0:
                admin = get_if_admin_state(iface)
                if admin == "up":
                    oper = get_if_oper_state(iface)
                else:
                    oper = "down"
                master = get_if_master(iface)
                if clicommon.get_interface_naming_mode() == "alias":
                    iface = iface_alias_converter.name_to_alias(iface)

                data.append([iface, master, ifaddresses[0][1], admin + "/" + oper, neighbor_info[0][0], neighbor_info[0][1]])
                neighbor_info.pop(0)

                for ifaddr in ifaddresses[1:]:
                    data.append(["", "", ifaddr[1], admin + "/" + oper, neighbor_info[0][0], neighbor_info[0][1]])
                    neighbor_info.pop(0)

    print(tabulate(data, header, tablefmt="simple", stralign='left', missingval=""))

# get bgp peering info
def get_bgp_peer():
    """
    collects local and bgp neighbor ip along with device name in below format
    {
     'local_addr1':['neighbor_device1_name', 'neighbor_device1_ip'],
     'local_addr2':['neighbor_device2_name', 'neighbor_device2_ip']
     }
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    bgp_peer = {}
    bgp_neighbor_tables = ['BGP_NEIGHBOR', 'BGP_INTERNAL_NEIGHBOR']

    for table in bgp_neighbor_tables:
        data = config_db.get_table(table)
        for neighbor_ip in data:
            local_addr = data[neighbor_ip]['local_addr']
            neighbor_name = data[neighbor_ip]['name']
            bgp_peer.setdefault(local_addr, [neighbor_name, neighbor_ip])

    return bgp_peer

#
# 'route' subcommand ("show ip route")
#

@ip.command()
@click.argument('args', metavar='[IPADDRESS] [vrf <vrf_name>] [...]', nargs=-1, required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def route(args, verbose):
    """Show IP (IPv4) routing table"""
    cmd = 'sudo vtysh -c "show ip route'

    for arg in args:
        cmd += " " + str(arg)

    cmd += '"'

    run_command(cmd, display_cmd=verbose)

#
# 'prefix-list' subcommand ("show ip prefix-list")
#

@ip.command('prefix-list')
@click.argument('prefix_list_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def prefix_list(prefix_list_name, verbose):
    """show ip prefix-list"""
    cmd = 'sudo vtysh -c "show ip prefix-list'
    if prefix_list_name is not None:
        cmd += ' {}'.format(prefix_list_name)
    cmd += '"'
    run_command(cmd, display_cmd=verbose)


# 'protocol' command
@ip.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def protocol(verbose):
    """Show IPv4 protocol information"""
    cmd = 'sudo vtysh -c "show ip protocol"'
    run_command(cmd, display_cmd=verbose)


#
# 'ipv6' group ("show ipv6 ...")
#

# This group houses IPv6-related commands and subgroups
@cli.group(cls=clicommon.AliasedGroup)
def ipv6():
    """Show IPv6 commands"""
    pass

#
# 'prefix-list' subcommand ("show ipv6 prefix-list")
#

@ipv6.command('prefix-list')
@click.argument('prefix_list_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def prefix_list(prefix_list_name, verbose):
    """show ip prefix-list"""
    cmd = 'sudo vtysh -c "show ipv6 prefix-list'
    if prefix_list_name is not None:
        cmd += ' {}'.format(prefix_list_name)
    cmd += '"'
    run_command(cmd, display_cmd=verbose)



#
# 'show ipv6 interfaces' command
#
# Display all interfaces with master, an IPv6 address, admin/oper states, their BGP neighbor name and peer ip.
# Addresses from all scopes are included. Interfaces with no addresses are
# excluded.
#
@ipv6.command()
def interfaces():
    """Show interfaces IPv6 address"""
    header = ['Interface', 'Master', 'IPv6 address/mask', 'Admin/Oper', 'BGP Neighbor', 'Neighbor IP']
    data = []
    bgp_peer = get_bgp_peer()

    interfaces = natsorted(netifaces.interfaces())

    for iface in interfaces:
        ipaddresses = netifaces.ifaddresses(iface)

        if netifaces.AF_INET6 in ipaddresses:
            ifaddresses = []
            neighbor_info = []
            for ipaddr in ipaddresses[netifaces.AF_INET6]:
                neighbor_name = 'N/A'
                neighbor_ip = 'N/A'
                local_ip = str(ipaddr['addr'])
                netmask = ipaddr['netmask'].split('/', 1)[-1]
                ifaddresses.append(["", local_ip + "/" + str(netmask)])
                try:
                    neighbor_name = bgp_peer[local_ip][0]
                    neighbor_ip = bgp_peer[local_ip][1]
                except Exception:
                    pass
                neighbor_info.append([neighbor_name, neighbor_ip])

            if len(ifaddresses) > 0:
                admin = get_if_admin_state(iface)
                if admin == "up":
                    oper = get_if_oper_state(iface)
                else:
                    oper = "down"
                master = get_if_master(iface)
                if clicommon.get_interface_naming_mode() == "alias":
                    iface = iface_alias_converter.name_to_alias(iface)
                data.append([iface, master, ifaddresses[0][1], admin + "/" + oper, neighbor_info[0][0], neighbor_info[0][1]])
                neighbor_info.pop(0)
                for ifaddr in ifaddresses[1:]:
                    data.append(["", "", ifaddr[1], admin + "/" + oper, neighbor_info[0][0], neighbor_info[0][1]])
                    neighbor_info.pop(0)

    print(tabulate(data, header, tablefmt="simple", stralign='left', missingval=""))


#
# 'route' subcommand ("show ipv6 route")
#

@ipv6.command()
@click.argument('args', metavar='[IPADDRESS] [vrf <vrf_name>] [...]', nargs=-1, required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def route(args, verbose):
    """Show IPv6 routing table"""
    cmd = 'sudo vtysh -c "show ipv6 route'

    for arg in args:
        cmd += " " + str(arg)

    cmd += '"'

    run_command(cmd, display_cmd=verbose)


# 'protocol' command
@ipv6.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def protocol(verbose):
    """Show IPv6 protocol information"""
    cmd = 'sudo vtysh -c "show ipv6 protocol"'
    run_command(cmd, display_cmd=verbose)

#
# Inserting BGP functionality into cli's show parse-chain.
# BGP commands are determined by the routing-stack being elected.
#
if routing_stack == "quagga":
    from .bgp_quagga_v4 import bgp
    ip.add_command(bgp)
    from .bgp_quagga_v6 import bgp
    ipv6.add_command(bgp)
elif routing_stack == "frr":
    from .bgp_frr_v4 import bgp
    ip.add_command(bgp)
    from .bgp_frr_v6 import bgp
    ipv6.add_command(bgp)

#
# 'lldp' group ("show lldp ...")
#

@cli.group(cls=clicommon.AliasedGroup)
def lldp():
    """LLDP (Link Layer Discovery Protocol) information"""
    pass

# Default 'lldp' command (called if no subcommands or their aliases were passed)
@lldp.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def neighbors(interfacename, verbose):
    """Show LLDP neighbors"""
    cmd = "sudo lldpshow -d"

    if interfacename is not None:
        if clicommon.get_interface_naming_mode() == "alias":
            interfacename = iface_alias_converter.alias_to_name(interfacename)

        cmd += " -p {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)

# 'table' subcommand ("show lldp table")
@lldp.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def table(verbose):
    """Show LLDP neighbors in tabular format"""
    cmd = "sudo lldpshow"
    run_command(cmd, display_cmd=verbose)

#
# 'platform' group ("show platform ...")
#

def get_hw_info_dict():
    """
    This function is used to get the HW info helper function
    """
    hw_info_dict = {}

    version_info = device_info.get_sonic_version_info()

    hw_info_dict['platform'] = device_info.get_platform()
    hw_info_dict['hwsku'] = device_info.get_hwsku()
    hw_info_dict['asic_type'] = version_info['asic_type']
    hw_info_dict['asic_count'] = multi_asic.get_num_asics()

    return hw_info_dict

@cli.group(cls=clicommon.AliasedGroup)
def platform():
    """Show platform-specific hardware info"""
    pass

version_info = device_info.get_sonic_version_info()
if (version_info and version_info.get('asic_type') == 'mellanox'):
    platform.add_command(mlnx.mlnx)

# 'summary' subcommand ("show platform summary")
@platform.command()
@click.option('--json', is_flag=True, help="JSON output")
def summary(json):
    """Show hardware platform information"""

    hw_info_dict = get_hw_info_dict()
    if json:
        click.echo(clicommon.json_dump(hw_info_dict))
    else:
        click.echo("Platform: {}".format(hw_info_dict['platform']))
        click.echo("HwSKU: {}".format(hw_info_dict['hwsku']))
        click.echo("ASIC: {}".format(hw_info_dict['asic_type']))
        click.echo("ASIC Count: {}".format(hw_info_dict['asic_count']))

# 'syseeprom' subcommand ("show platform syseeprom")
@platform.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def syseeprom(verbose):
    """Show system EEPROM information"""
    cmd = "sudo decode-syseeprom -d"
    run_command(cmd, display_cmd=verbose)

# 'psustatus' subcommand ("show platform psustatus")
@platform.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def psustatus(index, verbose):
    """Show PSU status information"""
    cmd = "psushow -s"

    if index >= 0:
        cmd += " -i {}".format(index)

    run_command(cmd, display_cmd=verbose)

# 'ssdhealth' subcommand ("show platform ssdhealth [--verbose/--vendor]")
@platform.command()
@click.argument('device', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--vendor', is_flag=True, help="Enable vendor specific output")
def ssdhealth(device, verbose, vendor):
    """Show SSD Health information"""
    if not device:
        device = os.popen("lsblk -o NAME,TYPE -p | grep disk").readline().strip().split()[0]
    cmd = "ssdutil -d " + device
    options = " -v" if verbose else ""
    options += " -e" if vendor else ""
    run_command(cmd + options, display_cmd=verbose)

@platform.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('-c', '--check', is_flag=True, help="Check the platfome pcie device")
def pcieinfo(check, verbose):
    """Show Device PCIe Info"""
    cmd = "pcieutil pcie_show"
    if check:
        cmd = "pcieutil pcie_check"
    run_command(cmd, display_cmd=verbose)

# 'fan' subcommand ("show platform fan")
@platform.command()
def fan():
    """Show fan status information"""
    cmd = 'fanshow'
    run_command(cmd)

# 'temperature' subcommand ("show platform temperature")
@platform.command()
def temperature():
    """Show device temperature information"""
    cmd = 'tempershow'
    run_command(cmd)

# 'firmware' subcommand ("show platform firmware")
@platform.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True
    ),
    add_help_option=False
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def firmware(args):
    """Show firmware information"""
    cmd = "fwutil show {}".format(" ".join(args))

    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

#
# 'logging' command ("show logging")
#

@cli.command()
@click.argument('process', required=False)
@click.option('-l', '--lines')
@click.option('-f', '--follow', is_flag=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def logging(process, lines, follow, verbose):
    """Show system log"""
    if follow:
        cmd = "sudo tail -F /var/log/syslog"
        run_command(cmd, display_cmd=verbose)
    else:
        if os.path.isfile("/var/log/syslog.1"):
            cmd = "sudo cat /var/log/syslog.1 /var/log/syslog"
        else:
            cmd = "sudo cat /var/log/syslog"

        if process is not None:
            cmd += " | grep '{}'".format(process)

        if lines is not None:
            cmd += " | tail -{}".format(lines)

        run_command(cmd, display_cmd=verbose)


#
# 'version' command ("show version")
#

@cli.command()
@click.option("--verbose", is_flag=True, help="Enable verbose output")
def version(verbose):
    """Show version information"""
    version_info = device_info.get_sonic_version_info()
    hw_info_dict = get_hw_info_dict()
    serial_number_cmd = "sudo decode-syseeprom -s"
    serial_number = subprocess.Popen(serial_number_cmd, shell=True, text=True, stdout=subprocess.PIPE)
    sys_uptime_cmd = "uptime"
    sys_uptime = subprocess.Popen(sys_uptime_cmd, shell=True, text=True, stdout=subprocess.PIPE)
    click.echo("\nSONiC Software Version: SONiC.{}".format(version_info['build_version']))
    click.echo("Distribution: Debian {}".format(version_info['debian_version']))
    click.echo("Kernel: {}".format(version_info['kernel_version']))
    click.echo("Build commit: {}".format(version_info['commit_id']))
    click.echo("Build date: {}".format(version_info['build_date']))
    click.echo("Built by: {}".format(version_info['built_by']))
    click.echo("\nPlatform: {}".format(hw_info_dict['platform']))
    click.echo("HwSKU: {}".format(hw_info_dict['hwsku']))
    click.echo("ASIC: {}".format(hw_info_dict['asic_type']))
    click.echo("Serial Number: {}".format(serial_number.stdout.read().strip()))
    click.echo("Uptime: {}".format(sys_uptime.stdout.read().strip()))
    click.echo("\nDocker images:")
    cmd = 'sudo docker images --format "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.Size}}"'
    p = subprocess.Popen(cmd, shell=True, text=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

#
# 'environment' command ("show environment")
#

@cli.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def environment(verbose):
    """Show environmentals (voltages, fans, temps)"""
    cmd = "sudo sensors"
    run_command(cmd, display_cmd=verbose)


#
# 'processes' group ("show processes ...")
#

@cli.group(cls=clicommon.AliasedGroup)
def processes():
    """Display process information"""
    pass

@processes.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def summary(verbose):
    """Show processes info"""
    # Run top batch mode to prevent unexpected newline after each newline
    cmd = "ps -eo pid,ppid,cmd,%mem,%cpu "
    run_command(cmd, display_cmd=verbose)


# 'cpu' subcommand ("show processes cpu")
@processes.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def cpu(verbose):
    """Show processes CPU info"""
    # Run top in batch mode to prevent unexpected newline after each newline
    cmd = "top -bn 1 -o %CPU"
    run_command(cmd, display_cmd=verbose)

# 'memory' subcommand
@processes.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def memory(verbose):
    """Show processes memory info"""
    # Run top batch mode to prevent unexpected newline after each newline
    cmd = "top -bn 1 -o %MEM"
    run_command(cmd, display_cmd=verbose)

#
# 'users' command ("show users")
#

@cli.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def users(verbose):
    """Show users"""
    cmd = "who"
    run_command(cmd, display_cmd=verbose)


#
# 'techsupport' command ("show techsupport")
#

@cli.command()
@click.option('--since', required=False, help="Collect logs and core files since given date")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def techsupport(since, verbose):
    """Gather information for troubleshooting"""
    cmd = "sudo generate_dump -v"
    if since:
        cmd += " -s {}".format(since)
    run_command(cmd, display_cmd=verbose)


#
# 'runningconfiguration' group ("show runningconfiguration")
#

@cli.group(cls=clicommon.AliasedGroup)
def runningconfiguration():
    """Show current running configuration information"""
    pass


# 'all' subcommand ("show runningconfiguration all")
@runningconfiguration.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Show full running configuration"""
    cmd = "sonic-cfggen -d --print-data"
    run_command(cmd, display_cmd=verbose)


# 'acl' subcommand ("show runningconfiguration acl")
@runningconfiguration.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def acl(verbose):
    """Show acl running configuration"""
    cmd = "sonic-cfggen -d --var-json ACL_RULE"
    run_command(cmd, display_cmd=verbose)


# 'ports' subcommand ("show runningconfiguration ports <portname>")
@runningconfiguration.command()
@click.argument('portname', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def ports(portname, verbose):
    """Show ports running configuration"""
    cmd = "sonic-cfggen -d --var-json PORT"

    if portname is not None:
        cmd += " {0} {1}".format("--key", portname)

    run_command(cmd, display_cmd=verbose)


# 'bgp' subcommand ("show runningconfiguration bgp")
@runningconfiguration.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def bgp(verbose):
    """Show BGP running configuration"""
    cmd = 'sudo vtysh -c "show running-config"'
    run_command(cmd, display_cmd=verbose)


# 'interfaces' subcommand ("show runningconfiguration interfaces")
@runningconfiguration.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def interfaces(interfacename, verbose):
    """Show interfaces running configuration"""
    cmd = "sonic-cfggen -d --var-json INTERFACE"

    if interfacename is not None:
        cmd += " {0} {1}".format("--key", interfacename)

    run_command(cmd, display_cmd=verbose)


# 'snmp' subcommand ("show runningconfiguration snmp")
@runningconfiguration.command()
@click.argument('server', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def snmp(server, verbose):
    """Show SNMP information"""
    cmd = "sudo docker exec snmp cat /etc/snmp/snmpd.conf"

    if server is not None:
        cmd += " | grep -i agentAddress"

    run_command(cmd, display_cmd=verbose)


# 'ntp' subcommand ("show runningconfiguration ntp")
@runningconfiguration.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def ntp(verbose):
    """Show NTP running configuration"""
    ntp_servers = []
    ntp_dict = {}
    with open("/etc/ntp.conf") as ntp_file:
        data = ntp_file.readlines()
    for line in data:
        if line.startswith("server "):
            ntp_server = line.split(" ")[1]
            ntp_servers.append(ntp_server)
    ntp_dict['NTP Servers'] = ntp_servers
    print(tabulate(ntp_dict, headers=list(ntp_dict.keys()), tablefmt="simple", stralign='left', missingval=""))


# 'syslog' subcommand ("show runningconfiguration syslog")
@runningconfiguration.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def syslog(verbose):
    """Show Syslog running configuration"""
    syslog_servers = []
    syslog_dict = {}
    with open("/etc/rsyslog.conf") as syslog_file:
        data = syslog_file.readlines()
    for line in data:
        if line.startswith("*.* @"):
            line = line.split(":")
            server = line[0][5:]
            syslog_servers.append(server)
    syslog_dict['Syslog Servers'] = syslog_servers
    print(tabulate(syslog_dict, headers=list(syslog_dict.keys()), tablefmt="simple", stralign='left', missingval=""))


#
# 'startupconfiguration' group ("show startupconfiguration ...")
#

@cli.group(cls=clicommon.AliasedGroup)
def startupconfiguration():
    """Show startup configuration information"""
    pass


# 'bgp' subcommand  ("show startupconfiguration bgp")
@startupconfiguration.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def bgp(verbose):
    """Show BGP startup configuration"""
    cmd = "sudo docker ps | grep bgp | awk '{print$2}' | cut -d'-' -f3 | cut -d':' -f1"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, text=True)
    result = proc.stdout.read().rstrip()
    click.echo("Routing-Stack is: {}".format(result))
    if result == "quagga":
        run_command('sudo docker exec bgp cat /etc/quagga/bgpd.conf', display_cmd=verbose)
    elif result == "frr":
        run_command('sudo docker exec bgp cat /etc/frr/bgpd.conf', display_cmd=verbose)
    elif result == "gobgp":
        run_command('sudo docker exec bgp cat /etc/gpbgp/bgpd.conf', display_cmd=verbose)
    else:
        click.echo("Unidentified routing-stack")

#
# 'ntp' command ("show ntp")
#

@cli.command()
@click.pass_context
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def ntp(ctx, verbose):
    """Show NTP information"""
    ntpstat_cmd = "ntpstat"
    ntpcmd = "ntpq -p -n"
    if is_mgmt_vrf_enabled(ctx) is True:
        #ManagementVRF is enabled. Call ntpq using "ip vrf exec" or cgexec based on linux version
        os_info =  os.uname()
        release = os_info[2].split('-')
        if parse_version(release[0]) > parse_version("4.9.0"):
            ntpstat_cmd = "sudo ip vrf exec mgmt ntpstat"
            ntpcmd = "sudo ip vrf exec mgmt ntpq -p -n"
        else:
            ntpstat_cmd = "sudo cgexec -g l3mdev:mgmt ntpstat"
            ntpcmd = "sudo cgexec -g l3mdev:mgmt ntpq -p -n"

    run_command(ntpstat_cmd, display_cmd=verbose)
    run_command(ntpcmd, display_cmd=verbose)

#
# 'uptime' command ("show uptime")
#

@cli.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def uptime(verbose):
    """Show system uptime"""
    cmd = "uptime -p"
    run_command(cmd, display_cmd=verbose)

@cli.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def clock(verbose):
    """Show date and time"""
    cmd ="date"
    run_command(cmd, display_cmd=verbose)

@cli.command('system-memory')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def system_memory(verbose):
    """Show memory information"""
    cmd = "free -m"
    run_command(cmd, display_cmd=verbose)

#
# 'kdump command ("show kdump ...")
#
@cli.group(cls=clicommon.AliasedGroup)
def kdump():
    """Show kdump configuration, status and information """
    pass

@kdump.command('enabled')
def enabled():
    """Show if kdump is enabled or disabled"""
    kdump_is_enabled = False
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        table_data = config_db.get_table('KDUMP')
        if table_data is not None:
            config_data = table_data.get('config')
            if config_data is not None:
                if config_data.get('enabled').lower() == 'true':
                    kdump_is_enabled = True
    if kdump_is_enabled:
        click.echo("kdump is enabled")
    else:
        click.echo("kdump is disabled")

@kdump.command('status')
def status():
    """Show kdump status"""
    run_command("sonic-kdump-config --status")
    run_command("sonic-kdump-config --memory")
    run_command("sonic-kdump-config --num_dumps")
    run_command("sonic-kdump-config --files")

@kdump.command('memory')
def memory():
    """Show kdump memory information"""
    kdump_memory = "0M-2G:256M,2G-4G:320M,4G-8G:384M,8G-:448M"
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        table_data = config_db.get_table('KDUMP')
        if table_data is not None:
            config_data = table_data.get('config')
            if config_data is not None:
                kdump_memory_from_db = config_data.get('memory')
                if kdump_memory_from_db is not None:
                    kdump_memory = kdump_memory_from_db
    click.echo("Memory Reserved: %s" % kdump_memory)

@kdump.command('num_dumps')
def num_dumps():
    """Show kdump max number of dump files"""
    kdump_num_dumps = "3"
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        table_data = config_db.get_table('KDUMP')
        if table_data is not None:
            config_data = table_data.get('config')
            if config_data is not None:
                kdump_num_dumps_from_db = config_data.get('num_dumps')
                if kdump_num_dumps_from_db is not None:
                    kdump_num_dumps = kdump_num_dumps_from_db
    click.echo("Maximum number of Kernel Core files Stored: %s" % kdump_num_dumps)

@kdump.command('files')
def files():
    """Show kdump kernel core dump files"""
    run_command("sonic-kdump-config --files")

@kdump.command()
@click.argument('record', required=True)
@click.argument('lines', metavar='<lines>', required=False)
def log(record, lines):
    """Show kdump kernel core dump file kernel log"""
    if lines is None:
        run_command("sonic-kdump-config --file %s" % record)
    else:
        run_command("sonic-kdump-config --file %s --lines %s" % (record, lines))

@cli.command('services')
def services():
    """Show all daemon services"""
    cmd = "sudo docker ps --format '{{.Names}}'"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, text=True)
    while True:
        line = proc.stdout.readline()
        if line != '':
                print(line.rstrip()+'\t'+"docker")
                print("---------------------------")
                cmd = "sudo docker exec {} ps aux | sed '$d'".format(line.rstrip())
                proc1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, text=True)
                print(proc1.stdout.read())
        else:
                break

@cli.command()
def aaa():
    """Show AAA configuration"""
    config_db = ConfigDBConnector()
    config_db.connect()
    data = config_db.get_table('AAA')
    output = ''

    aaa = {
        'authentication': {
            'login': 'local (default)',
            'failthrough': 'False (default)'
        }
    }
    if 'authentication' in data:
        aaa['authentication'].update(data['authentication'])
    for row in aaa:
        entry = aaa[row]
        for key in entry:
            output += ('AAA %s %s %s\n' % (row, key, str(entry[key])))
    click.echo(output)


@cli.command()
def tacacs():
    """Show TACACS+ configuration"""
    config_db = ConfigDBConnector()
    config_db.connect()
    output = ''
    data = config_db.get_table('TACPLUS')

    tacplus = {
        'global': {
            'auth_type': 'pap (default)',
            'timeout': '5 (default)',
            'passkey': '<EMPTY_STRING> (default)'
        }
    }
    if 'global' in data:
        tacplus['global'].update(data['global'])
    for key in tacplus['global']:
        output += ('TACPLUS global %s %s\n' % (str(key), str(tacplus['global'][key])))

    data = config_db.get_table('TACPLUS_SERVER')
    if data != {}:
        for row in data:
            entry = data[row]
            output += ('\nTACPLUS_SERVER address %s\n' % row)
            for key in entry:
                output += ('               %s %s\n' % (key, str(entry[key])))
    click.echo(output)

#
# 'mirror_session' command  ("show mirror_session ...")
#
@cli.command('mirror_session')
@click.argument('session_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def mirror_session(session_name, verbose):
    """Show existing everflow sessions"""
    cmd = "acl-loader show session"

    if session_name is not None:
        cmd += " {}".format(session_name)

    run_command(cmd, display_cmd=verbose)


#
# 'policer' command  ("show policer ...")
#
@cli.command()
@click.argument('policer_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def policer(policer_name, verbose):
    """Show existing policers"""
    cmd = "acl-loader show policer"

    if policer_name is not None:
        cmd += " {}".format(policer_name)

    run_command(cmd, display_cmd=verbose)


#
# 'sflow command ("show sflow ...")
#
@cli.group(invoke_without_command=True)
@clicommon.pass_db
@click.pass_context
def sflow(ctx, db):
    """Show sFlow related information"""
    if ctx.invoked_subcommand is None:
        show_sflow_global(db.cfgdb)

#
# 'sflow command ("show sflow interface ...")
#
@sflow.command('interface')
@clicommon.pass_db
def sflow_interface(db):
    """Show sFlow interface information"""
    show_sflow_interface(db.cfgdb)

def sflow_appDB_connect():
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.APPL_DB, False)
    return db

def show_sflow_interface(config_db):
    sess_db = sflow_appDB_connect()
    if not sess_db:
        click.echo("sflow AppDB error")
        return

    port_tbl = config_db.get_table('PORT')
    if not port_tbl:
        click.echo("No ports configured")
        return

    click.echo("\nsFlow interface configurations")
    header = ['Interface', 'Admin State', 'Sampling Rate']
    body = []
    for pname in natsorted(list(port_tbl.keys())):
        intf_key = 'SFLOW_SESSION_TABLE:' + pname
        sess_info = sess_db.get_all(sess_db.APPL_DB, intf_key)
        if sess_info is None:
            continue
        body_info = [pname]
        body_info.append(sess_info['admin_state'])
        body_info.append(sess_info['sample_rate'])
        body.append(body_info)
    click.echo(tabulate(body, header, tablefmt='grid'))

def show_sflow_global(config_db):

    sflow_info = config_db.get_table('SFLOW')
    global_admin_state = 'down'
    if sflow_info:
        global_admin_state = sflow_info['global']['admin_state']

    click.echo("\nsFlow Global Information:")
    click.echo("  sFlow Admin State:".ljust(30) + "{}".format(global_admin_state))


    click.echo("  sFlow Polling Interval:".ljust(30), nl=False)
    if (sflow_info and 'polling_interval' in sflow_info['global']):
        click.echo("{}".format(sflow_info['global']['polling_interval']))
    else:
        click.echo("default")

    click.echo("  sFlow AgentID:".ljust(30), nl=False)
    if (sflow_info and 'agent_id' in sflow_info['global']):
        click.echo("{}".format(sflow_info['global']['agent_id']))
    else:
        click.echo("default")

    sflow_info = config_db.get_table('SFLOW_COLLECTOR')
    click.echo("\n  {} Collectors configured:".format(len(sflow_info)))
    for collector_name in sorted(list(sflow_info.keys())):
        vrf_name = (sflow_info[collector_name]['collector_vrf']
                    if 'collector_vrf' in sflow_info[collector_name] else 'default')
        click.echo("    Name: {}".format(collector_name).ljust(30) +
                   "IP addr: {} ".format(sflow_info[collector_name]['collector_ip']).ljust(25) +
                   "UDP port: {}".format(sflow_info[collector_name]['collector_port']).ljust(17) +
                   "VRF: {}".format(vrf_name))


#
# 'acl' group ###
#

@cli.group(cls=clicommon.AliasedGroup)
def acl():
    """Show ACL related information"""
    pass


# 'rule' subcommand  ("show acl rule")
@acl.command()
@click.argument('table_name', required=False)
@click.argument('rule_id', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def rule(table_name, rule_id, verbose):
    """Show existing ACL rules"""
    cmd = "acl-loader show rule"

    if table_name is not None:
        cmd += " {}".format(table_name)

    if rule_id is not None:
        cmd += " {}".format(rule_id)

    run_command(cmd, display_cmd=verbose)


# 'table' subcommand  ("show acl table")
@acl.command()
@click.argument('table_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def table(table_name, verbose):
    """Show existing ACL tables"""
    cmd = "acl-loader show table"

    if table_name is not None:
        cmd += " {}".format(table_name)

    run_command(cmd, display_cmd=verbose)


#
# 'dropcounters' group ###
#

@cli.group(cls=clicommon.AliasedGroup)
def dropcounters():
    """Show drop counter related information"""
    pass


# 'configuration' subcommand ("show dropcounters configuration")
@dropcounters.command()
@click.option('-g', '--group', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def configuration(group, verbose):
    """Show current drop counter configuration"""
    cmd = "dropconfig -c show_config"

    if group:
        cmd += " -g '{}'".format(group)

    run_command(cmd, display_cmd=verbose)


# 'capabilities' subcommand ("show dropcounters capabilities")
@dropcounters.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def capabilities(verbose):
    """Show device drop counter capabilities"""
    cmd = "dropconfig -c show_capabilities"

    run_command(cmd, display_cmd=verbose)


# 'counts' subcommand ("show dropcounters counts")
@dropcounters.command()
@click.option('-g', '--group', required=False)
@click.option('-t', '--counter_type', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counts(group, counter_type, verbose):
    """Show drop counts"""
    cmd = "dropstat -c show"

    if group:
        cmd += " -g '{}'".format(group)

    if counter_type:
        cmd += " -t '{}'".format(counter_type)

    run_command(cmd, display_cmd=verbose)

#
# 'ecn' command ("show ecn")
#
@cli.command('ecn')
def ecn():
    """Show ECN configuration"""
    cmd = "ecnconfig -l"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, text=True)
    click.echo(proc.stdout.read())


#
# 'boot' command ("show boot")
#
@cli.command('boot')
def boot():
    """Show boot configuration"""
    cmd = "sudo sonic-installer list"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, text=True)
    click.echo(proc.stdout.read())


# 'mmu' command ("show mmu")
#
@cli.command('mmu')
def mmu():
    """Show mmu configuration"""
    cmd = "mmuconfig -l"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, text=True)
    click.echo(proc.stdout.read())


#
# 'reboot-cause' command ("show reboot-cause")
#
@cli.command('reboot-cause')
def reboot_cause():
    """Show cause of most recent reboot"""
    PREVIOUS_REBOOT_CAUSE_FILE = "/host/reboot-cause/previous-reboot-cause.txt"

    # At boot time, PREVIOUS_REBOOT_CAUSE_FILE is generated based on
    # the contents of the 'reboot cause' file as it was left when the device
    # went down for reboot. This file should always be created at boot,
    # but check first just in case it's not present.
    if not os.path.isfile(PREVIOUS_REBOOT_CAUSE_FILE):
        click.echo("Unable to determine cause of previous reboot\n")
    else:
        cmd = "cat {}".format(PREVIOUS_REBOOT_CAUSE_FILE)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, text=True)
        click.echo(proc.stdout.read())


#
# 'line' command ("show line")
#
@cli.command('line')
@click.option('--brief', '-b', metavar='<brief_mode>', required=False, is_flag=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def line(brief, verbose):
    """Show all console lines and their info include available ttyUSB devices unless specified brief mode"""
    cmd = "consutil show" + (" -b" if brief else "")
    run_command(cmd, display_cmd=verbose)
    return


@cli.group(name='warm_restart', cls=clicommon.AliasedGroup)
def warm_restart():
    """Show warm restart configuration and state"""
    pass

@warm_restart.command()
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def state(redis_unix_socket_path):
    """Show warm restart state"""
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path

    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.STATE_DB, False)   # Make one attempt only

    TABLE_NAME_SEPARATOR = '|'
    prefix = 'WARM_RESTART_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(prefix, '*')
    table_keys = db.keys(db.STATE_DB, _hash)

    def remove_prefix(text, prefix):
        if text.startswith(prefix):
            return text[len(prefix):]
        return text

    table = []
    for tk in table_keys:
        entry = db.get_all(db.STATE_DB, tk)
        r = []
        r.append(remove_prefix(tk, prefix))
        if 'restore_count' not in entry:
            r.append("")
        else:
            r.append(entry['restore_count'])

        if 'state' not in entry:
            r.append("")
        else:
            r.append(entry['state'])

        table.append(r)

    header = ['name', 'restore_count', 'state']
    click.echo(tabulate(table, header))

@warm_restart.command()
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def config(redis_unix_socket_path):
    """Show warm restart config"""
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path
    config_db = ConfigDBConnector(**kwargs)
    config_db.connect(wait_for_init=False)
    data = config_db.get_table('WARM_RESTART')
    # Python dictionary keys() Method
    keys = list(data.keys())

    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)   # Make one attempt only
    TABLE_NAME_SEPARATOR = '|'
    prefix = 'WARM_RESTART_ENABLE_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(prefix, '*')
    # DBInterface keys() method
    enable_table_keys = state_db.keys(state_db.STATE_DB, _hash)

    def tablelize(keys, data, enable_table_keys, prefix):
        table = []

        if enable_table_keys is not None:
            for k in enable_table_keys:
                k = k.replace(prefix, "")
                if k not in keys:
                    keys.append(k)

        for k in keys:
            r = []
            r.append(k)

            enable_k = prefix + k
            if enable_table_keys is None or enable_k not in enable_table_keys:
                r.append("false")
            else:
                r.append(state_db.get(state_db.STATE_DB, enable_k, "enable"))

            if k not in data:
                r.append("NULL")
                r.append("NULL")
                r.append("NULL")
            elif 'neighsyncd_timer' in  data[k]:
                r.append("neighsyncd_timer")
                r.append(data[k]['neighsyncd_timer'])
                r.append("NULL")
            elif 'bgp_timer' in data[k] or 'bgp_eoiu' in data[k]:
                if 'bgp_timer' in data[k]:
                    r.append("bgp_timer")
                    r.append(data[k]['bgp_timer'])
                else:
                    r.append("NULL")
                    r.append("NULL")
                if 'bgp_eoiu' in data[k]:
                    r.append(data[k]['bgp_eoiu'])
                else:
                    r.append("NULL")
            elif 'teamsyncd_timer' in data[k]:
                r.append("teamsyncd_timer")
                r.append(data[k]['teamsyncd_timer'])
                r.append("NULL")
            else:
                r.append("NULL")
                r.append("NULL")
                r.append("NULL")

            table.append(r)

        return table

    header = ['name', 'enable', 'timer_name', 'timer_duration', 'eoiu_enable']
    click.echo(tabulate(tablelize(keys, data, enable_table_keys, prefix), header))
    state_db.close(state_db.STATE_DB)

#
# 'nat' group ("show nat ...")
#

@cli.group(cls=clicommon.AliasedGroup)
def nat():
    """Show details of the nat """
    pass

# 'statistics' subcommand ("show nat statistics")
@nat.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def statistics(verbose):
    """ Show NAT statistics """

    cmd = "sudo natshow -s"
    run_command(cmd, display_cmd=verbose)

# 'translations' subcommand ("show nat translations")
@nat.group(invoke_without_command=True)
@click.pass_context
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def translations(ctx, verbose):
    """ Show NAT translations """

    if ctx.invoked_subcommand is None:
        cmd = "sudo natshow -t"
        run_command(cmd, display_cmd=verbose)

# 'count' subcommand ("show nat translations count")
@translations.command()
def count():
    """ Show NAT translations count """

    cmd = "sudo natshow -c"
    run_command(cmd)

# 'config' subcommand ("show nat config")
@nat.group(invoke_without_command=True)
@click.pass_context
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def config(ctx, verbose):
    """Show NAT config related information"""
    if ctx.invoked_subcommand is None:
        click.echo("\nGlobal Values")
        cmd = "sudo natconfig -g"
        run_command(cmd, display_cmd=verbose)
        click.echo("Static Entries")
        cmd = "sudo natconfig -s"
        run_command(cmd, display_cmd=verbose)
        click.echo("Pool Entries")
        cmd = "sudo natconfig -p"
        run_command(cmd, display_cmd=verbose)
        click.echo("NAT Bindings")
        cmd = "sudo natconfig -b"
        run_command(cmd, display_cmd=verbose)
        click.echo("NAT Zones")
        cmd = "sudo natconfig -z"
        run_command(cmd, display_cmd=verbose)

# 'static' subcommand  ("show nat config static")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def static(verbose):
    """Show static NAT configuration"""

    cmd = "sudo natconfig -s"
    run_command(cmd, display_cmd=verbose)

# 'pool' subcommand  ("show nat config pool")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def pool(verbose):
    """Show NAT Pool configuration"""

    cmd = "sudo natconfig -p"
    run_command(cmd, display_cmd=verbose)

# Define GEARBOX commands only if GEARBOX is configured
app_db = SonicV2Connector(host='127.0.0.1')
app_db.connect(app_db.APPL_DB)
if app_db.keys(app_db.APPL_DB, '_GEARBOX_TABLE:phy:*'):

    @cli.group(cls=clicommon.AliasedGroup)
    def gearbox():
        """Show gearbox info"""
        pass

    # 'phys' subcommand ("show gearbox phys")
    @gearbox.group(cls=clicommon.AliasedGroup)
    def phys():
        """Show external PHY information"""
        pass

    # 'status' subcommand ("show gearbox phys status")
    @phys.command()
    @click.pass_context
    def status(ctx):
        """Show gearbox phys status"""
        run_command("gearboxutil phys status")
        return

    # 'interfaces' subcommand ("show gearbox interfaces")
    @gearbox.group(cls=clicommon.AliasedGroup)
    def interfaces():
        """Show gearbox interfaces information"""
        pass

    # 'status' subcommand ("show gearbox interfaces status")
    @interfaces.command()
    @click.pass_context
    def status(ctx):
        """Show gearbox interfaces status"""
        run_command("gearboxutil interfaces status")
        return

# 'bindings' subcommand  ("show nat config bindings")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def bindings(verbose):
    """Show NAT binding configuration"""

    cmd = "sudo natconfig -b"
    run_command(cmd, display_cmd=verbose)

# 'globalvalues' subcommand  ("show nat config globalvalues")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def globalvalues(verbose):
    """Show NAT Global configuration"""

    cmd = "sudo natconfig -g"
    run_command(cmd, display_cmd=verbose)

# 'zones' subcommand  ("show nat config zones")
@config.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def zones(verbose):
    """Show NAT Zone configuration"""

    cmd = "sudo natconfig -z"
    run_command(cmd, display_cmd=verbose)

#
# 'ztp status' command ("show ztp status")
#
@cli.command()
@click.argument('status', required=False, type=click.Choice(["status"]))
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def ztp(status, verbose):
    """Show Zero Touch Provisioning status"""
    if os.path.isfile('/usr/bin/ztp') is False:
        exit("ZTP feature unavailable in this image version")

    cmd = "ztp status"
    if verbose:
       cmd = cmd + " --verbose"
    run_command(cmd, display_cmd=verbose)

#
# 'vnet' command ("show vnet")
#
@cli.group(cls=clicommon.AliasedGroup)
def vnet():
    """Show vnet related information"""
    pass

@vnet.command()
@click.argument('vnet_name', required=True)
def name(vnet_name):
    """Show vnet name <vnet name> information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vnet name', 'vxlan tunnel', 'vni', 'peer list']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_entry('VNET', vnet_name)

    def tablelize(vnet_key, vnet_data):
        table = []
        if vnet_data:
            r = []
            r.append(vnet_key)
            r.append(vnet_data.get('vxlan_tunnel'))
            r.append(vnet_data.get('vni'))
            r.append(vnet_data.get('peer_list'))
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_name, vnet_data), header))

@vnet.command()
def brief():
    """Show vnet brief information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vnet name', 'vxlan tunnel', 'vni', 'peer list']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_table('VNET')
    vnet_keys = natsorted(list(vnet_data.keys()))

    def tablelize(vnet_keys, vnet_data):
        table = []
        for k in vnet_keys:
            r = []
            r.append(k)
            r.append(vnet_data[k].get('vxlan_tunnel'))
            r.append(vnet_data[k].get('vni'))
            r.append(vnet_data[k].get('peer_list'))
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_keys, vnet_data), header))

@vnet.command()
@click.argument('vnet_alias', required=False)
def alias(vnet_alias):
    """Show vnet alias to name information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['Alias', 'Name']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_table('VNET')
    vnet_keys = natsorted(list(vnet_data.keys()))

    def tablelize(vnet_keys, vnet_data, vnet_alias):
        table = []
        for k in vnet_keys:
            r = []
            if vnet_alias is not None:
                if vnet_data[k].get('guid') == vnet_alias:
                    r.append(vnet_data[k].get('guid'))
                    r.append(k)
                    table.append(r)
                    return table
                else:
                    continue

            r.append(vnet_data[k].get('guid'))
            r.append(k)
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_keys, vnet_data, vnet_alias), header))

@vnet.command()
def interfaces():
    """Show vnet interfaces information"""
    config_db = ConfigDBConnector()
    config_db.connect()

    header = ['vnet name', 'interfaces']

    # Fetching data from config_db for interfaces
    intfs_data = config_db.get_table("INTERFACE")
    vlan_intfs_data = config_db.get_table("VLAN_INTERFACE")

    vnet_intfs = {}
    for k, v in intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    for k, v in vlan_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    table = []
    for k, v in vnet_intfs.items():
        r = []
        r.append(k)
        r.append(",".join(natsorted(v)))
        table.append(r)

    click.echo(tabulate(table, header))

@vnet.command()
def neighbors():
    """Show vnet neighbors information"""
    config_db = ConfigDBConnector()
    config_db.connect()

    header = ['<vnet_name>', 'neighbor', 'mac_address', 'interfaces']

    # Fetching data from config_db for interfaces
    intfs_data = config_db.get_table("INTERFACE")
    vlan_intfs_data = config_db.get_table("VLAN_INTERFACE")

    vnet_intfs = {}
    for k, v in intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    for k, v in vlan_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    # Fetching data from appl_db for neighbors
    nbrs = appl_db.keys(appl_db.APPL_DB, "NEIGH_TABLE*")
    nbrs_data = {}
    for nbr in nbrs if nbrs else []:
        tbl, intf, ip = nbr.split(":", 2)
        mac = appl_db.get(appl_db.APPL_DB, nbr, 'neigh')
        if intf in nbrs_data:
            nbrs_data[intf].append((ip, mac))
        else:
            nbrs_data[intf] = [(ip, mac)]

    table = []
    for k, v in vnet_intfs.items():
        v = natsorted(v)
        header[0] = k
        table = []
        for intf in v:
            if intf in nbrs_data:
                for ip, mac in nbrs_data[intf]:
                    r = ["", ip, mac, intf]
                    table.append(r)
        click.echo(tabulate(table, header))
        click.echo()

    if not bool(vnet_intfs):
        click.echo(tabulate(table, header))

@vnet.group()
def routes():
    """Show vnet routes related information"""
    pass

@routes.command()
def all():
    """Show all vnet routes"""
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    header = ['vnet name', 'prefix', 'nexthop', 'interface']

    # Fetching data from appl_db for VNET ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TABLE*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('nexthop'))
        r.append(val.get('ifname'))
        table.append(r)

    click.echo(tabulate(table, header))

    click.echo()

    header = ['vnet name', 'prefix', 'endpoint', 'mac address', 'vni']

    # Fetching data from appl_db for VNET TUNNEL ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TUNNEL_TABLE*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('endpoint'))
        r.append(val.get('mac_address'))
        r.append(val.get('vni'))
        table.append(r)

    click.echo(tabulate(table, header))

@routes.command()
def tunnel():
    """Show vnet tunnel routes"""
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    header = ['vnet name', 'prefix', 'endpoint', 'mac address', 'vni']

    # Fetching data from appl_db for VNET TUNNEL ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TUNNEL_TABLE*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('endpoint'))
        r.append(val.get('mac_address'))
        r.append(val.get('vni'))
        table.append(r)

    click.echo(tabulate(table, header))

#
# 'vxlan' command ("show vxlan")
#
@cli.group(cls=clicommon.AliasedGroup)
def vxlan():
    """Show vxlan related information"""
    pass

@vxlan.command()
@click.argument('vxlan_name', required=True)
def name(vxlan_name):
    """Show vxlan name <vxlan_name> information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vxlan tunnel name', 'source ip', 'destination ip', 'tunnel map name', 'tunnel map mapping(vni -> vlan)']

    # Fetching data from config_db for VXLAN TUNNEL
    vxlan_data = config_db.get_entry('VXLAN_TUNNEL', vxlan_name)

    table = []
    if vxlan_data:
        r = []
        r.append(vxlan_name)
        r.append(vxlan_data.get('src_ip'))
        r.append(vxlan_data.get('dst_ip'))
        vxlan_map_keys = config_db.keys(config_db.CONFIG_DB,
                        'VXLAN_TUNNEL_MAP{}{}{}*'.format(config_db.KEY_SEPARATOR, vxlan_name, config_db.KEY_SEPARATOR))
        if vxlan_map_keys:
            vxlan_map_mapping = config_db.get_all(config_db.CONFIG_DB, vxlan_map_keys[0])
            r.append(vxlan_map_keys[0].split(config_db.KEY_SEPARATOR, 2)[2])
            r.append("{} -> {}".format(vxlan_map_mapping.get('vni'), vxlan_map_mapping.get('vlan')))
        table.append(r)

    click.echo(tabulate(table, header))

@vxlan.command()
def tunnel():
    """Show vxlan tunnel information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vxlan tunnel name', 'source ip', 'destination ip', 'tunnel map name', 'tunnel map mapping(vni -> vlan)']

    # Fetching data from config_db for VXLAN TUNNEL
    vxlan_data = config_db.get_table('VXLAN_TUNNEL')
    vxlan_keys = natsorted(list(vxlan_data.keys()))

    table = []
    for k in vxlan_keys:
        r = []
        r.append(k)
        r.append(vxlan_data[k].get('src_ip'))
        r.append(vxlan_data[k].get('dst_ip'))
        vxlan_map_keys = config_db.keys(config_db.CONFIG_DB,
                        'VXLAN_TUNNEL_MAP{}{}{}*'.format(config_db.KEY_SEPARATOR,k, config_db.KEY_SEPARATOR))
        if vxlan_map_keys:
            vxlan_map_mapping = config_db.get_all(config_db.CONFIG_DB, vxlan_map_keys[0])
            r.append(vxlan_map_keys[0].split(config_db.KEY_SEPARATOR, 2)[2])
            r.append("{} -> {}".format(vxlan_map_mapping.get('vni'), vxlan_map_mapping.get('vlan')))
        table.append(r)

    click.echo(tabulate(table, header))

if __name__ == '__main__':
    cli()
