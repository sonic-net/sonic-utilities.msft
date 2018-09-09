#! /usr/bin/python -u

import click
import errno
import getpass
import json
import os
import subprocess
import sys
from click_default_group import DefaultGroup
from natsort import natsorted
from tabulate import tabulate
from swsssdk import ConfigDBConnector

import mlnx

try:
    # noinspection PyPep8Naming
    import ConfigParser as configparser
except ImportError:
    # noinspection PyUnresolvedReferences
    import configparser


# This is from the aliases example:
# https://github.com/pallets/click/blob/57c6f09611fc47ca80db0bd010f05998b3c0aa95/examples/aliases/aliases.py
class Config(object):
    """Object to hold CLI config"""

    def __init__(self):
        self.path = os.getcwd()
        self.aliases = {}

    def read_config(self, filename):
        parser = configparser.RawConfigParser()
        parser.read([filename])
        try:
            self.aliases.update(parser.items('aliases'))
        except configparser.NoSectionError:
            pass


# Global Config object
_config = None


# This aliased group has been modified from click examples to inherit from DefaultGroup instead of click.Group.
# DefaultGroup is a superclass of click.Group which calls a default subcommand instead of showing
# a help message if no subcommand is passed
class AliasedGroup(DefaultGroup):
    """This subclass of a DefaultGroup supports looking up aliases in a config
    file and with a bit of magic.
    """

    def get_command(self, ctx, cmd_name):
        global _config

        # If we haven't instantiated our global config, do it now and load current config
        if _config is None:
            _config = Config()

            # Load our config file
            cfg_file = os.path.join(os.path.dirname(__file__), 'aliases.ini')
            _config.read_config(cfg_file)

        # Try to get builtin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # No builtin found. Look up an explicit command alias in the config
        if cmd_name in _config.aliases:
            actual_cmd = _config.aliases[cmd_name]
            return click.Group.get_command(self, ctx, actual_cmd)

        # Alternative option: if we did not find an explicit alias we
        # allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        matches = [x for x in self.list_commands(ctx)
                   if x.lower().startswith(cmd_name.lower())]
        if not matches:
            # No command name matched. Issue Default command.
            ctx.arg0 = cmd_name
            cmd_name = self.default_cmd_name
            return DefaultGroup.get_command(self, ctx, cmd_name)
        elif len(matches) == 1:
            return DefaultGroup.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


# To be enhanced. Routing-stack information should be collected from a global
# location (configdb?), so that we prevent the continous execution of this
# bash oneliner. To be revisited once routing-stack info is tracked somewhere.
def get_routing_stack():
    command = "sudo docker ps | grep bgp | awk '{print$2}' | cut -d'-' -f3 | cut -d':' -f1"

    try:
        proc = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                shell=True,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        result = stdout.rstrip('\n')

    except OSError, e:
        raise OSError("Cannot detect routing-stack")

    return (result)


# Global Routing-Stack variable
routing_stack = get_routing_stack()


def run_command(command, display_cmd=False):
    if display_cmd:
        click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

    while True:
        output = proc.stdout.readline()
        if output == "" and proc.poll() is not None:
            break
        if output:
            click.echo(output.rstrip('\n'))

    rc = proc.poll()
    if rc != 0:
        sys.exit(rc)

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

#
# 'cli' group (root group)
#

# This is our entrypoint - the main "show" command
# TODO: Consider changing function name to 'show' for better understandability
@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
def cli():
    """SONiC command line - 'show' command"""
    pass


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

#
# 'interfaces' group ("show interfaces ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def interfaces():
    """Show details of the network interfaces"""
    pass

