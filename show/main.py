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


def run_command(command):
    click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    (out, err) = proc.communicate()

    try:
        click.echo(out)
    except IOError as e:
        # In our version of Click (v6.6), click.echo() and click.echo_via_pager() do not properly handle
        # SIGPIPE, and if a pipe is broken before all output is processed (e.g., pipe output to 'head'),
        # it will result in a stack trace. This is apparently fixed upstream, but for now, we silently
        # ignore SIGPIPE here.
        if e.errno == errno.EPIPE:
            sys.exit(0)
        else:
            raise

    if proc.returncode != 0:
        sys.exit(proc.returncode)

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
def arp(ipaddress):
    """Show IP ARP table"""
    cmd = "/usr/sbin/arp -n"
    if ipaddress is not None:
        command = '{} {}'.format(cmd, ipaddress)
        run_command(command)
    else:
        run_command(cmd)


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

    command = 'sonic-cfggen -d --var-json "PORT"'
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

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

# 'summary' subcommand ("show interfaces summary")
@interfaces.command()
@click.argument('interfacename', required=False)
def summary(interfacename):
    """Show interface status and information"""

    cmd_ifconfig = "/sbin/ifconfig"

    if interfacename is not None:
        command = "{} {}".format(cmd_ifconfig, interfacename)
        run_command(command)
    else:
        command = cmd_ifconfig
        run_command(command)


@interfaces.group(cls=AliasedGroup, default_if_no_args=False)
def transceiver():
    """Show SFP Transceiver information"""
    pass


@transceiver.command()
@click.argument('interfacename', required=False)
def basic(interfacename):
    """Show basic interface transceiver information"""

    command = "sudo sfputil show eeprom"

    if interfacename is not None:
        command += " -p {}".format(interfacename)

    run_command(command)

@transceiver.command()
@click.argument('interfacename', required=False)
def details(interfacename):
    """Show interface transceiver details (Digital Optical Monitoring)"""

    command = "sudo sfputil show eeprom --dom"

    if interfacename is not None:
        command += " -p {}".format(interfacename)

    run_command(command)

@interfaces.command()
@click.argument('interfacename', required=False)
def description(interfacename):
    """Show interface status, protocol and description"""

    if interfacename is not None:
        command = "sudo vtysh -c 'show interface {}'".format(interfacename)
    else:
        command = "sudo vtysh -c 'show interface description'"

    run_command(command)


# 'counters' subcommand ("show interfaces counters")
@interfaces.command()
@click.option('-p', '--period')
@click.option('-a', '--printall', is_flag=True)
@click.option('-c', '--clear', is_flag=True)
def counters(period, printall, clear):
    """Show interface counters"""

    cmd = "portstat"

    if clear:
        cmd += " -c"
    else:
        if printall:
            cmd += " -a"
        if period is not None:
            cmd += " -p {}".format(period)

    run_command(cmd)

# 'portchannel' subcommand ("show interfaces portchannel")
@interfaces.command()
def portchannel():
    """Show PortChannel information"""
    run_command("teamshow")

@interfaces.command()
def status():
    """Show Interface status information"""
    run_command("interface_stat")

#
# 'mac' command ("show mac ...")
#

@cli.command()
@click.option('-v', '--vlan')
@click.option('-p', '--port')
def mac(vlan, port):
    """Show MAC (FDB) entries"""

    command = "fdbshow"

    if vlan is not None:
        command += " -v {}".format(vlan)

    if port is not None:
        command += " -p {}".format(port)

    run_command(command)

#
# 'ip' group ("show ip ...")
#

# This group houses IP (i.e., IPv4) commands and subgroups
@cli.group()
def ip():
    """Show IP (IPv4) commands"""
    pass

#
# 'bgp' group ("show ip bgp ...")
#

@ip.group(cls=AliasedGroup, default_if_no_args=False)
def bgp():
    """Show IPv4 BGP (Border Gateway Protocol) information"""
    pass

# 'neighbors' subcommand ("show ip bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=False)
def neighbors(ipaddress):
    """Show IP (IPv4) BGP neighbors"""
    if ipaddress is not None:
        command = 'sudo vtysh -c "show ip bgp neighbor {} "'.format(ipaddress)
        run_command(command)
    else:
        run_command('sudo vtysh -c "show ip bgp neighbor"')

# 'summary' subcommand ("show ip bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv4 BGP state"""
    run_command('sudo vtysh -c "show ip bgp summary"')

