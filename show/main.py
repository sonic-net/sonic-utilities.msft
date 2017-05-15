#! /usr/bin/python -u

import click
import os
import subprocess
from click_default_group import DefaultGroup

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
# DefaultFroup is a superclass of click.Group which calls a default subcommand instead of showing
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


def run_command(command, pager=False):
    if pager is True:
        click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        click.echo_via_pager(p.stdout.read())
    else:
        click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        click.echo(p.stdout.read())


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '?'])


#
# 'cli' group (root group) ###
#

# THis is our entrypoint - the main "show" command
# TODO: Consider changing function name to 'show' for better understandability
@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
def cli():
    """SONiC command line - 'show' command"""
    pass


#
# 'ip' group ###
#

# This allows us to add commands to both cli and ip groups, allowing for
# "show <command>" and "show ip <command>" to function the same
@cli.group()
def ip():
    """Show IP commands"""
    pass


#
# 'interfaces' group ####
#

# We use the "click.group()" decorator because we want to add this group
# to more than one group, which we do using the "add_command() methods below.
@click.group(cls=AliasedGroup, default_if_no_args=False)
def interfaces():
    pass

# Add 'interfaces' group to both the root 'cli' group and the 'ip' subgroup
cli.add_command(interfaces)
ip.add_command(interfaces)

# 'summary' subcommand
@interfaces.command()
@click.argument('interfacename', required=False)
@click.argument('sfp', required=False)
def summary(interfacename, sfp):
    """Show interface status and information"""

    cmd_ifconfig = "/sbin/ifconfig"

    if interfacename is not None and sfp is not None:
        command = "sfputil -p {}".format(interfacename)
        run_command(command, pager=True)
    # FIXME: show sfp without an interface is bugged and doesn't work right.
    elif sfp is not None:
        run_command("sfputil")
    elif interfacename is not None:
        command = "{} {}".format(cmd_ifconfig, interfacename)
        run_command(command)
    else:
        command = cmd_ifconfig
        run_command(command, pager=True)

# 'counters' subcommand
@interfaces.command()
def counters():
    """Show interface counters"""
    run_command("portstat -a -p 30", pager=True)

# 'portchannel' subcommand
@interfaces.command()
def portchannel():
    """Show PortChannel information"""
    run_command("teamshow", pager=True)


#
# 'lldp' group ####
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def lldp():
    pass

# Default 'lldp' command (called if no subcommands or their aliases were passed)
@lldp.command()
@click.argument('interfacename', required=False)
def neighbors(interfacename):
    """Show LLDP neighbors"""
    if interfacename is not None:
        command = "lldpctl {}".format(interfacename)
        run_command(command)
    else:
        run_command("lldpctl", pager=True)

# 'tables' subcommand ####
@lldp.command()
def table():
    """Show LLDP neighbors in tabular format"""
    run_command("lldpshow", pager=True)

#
# 'bgp' group ####
#

# We use the "click.group()" decorator because we want to add this group
# to more than one group, which we do using the "add_command() methods below.
@click.group(cls=AliasedGroup, default_if_no_args=False)
def bgp():
    """Show BGP (Border Gateway Protocol) information"""
    pass

# Add 'bgp' group to both the root 'cli' group and the 'ip' subgroup
cli.add_command(bgp)
ip.add_command(bgp)

# 'neighbors' subcommand ####
@bgp.command()
@click.argument('ipaddress', required=False)
def neighbor(ipaddress):
    """Show BGP neighbors"""
    if ipaddress is not None:
        command = 'vtysh -c "show ip bgp neighbor {} "'.format(ipaddress)
        run_command(command)
    else:
        run_command('vtysh -c "show ip bgp neighbor"', pager=True)

# 'summary' subcommand ####
@bgp.command()
def summary():
    """Show summarized information of BGP state"""
    run_command('vtysh -c "show ip bgp summary"')


#
# 'platform' group ####
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def platform():
    pass

@platform.command()
def summary():
    """Show hardware platform information"""
    click.echo("")

    PLATFORM_TEMPLATE_FILE = "/tmp/cli_platform.j2"
    PLATFORM_TEMPLATE_CONTENTS = "Platform: {{ platform }}\n" \
                                 "HwSKU: {{ minigraph_hwsku }}\n" \
                                 "ASIC: {{ asic_type }}"

    # Create a temporary Jinja2 template file to use with sonic-cfggen
    f = open(PLATFORM_TEMPLATE_FILE, 'w')
    f.write(PLATFORM_TEMPLATE_CONTENTS)
    f.close()

    command = "sonic-cfggen -m /etc/sonic/minigraph.xml -y /etc/sonic/sonic_version.yml -t {0}".format(PLATFORM_TEMPLATE_FILE)
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    # Clean up
    os.remove(PLATFORM_TEMPLATE_FILE)