# 'alias' subcommand ("show interfaces alias")
@interfaces.command()
@click.argument('interfacename', required=False)
def alias(interfacename):
    """Show Interface Name/Alias Mapping"""

    cmd = 'sonic-cfggen -d --var-json "PORT"'
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

    port_dict = json.loads(p.stdout.read())

    header = ['Name', 'Alias']
    body = []

    if interfacename is not None:
        # If we're given an interface name, output name and alias for that interface only
        if interfacename in port_dict:
            if 'alias' in port_dict[interfacename]:
                body.append([interfacename, port_dict[interfacename]['alias']])
            else:
                body.append([interfacename, interfacename])
        else:
            click.echo("Invalid interface name, '{0}'".format(interfacename))
            return
    else:
        # Output name and alias for all interfaces
        for port_name in natsorted(port_dict.keys()):
            if 'alias' in port_dict[port_name]:
                body.append([port_name, port_dict[port_name]['alias']])
            else:
                body.append([port_name, port_name])

    click.echo(tabulate(body, header))

#
# 'neighbor' group ###
#
@interfaces.group(cls=AliasedGroup, default_if_no_args=False)
def neighbor():
    """Show neighbor related information"""
    pass

# 'expected' subcommand ("show interface neighbor expected")
@neighbor.command()
@click.argument('interfacename', required=False)
def expected(interfacename):
    """Show expected neighbor information by interfaces"""
    neighbor_cmd = 'sonic-cfggen -d --var-json "DEVICE_NEIGHBOR"'
    p1 = subprocess.Popen(neighbor_cmd, shell=True, stdout=subprocess.PIPE)
    neighbor_dict = json.loads(p1.stdout.read())

    neighbor_metadata_cmd = 'sonic-cfggen -d --var-json "DEVICE_NEIGHBOR_METADATA"'
    p2 = subprocess.Popen(neighbor_metadata_cmd, shell=True, stdout=subprocess.PIPE)
    neighbor_metadata_dict = json.loads(p2.stdout.read())

    #Swap Key and Value from interface: name to name: interface
    device2interface_dict = {}
    for port in natsorted(neighbor_dict.keys()):
        device2interface_dict[neighbor_dict[port]['name']] = {'localPort': port, 'neighborPort': neighbor_dict[port]['port']}

    header = ['LocalPort', 'Neighbor', 'NeighborPort', 'NeighborLoopback', 'NeighborMgmt', 'NeighborType']
    body = []
    if interfacename:
        for device in natsorted(neighbor_metadata_dict.keys()):
            if device2interface_dict[device]['localPort'] == interfacename:
                body.append([device2interface_dict[device]['localPort'],
                             device,
                             device2interface_dict[device]['neighborPort'],
                             neighbor_metadata_dict[device]['lo_addr'],
                             neighbor_metadata_dict[device]['mgmt_addr'],
                             neighbor_metadata_dict[device]['type']])
    else:
        for device in natsorted(neighbor_metadata_dict.keys()):
            body.append([device2interface_dict[device]['localPort'],
                         device,
                         device2interface_dict[device]['neighborPort'],
                         neighbor_metadata_dict[device]['lo_addr'],
                         neighbor_metadata_dict[device]['mgmt_addr'],
                         neighbor_metadata_dict[device]['type']])

    click.echo(tabulate(body, header))

# 'summary' subcommand ("show interfaces summary")
@interfaces.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def summary(interfacename, verbose):
    """Show interface status and information"""

    cmd = "/sbin/ifconfig"

    if interfacename is not None:
        cmd += " {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)


@interfaces.group(cls=AliasedGroup, default_if_no_args=False)
def transceiver():
    """Show SFP Transceiver information"""
    pass


@transceiver.command()
@click.argument('interfacename', required=False)
@click.option('-d', '--dom', 'dump_dom', is_flag=True, help="Also display Digital Optical Monitoring (DOM) data")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def eeprom(interfacename, dump_dom, verbose):
    """Show interface transceiver EEPROM information"""

    cmd = "sudo sfputil show eeprom"

    if dump_dom:
        cmd += " --dom"

    if interfacename is not None:
        cmd += " -p {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)


@transceiver.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def lpmode(interfacename, verbose):
    """Show interface transceiver low-power mode status"""

    cmd = "sudo sfputil show lpmode"

    if interfacename is not None:
        cmd += " -p {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)

