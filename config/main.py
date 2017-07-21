#!/usr/sbin/env python

import sys
import os
import click
import json
import subprocess
from swsssdk import ConfigDBConnector

SONIC_CFGGEN_PATH = "sonic-cfggen"
MINIGRAPH_PATH = "/etc/sonic/minigraph.xml"
MINIGRAPH_BGP_SESSIONS = "minigraph_bgp"

#
# Helper functions
#

def run_command(command, pager=False, display_cmd=False):
    """Run bash command and print output to stdout
    """
    if display_cmd == True:
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    stdout = p.communicate()[0]
    p.wait()

    if len(stdout) > 0:
        if pager is True:
            click.echo_via_pager(p.stdout.read())
        else:
            click.echo(p.stdout.read())

    if p.returncode != 0:
        sys.exit(p.returncode)

def _get_bgp_neighbors():
    """Returns BGP neighbor dict from minigraph
    """
    proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-m', MINIGRAPH_PATH, '--var-json', MINIGRAPH_BGP_SESSIONS],
                            stdout=subprocess.PIPE,
                            shell=False,
                            stderr=subprocess.STDOUT)
    stdout = proc.communicate()[0]
    proc.wait()
    return json.loads(stdout.rstrip('\n'))

def _is_neighbor_ipaddress(ipaddress):
    """Returns True if a neighbor has the IP address <ipaddress>, False if not
    """
    bgp_session_list = _get_bgp_neighbors()
    for session in bgp_session_list:
        if session['addr'] == ipaddress:
            return True
    return False

def _get_all_neighbor_ipaddresses():
    """Returns list of strings containing IP addresses of all BGP neighbors
    """
    bgp_session_list = _get_bgp_neighbors()
    return [item['addr'] for item in bgp_session_list]

def _get_neighbor_ipaddress_by_hostname(hostname):
    """Returns string containing IP address of neighbor with hostname <hostname> or None if <hostname> not a neighbor
    """
    bgp_session_list = _get_bgp_neighbors()
    for session in bgp_session_list:
        if session['name'] == hostname:
            return session['addr']
    return None

def _switch_bgp_session_status_by_addr(ipaddress, status, verbose):
    """Start up or shut down BGP session by IP address 
    """
    verb = 'Starting' if status == 'up' else 'Shutting'
    click.echo("{} {} BGP session with neighbor {}...".format(verb, status, ipaddress))
    config_db = ConfigDBConnector()
    config_db.connect()
    config_db.set_entry('bgp_neighbor', ipaddress, {'admin_status': status})

def _switch_bgp_session_status(ipaddr_or_hostname, status, verbose):
    """Start up or shut down BGP session by IP address or hostname
    """
    if _is_neighbor_ipaddress(ipaddr_or_hostname):
        ipaddress = ipaddr_or_hostname
    else:
        # If <ipaddr_or_hostname> is not the IP address of a neighbor, check to see if it's a hostname
        ipaddress = _get_neighbor_ipaddress_by_hostname(ipaddr_or_hostname)
    if ipaddress == None:
        print "Error: could not locate neighbor '{}'".format(ipaddr_or_hostname)
        raise click.Abort
    _switch_bgp_session_status_by_addr(ipaddress, status, verbose)

# This is our main entrypoint - the main 'config' command
@click.group()
def cli():
    """SONiC command line - 'config' command"""
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

#
# 'bgp' group
#

@cli.group()
def bgp():
    """BGP-related configuration tasks"""
    pass

#
# 'shutdown' subgroup
#

@bgp.group()
def shutdown():
    """Shut down BGP session(s)"""
    pass

# 'all' subcommand
@shutdown.command()
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Shut down all BGP sessions"""
    bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses()
    for ipaddress in bgp_neighbor_ip_list:
        _switch_bgp_session_status_by_addr(ipaddress, 'down', verbose)

# 'neighbor' subcommand
@shutdown.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Shut down BGP session by neighbor IP address or hostname"""
    _switch_bgp_session_status(ipaddr_or_hostname, 'down', verbose)

@bgp.group()
def startup():
    """Start up BGP session(s)"""
    pass

# 'all' subcommand
@startup.command()
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Start up all BGP sessions"""
    bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses()
    for ipaddress in bgp_neighbor_ip_list:
        _switch_bgp_session_status(ipaddress, 'up', verbose)

# 'neighbor' subcommand
@startup.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Start up BGP session by neighbor IP address or hostname"""
    _switch_bgp_session_status(ipaddr_or_hostname, 'up', verbose)

#
# 'interface' group
#

@cli.group()
def interface():
    """Interface-related configuration tasks"""
    pass

#
# 'shutdown' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def shutdown(interface_name, verbose):
    """Shut down interface"""
    command = "ip link set {} down".format(interface_name)
    run_command(command, display_cmd=verbose)

#
# 'startup' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def startup(interface_name, verbose):
    """Start up interface"""
    command = "ip link set {} up".format(interface_name)
    run_command(command, display_cmd=verbose)


if __name__ == '__main__':
    cli()