# 'syseeprom' subcommand ####
@platform.command()
def syseeprom():
    """Show system EEPROM information"""
    run_command("sudo decode-syseeprom")


#
# 'logging' command ####
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

        run_command(command, pager=True)


#
# 'version' command ###
#

@cli.command()
def version():
    """Show version information"""
    click.echo("")

    VERSION_TEMPLATE_FILE = "/tmp/cli_version.j2"
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
    command = 'docker images --format "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.Size}}"'
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    click.echo(p.stdout.read())

    # Clean up
    os.remove(VERSION_TEMPLATE_FILE)

#
# 'environment' command ###
#

@cli.command()
def environment():
    """Show environmentals (voltages, fans, temps)"""
    run_command('sensors', pager=True)


#
# 'processes' group ###
#

@cli.group()
def processes():
    """Display process information"""
    pass

# 'cpu' subcommand
@processes.command()
def cpu():
    """Show processes CPU info"""
    # Run top batch mode to prevent unexpected newline after each newline
    run_command('top -bn 1', pager=True)


#
# 'users' command ###
#

@cli.command()
def users():
    """Show users"""
    run_command('who')


#
# 'techsupport' command ###
#

@cli.command()
def techsupport():
    """Gather information for troubleshooting"""
    run_command('generate_dump -v')


#
# 'runningconfiguration' group ###
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def runningconfiguration():
    """Show current running configuration information"""
    pass


# 'bgp' subcommand
@runningconfiguration.command()
def bgp():
    """Show BGP running configuration"""
    run_command('vtysh -c "show running-config"', pager=True)


# 'interfaces' subcommand
@runningconfiguration.command()
@click.argument('interfacename', required=False)
def interfaces(interfacename):
    """Show interfaces running configuration"""
    if interfacename is not None:
        command = "cat /etc/network/interfaces | grep {} -A 4".format(interfacename)
        run_command(command)
    else:
        run_command('cat /etc/network/interfaces', pager=True)


# 'snmp' subcommand
@runningconfiguration.command()
def snmp():
    """Show SNMP running configuration"""
    command = 'docker exec -it snmp cat /etc/snmp/snmpd.conf'
    run_command(command, pager=True)


# 'ntp' subcommand
@runningconfiguration.command()
def ntp():
    """Show NTP running configuration"""
    run_command('cat /etc/ntp.conf', pager=True)


# 'startupconfiguration' group ###
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def startupconfiguration():
    """Show startup configuration information"""
    pass


# 'bgp' subcommand
@startupconfiguration.command()
def bgp():
    """Show BGP startup configuration"""
    run_command('docker exec -it bgp cat /etc/quagga/bgpd.conf')


#
# 'arp' command ####
#

@click.command()
@click.argument('ipaddress', required=False)
def arp(ipaddress):
    """Show ip arp table"""
    cmd = "/usr/sbin/arp"
    if ipaddress is not None:
        command = '{} {}'.format(cmd, ipaddress)
        run_command(command)
    else:
        run_command(cmd, pager=True)

# Add 'arp' command to both the root 'cli' group and the 'ip' subgroup
cli.add_command(arp)
ip.add_command(arp)


#
# 'route' command ####
#

@click.command()
@click.argument('ipaddress', required=False)
def route(ipaddress):
    """Show ip routing table"""
    if ipaddress is not None:
        command = 'vtysh -c "show ip route {}"'.format(ipaddress)
        run_command(command)
    else:
        run_command('vtysh -c "show ip route"', pager=True)

# Add 'route' command to both the root 'cli' group and the 'ip' subgroup
cli.add_command(route)
ip.add_command(route)


#
# 'ntp' command ####
#

@cli.command()
def ntp():
    """Show NTP information"""
    run_command('ntpq -p')


#
# 'uptime' command ####
#

@cli.command()
def uptime():
    """Show system uptime"""
    run_command('uptime -p')


if __name__ == '__main__':
    cli()