@transceiver.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def presence(interfacename, verbose):
    """Show interface transceiver presence"""

    cmd = "sudo sfputil show presence"

    if interfacename is not None:
        cmd += " -p {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)


@interfaces.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def description(interfacename, verbose):
    """Show interface status, protocol and description"""

    cmd = "intfutil description"

    if interfacename is not None:
        cmd += " {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)


@interfaces.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def status(interfacename, verbose):
    """Show Interface status information"""

    cmd = "intfutil status"

    if interfacename is not None:
        cmd += " {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)


# 'counters' subcommand ("show interfaces counters")
@interfaces.command()
@click.option('-a', '--printall', is_flag=True)
@click.option('-c', '--clear', is_flag=True)
@click.option('-p', '--period')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counters(period, printall, clear, verbose):
    """Show interface counters"""

    cmd = "portstat"

    if clear:
        cmd += " -c"
    else:
        if printall:
            cmd += " -a"
        if period is not None:
            cmd += " -p {}".format(period)

    run_command(cmd, display_cmd=verbose)

# 'portchannel' subcommand ("show interfaces portchannel")
@interfaces.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def portchannel(verbose):
    """Show PortChannel information"""
    cmd = "teamshow"
    run_command(cmd, display_cmd=verbose)

#
# 'pfc' group ("show pfc ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def pfc():
    """Show details of the priority-flow-control (pfc) """
    pass

