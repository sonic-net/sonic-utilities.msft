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


def run_command(command, pager=False):
    if pager is True:
        #click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        click.echo_via_pager(p.stdout.read())
    else:
        #click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        click.echo(p.stdout.read())


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])


#
# 'cli' group (root group) ###
#

# This is our entrypoint - the main "Clear" command
@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
def cli():
    """SONiC command line - 'Clear' command"""
    pass


#
# 'ip' group ###
#

# This allows us to add commands to both cli and ip groups, allowing for
# "Clear <command>" and "Clear ip <command>" to function the same
@cli.group()
def ip():
    """Clear IP """
    pass


# 'ipv6' group

@cli.group()
def ipv6():
    """Clear IPv6 information"""
    pass


#
# Inserting BGP functionality into cli's clear parse-chain.
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
    def bgp(bgp_args):
        """BGP information"""
        bgp_cmd = "clear bgp"
        options = False
        for arg in bgp_args:
            bgp_cmd += " " + str(arg)
            options = True
        if options is True:
            command = 'sudo vtysh -c "{}"'.format(bgp_cmd)
        else:
            command = 'sudo vtysh -c "clear bgp *"'
        run_command(command)


@cli.command()
def counters():
    """Clear counters"""
    command = "portstat -c"
    run_command(command)

@cli.command()
def queuecounters():
    """Clear queue counters"""
    command = "queuestat -c"
    run_command(command)

@cli.command()
def pfccounters():
    """Clear pfc counters"""
    command = "pfcstat -c"
    run_command(command)

#
# 'arp' command ####
#

@click.command()
@click.argument('ipaddress', required=False)
def arp(ipaddress):
    """Clear IP ARP table"""
    if ipaddress is not None:
        command = 'sudo /usr/sbin/arp -d {}'.format(ipaddress)
        run_command(command)
    else:
        run_command("sudo ip -s -s neigh flush all")

# Add 'arp' command to both the root 'cli' group and the 'ip' subgroup
cli.add_command(arp)
ip.add_command(arp)

#
# 'fdb' command ####
#
@cli.group()
def fdb():
    """Clear FDB table"""
    pass

@fdb.command('all')
def clear_all_fdb():
    """Clear All FDB entries"""
    command = 'fdbclear'
    run_command(command)

# 'sonic-clear fdb port' and 'sonic-clear fdb vlan' will be added later
'''
@fdb.command('port')
@click.argument('portid', required=True)
def clear_port_fdb(portid):
    """Clear FDB entries learned from one port"""
    command = 'fdbclear' + ' -p ' + portid
    run_command(command)

@fdb.command('vlan')
@click.argument('vlanid', required=True)
def clear_vlan_fdb(vlanid):
    """Clear FDB entries learned in one VLAN"""
    command = 'fdbclear' + ' -v ' + vlanid
    run_command(command)
'''

#
# 'line' command
#
@cli.command('line')
@click.argument('linenum')
def line(linenum):
    """Clear preexisting connection to line"""
    cmd = "consutil clear " + str(linenum)
    run_command(cmd)

if __name__ == '__main__':
    cli()