#
# 'route' subcommand ("show ip route")
#

@ip.command()
@click.argument('ipaddress', required=False)
def route(ipaddress):
    """Show IP (IPv4) routing table"""
    if ipaddress is not None:
        command = 'sudo vtysh -c "show ip route {}"'.format(ipaddress)
        run_command(command)
    else:
        run_command('sudo vtysh -c "show ip route"')


#
# 'ipv6' group ("show ipv6 ...")
#

# This group houses IPv6-related commands and subgroups
@cli.group()
def ipv6():
    """Show IPv6 commands"""
    pass

#
# 'bgp' group ("show ipv6 bgp ...")
#

@ipv6.group(cls=AliasedGroup, default_if_no_args=False)
def bgp():
    """Show IPv6 BGP (Border Gateway Protocol) information"""
    pass

# 'neighbors' subcommand ("show ip bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=True)
def neighbors(ipaddress):
    """Show IPv6 BGP neighbors"""
    command = 'sudo vtysh -c "show ipv6 bgp neighbor {} "'.format(ipaddress)
    run_command(command)

# 'summary' subcommand ("show ip bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv6 BGP state"""
    run_command('sudo vtysh -c "show ipv6 bgp summary"')

#
# 'route' subcommand ("show ipv6 route")
#

@ip.command()
@click.argument('ipaddress', required=False)
def route(ipaddress):
    """Show IPv6 routing table"""
    if ipaddress is not None:
        command = 'sudo vtysh -c "show ipv6 route {}"'.format(ipaddress)
        run_command(command)
    else:
        run_command('sudo vtysh -c "show ipv6 route"')


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
def neighbors(interfacename):
    """Show LLDP neighbors"""
    if interfacename is not None:
        command = "sudo lldpctl {}".format(interfacename)
        run_command(command)
    else:
        run_command("sudo lldpctl")

# 'table' subcommand ("show lldp table")
@lldp.command()
def table():
    """Show LLDP neighbors in tabular format"""
    run_command("sudo lldpshow")

#
# 'platform' group ("show platform ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def platform():
    """Show platform-specific hardware info"""
    pass

# 'summary' subcommand ("show platform summary")
@platform.command()
def summary():
    """Show hardware platform information"""
    username = getpass.getuser()

    PLATFORM_TEMPLATE_FILE = "/tmp/cli_platform_{0}.j2".format(username)
    PLATFORM_TEMPLATE_CONTENTS = "Platform: {{ platform }}\n" \
                                 "HwSKU: {{ DEVICE_METADATA['localhost']['hwsku'] }}\n" \
                                 "ASIC: {{ asic_type }}"

    # Create a temporary Jinja2 template file to use with sonic-cfggen
    f = open(PLATFORM_TEMPLATE_FILE, 'w')
    f.write(PLATFORM_TEMPLATE_CONTENTS)
    f.close()

    command = "sonic-cfggen -d -y /etc/sonic/sonic_version.yml -t {0}".format(PLATFORM_TEMPLATE_FILE)
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    # Clean up
    os.remove(PLATFORM_TEMPLATE_FILE)


# 'syseeprom' subcommand ("show platform syseeprom")
@platform.command()
def syseeprom():
    """Show system EEPROM information"""
    run_command("sudo decode-syseeprom")


#
# 'logging' command ("show logging")
#

@cli.command()
@click.argument('process', required=False)
@click.option('-l', '--lines')
@click.option('-f', '--follow', is_flag=True)
def logging(process, lines, follow):
    """Show system log"""
    if follow:
        run_command("sudo tail -f /var/log/syslog")
    else:
        command = "sudo cat /var/log/syslog"

        if process is not None:
            command += " | grep '{}'".format(process)

        if lines is not None:
            command += " | tail -{}".format(lines)

        run_command(command)


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

    command = "sonic-cfggen -y /etc/sonic/sonic_version.yml -t {0}".format(VERSION_TEMPLATE_FILE)
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    click.echo("Docker images:")
    command = 'sudo docker images --format "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.Size}}"'
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    # Clean up
    os.remove(VERSION_TEMPLATE_FILE)

#
# 'environment' command ("show environment")
#

@cli.command()
def environment():
    """Show environmentals (voltages, fans, temps)"""
    run_command('sudo sensors')


#
# 'processes' group ("show processes ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def processes():
    """Display process information"""
    pass

@processes.command()
def summary():
    """Show processes info"""
    # Run top batch mode to prevent unexpected newline after each newline
    run_command('ps -eo pid,ppid,cmd,%mem,%cpu ')