# 'counters' subcommand ("show interfaces pfccounters")
@pfc.command()
@click.option('-c', '--clear', is_flag=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counters(clear, verbose):
    """Show pfc counters"""

    cmd = "pfcstat"

    if clear:
        cmd += " -c"

    run_command(cmd, display_cmd=verbose)

#
# 'queue' group ("show queue ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def queue():
    """Show details of the queues """
    pass

# 'queuecounters' subcommand ("show queue counters")
@queue.command()
@click.argument('interfacename', required=False)
@click.option('-c', '--clear', is_flag=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counters(interfacename, clear, verbose):
    """Show queue counters"""

    cmd = "queuestat"

    if clear:
        cmd += " -c"
    else:
        if interfacename is not None:
            cmd += " -p {}".format(interfacename)

    run_command(cmd, display_cmd=verbose)

#
# 'pfc' group ###
#

@interfaces.group(cls=AliasedGroup, default_if_no_args=False)
def pfc():
    """Show PFC information"""
    pass


#
# 'pfc status' command ###
#

@pfc.command()
@click.argument('interface', type=click.STRING, required=False)
def status(interface):
    """Show PFC information"""
    if interface is None:
        interface = ""

    run_command("pfc show asymmetric {0}".format(interface))


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
# 'ip' group ("show ip ...")
#

# This group houses IP (i.e., IPv4) commands and subgroups
@cli.group()
def ip():
    """Show IP (IPv4) commands"""
    pass


#
# 'route' subcommand ("show ip route")
#

@ip.command()
@click.argument('ipaddress', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def route(ipaddress, verbose):
    """Show IP (IPv4) routing table"""
    cmd = 'sudo vtysh -c "show ip route'

    if ipaddress is not None:
        cmd += ' {}'.format(ipaddress)

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
@cli.group()
def ipv6():
    """Show IPv6 commands"""
    pass


#
# 'route' subcommand ("show ipv6 route")
#

@ipv6.command()
@click.argument('ipaddress', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def route(ipaddress, verbose):
    """Show IPv6 routing table"""
    cmd = 'sudo vtysh -c "show ipv6 route'

    if ipaddress is not None:
        cmd += ' {}'.format(ipaddress)

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
    @cli.command()
    @click.argument('bgp_args', nargs = -1, required = False)
    @click.option('--verbose', is_flag=True, help="Enable verbose output")
    def bgp(bgp_args, verbose):
        """BGP information"""
        bgp_cmd = "show bgp"
        for arg in bgp_args:
            bgp_cmd += " " + str(arg)
        cmd = 'sudo vtysh -c "{}"'.format(bgp_cmd)
        run_command(cmd, display_cmd=verbose)


#
# 'lldp' group ("show lldp ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def lldp():
    """LLDP (Link Layer Discovery Protocol) information"""
    pass

# Default 'lldp' command (called if no subcommands or their aliases were passed)
@lldp.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def neighbors(interfacename, verbose):
    """Show LLDP neighbors"""
    cmd = "sudo lldpctl"

    if interfacename is not None:
        cmd += " {}".format(interfacename)

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

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def platform():
    """Show platform-specific hardware info"""
    pass

platform.add_command(mlnx.mlnx)

# 'summary' subcommand ("show platform summary")
@platform.command()
def summary():
    """Show hardware platform information"""
    username = getpass.getuser()

    PLATFORM_TEMPLATE_FILE = "/tmp/cli_platform_{0}.j2".format(username)
    PLATFORM_TEMPLATE_CONTENTS = "Platform: {{ DEVICE_METADATA.localhost.platform }}\n" \
                                 "HwSKU: {{ DEVICE_METADATA.localhost.hwsku }}\n" \
                                 "ASIC: {{ asic_type }}"

    # Create a temporary Jinja2 template file to use with sonic-cfggen
    f = open(PLATFORM_TEMPLATE_FILE, 'w')
    f.write(PLATFORM_TEMPLATE_CONTENTS)
    f.close()

    cmd = "sonic-cfggen -d -y /etc/sonic/sonic_version.yml -t {0}".format(PLATFORM_TEMPLATE_FILE)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    # Clean up
    os.remove(PLATFORM_TEMPLATE_FILE)


# 'syseeprom' subcommand ("show platform syseeprom")
@platform.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def syseeprom(verbose):
    """Show system EEPROM information"""
    cmd = "sudo decode-syseeprom"
    run_command(cmd, display_cmd=verbose)

# 'psustatus' subcommand ("show platform psustatus")
@platform.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def psustatus(index, verbose):
    """Show PSU status information"""
    cmd = "sudo psuutil status"

    if index >= 0:
        cmd += " -i {}".format(index)

    run_command(cmd, display_cmd=verbose)

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
def version():
    """Show version information"""
    username = getpass.getuser()

    VERSION_TEMPLATE_FILE = "/tmp/cli_version_{0}.j2".format(username)
    VERSION_TEMPLATE_CONTENTS = "SONiC Software Version: SONiC.{{ build_version }}\n" \
                                "Distribution: Debian {{ debian_version }}\n" \
                                "Kernel: {{ kernel_version }}\n" \
                                "Build commit: {{ commit_id }}\n" \
                                "Build date: {{ build_date }}\n" \
                                "Built by: {{ built_by }}"

    # Create a temporary Jinja2 template file to use with sonic-cfggen
    f = open(VERSION_TEMPLATE_FILE, 'w')
    f.write(VERSION_TEMPLATE_CONTENTS)
    f.close()

    cmd = "sonic-cfggen -y /etc/sonic/sonic_version.yml -t {0}".format(VERSION_TEMPLATE_FILE)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    click.echo("Docker images:")
    cmd = 'sudo docker images --format "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.Size}}"'
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    # Clean up
    os.remove(VERSION_TEMPLATE_FILE)

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

@cli.group(cls=AliasedGroup, default_if_no_args=False)
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
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def techsupport(verbose):
    """Gather information for troubleshooting"""
    cmd = "sudo generate_dump -v"
    run_command(cmd, display_cmd=verbose)


#
# 'runningconfiguration' group ("show runningconfiguration")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
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
    cmd = "cat /etc/network/interfaces"

    if interfacename is not None:
        cmd += " | grep {} -A 4".format(interfacename)

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
    cmd = "cat /etc/ntp.conf"
    run_command(cmd, display_cmd=verbose)


#
# 'startupconfiguration' group ("show startupconfiguration ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def startupconfiguration():
    """Show startup configuration information"""
    pass


# 'bgp' subcommand  ("show startupconfiguration bgp")
@startupconfiguration.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def bgp(verbose):
    """Show BGP startup configuration"""
    cmd = "sudo docker ps | grep bgp | awk '{print$2}' | cut -d'-' -f3 | cut -d':' -f1"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
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
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def ntp(verbose):
    """Show NTP information"""
    cmd = "ntpq -p"
    run_command(cmd, display_cmd=verbose)


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

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def vlan():
    """Show VLAN information"""
    pass

@vlan.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def brief(verbose):
    """Show all bridge information"""
    cmd = "sudo brctl show"
    run_command(cmd, display_cmd=verbose)

@vlan.command()
@click.argument('bridge_name', required=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def id(bridge_name, verbose):
    """Show list of learned MAC addresses for particular bridge"""
    cmd = "sudo brctl showmacs {}".format(bridge_name)
    run_command(cmd, display_cmd=verbose)

@vlan.command()
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def config(redis_unix_socket_path):
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path
    config_db = ConfigDBConnector(**kwargs)
    config_db.connect(wait_for_init=False)
    data = config_db.get_table('VLAN')
    keys = data.keys()

    def tablelize(keys, data):
        table = []

        for k in keys:
            for m in data[k].get('members', []):
                r = []
                r.append(k)
                r.append(data[k]['vlanid'])
                r.append(m)

                entry = config_db.get_entry('VLAN_MEMBER', (k, m))
                mode = entry.get('tagging_mode')
                if mode == None:
                    r.append('?')
                else:
                    r.append(mode)

                table.append(r)

        return table

    header = ['Name', 'VID', 'Member', 'Mode']
    click.echo(tabulate(tablelize(keys, data), header))

@cli.command('services')
def services():
    """Show all daemon services"""
    cmd = "sudo docker ps --format '{{.Names}}'"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    while True:
        line = proc.stdout.readline()
        if line != '':
                print(line.rstrip()+'\t'+"docker")
                print("---------------------------")
                cmd = "sudo docker exec {} ps aux | sed '$d'".format(line.rstrip())
                proc1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
                print proc1.stdout.read()
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
            'failthrough': 'True (default)',
            'fallback': 'True (default)'
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
# 'mirror' group ###
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def mirror():
    """Show mirroring (Everflow) information"""
    pass


# 'session' subcommand  ("show mirror session")
@mirror.command()
@click.argument('session_name', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def session(session_name, verbose):
    """Show existing everflow sessions"""
    cmd = "acl-loader show session"

    if session_name is not None:
        cmd += " {}".format(session_name)

    run_command(cmd, display_cmd=verbose)


#
# 'acl' group ###
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
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
# 'ecn' command ("show ecn")
#
@cli.command('ecn')
def ecn():
    """Show ECN configuration"""
    cmd = "ecnconfig -l"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    click.echo(proc.stdout.read())


#
# 'reboot-cause' command ("show reboot-cause")
#
@cli.command('reboot-cause')
def reboot_cause():
    """Show cause of most recent reboot"""
    PREVIOUS_REBOOT_CAUSE_FILE = "/var/cache/sonic/previous-reboot-cause.txt"

    # At boot time, PREVIOUS_REBOOT_CAUSE_FILE is generated based on
    # the contents of the 'reboot cause' file as it was left when the device
    # went down for reboot. This file should always be created at boot,
    # but check first just in case it's not present.
    if not os.path.isfile(PREVIOUS_REBOOT_CAUSE_FILE):
        click.echo("Unable to determine cause of previous reboot\n")
    else:
        cmd = "cat {}".format(PREVIOUS_REBOOT_CAUSE_FILE)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        click.echo(proc.stdout.read())


#
# 'line' command ("show line")
#
@cli.command('line')
def line():
    """Show all /dev/ttyUSB lines and their info"""
    cmd = "consutil show"
    run_command(cmd, display_cmd=verbose)


if __name__ == '__main__':
    cli()