# 'cpu' subcommand ("show processes cpu")
@processes.command()
def cpu():
    """Show processes CPU info"""
    # Run top in batch mode to prevent unexpected newline after each newline
    run_command('top -bn 1 -o %CPU')
 
# 'memory' subcommand
@processes.command()
def memory():
    """Show processes memory info"""
    # Run top batch mode to prevent unexpected newline after each newline
    run_command('top -bn 1 -o %MEM')

#
# 'users' command ("show users")
#

@cli.command()
def users():
    """Show users"""
    run_command('who')


#
# 'techsupport' command ("show techsupport")
#

@cli.command()
def techsupport():
    """Gather information for troubleshooting"""
    run_command('sudo generate_dump -v')


#
# 'runningconfiguration' group ("show runningconfiguration")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def runningconfiguration():
    """Show current running configuration information"""
    pass


# 'bgp' subcommand ("show runningconfiguration bgp")
@runningconfiguration.command()
def bgp():
    """Show BGP running configuration"""
    run_command('sudo vtysh -c "show running-config"')


# 'interfaces' subcommand ("show runningconfiguration interfaces")
@runningconfiguration.command()
@click.argument('interfacename', required=False)
def interfaces(interfacename):
    """Show interfaces running configuration"""
    if interfacename is not None:
        command = "cat /etc/network/interfaces | grep {} -A 4".format(interfacename)
        run_command(command)
    else:
        run_command('cat /etc/network/interfaces')


# 'snmp' subcommand ("show runningconfiguration snmp")
@runningconfiguration.command()
@click.argument('server', required=False)
def snmp(server):
    """Show SNMP information"""
    if server is not None:
        command = 'sudo docker exec -it snmp cat /etc/snmp/snmpd.conf | grep -i agentAddress'
        run_command(command)
    else:
        command = 'sudo docker exec -it snmp cat /etc/snmp/snmpd.conf'
        run_command(command)

# 'ntp' subcommand ("show runningconfiguration ntp")
@runningconfiguration.command()
def ntp():
    """Show NTP running configuration"""
    run_command('cat /etc/ntp.conf')


#
# 'startupconfiguration' group ("show startupconfiguration ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def startupconfiguration():
    """Show startup configuration information"""
    pass


# 'bgp' subcommand  ("show startupconfiguration bgp")
@startupconfiguration.command()
def bgp():
    """Show BGP startup configuration"""
    command = "sudo docker ps | grep bgp | awk '{print$2}' | cut -d'-' -f3 | cut -d':' -f1"
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    result = proc.stdout.read().rstrip()
    click.echo("Routing-Stack is: {}".format(result))
    if result == "quagga":
        run_command('sudo docker exec -it bgp cat /etc/quagga/bgpd.conf')
    elif result == "frr":
        run_command('sudo docker exec -it bgp cat /etc/frr/bgpd.conf')
    elif result == "gobgp":
        run_command('sudo docker exec -it bgp cat /etc/gpbgp/bgpd.conf')
    else:
        click.echo("unidentified routing-stack")

#
# 'ntp' command ("show ntp")
#

@cli.command()
def ntp():
    """Show NTP information"""
    run_command('ntpq -p')


#
# 'uptime' command ("show uptime")
#

@cli.command()
def uptime():
    """Show system uptime"""
    run_command('uptime -p')

@cli.command()
def clock():
    """Show date and time"""
    run_command('date')

@cli.command('system-memory')
def system_memory():
    """Show memory information"""
    command="free -m"
    run_command(command)

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def vlan():
    """Show VLAN information"""
    pass

@vlan.command()
def brief():
    """Show all bridge information"""
    command="sudo brctl show"
    run_command(command)

@vlan.command()
@click.argument('bridge_name', required=True)
def id(bridge_name):
    """Show list of learned MAC addresses for particular bridge"""
    command="sudo brctl showmacs {}".format(bridge_name)
    run_command(command)

@cli.command('services')
def services():
    """Show all daemon services"""
    command = "sudo docker ps --format '{{.Names}}'"
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    while True:
        line = proc.stdout.readline()
        if line != '':
                print(line.rstrip()+'\t'+"docker")
                print("---------------------------")
                command = "sudo docker exec -it {} ps -ef | sed '$d'".format(line.rstrip())
                proc1 = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
                print proc1.stdout.read()
        else:
                break

if __name__ == '__main__':
    cli()
