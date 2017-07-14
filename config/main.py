#!/usr/sbin/env python

import sys
import os
import click
import json
import subprocess

SONIC_CFGGEN_PATH = "/usr/local/bin/sonic-cfggen"
MINIGRAPH_PATH = "/etc/sonic/minigraph.xml"
MINIGRAPH_BGP_ASN_KEY = "minigraph_bgp_asn"
MINIGRAPH_BGP_SESSIONS = "minigraph_bgp"

BGP_ADMIN_STATE_YML_PATH = "/etc/sonic/bgp_admin.yml"

#
# Helper functions
#

# Run bash command and print output to stdout
def run_command(command, pager=False, display_cmd=False):
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

# Returns BGP ASN as a string
def _get_bgp_asn_from_minigraph():
    # Get BGP ASN from minigraph
    proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-m', MINIGRAPH_PATH, '--var-json', MINIGRAPH_BGP_ASN_KEY],
                            stdout=subprocess.PIPE,
                            shell=False,
                            stderr=subprocess.STDOUT)
    stdout = proc.communicate()[0]
    proc.wait()
    return json.loads(stdout.rstrip('\n'))

# Returns True if a neighbor has the IP address <ipaddress>, False if not
def _is_neighbor_ipaddress(ipaddress):
    # Get BGP sessions from minigraph
    proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-m', MINIGRAPH_PATH, '--var-json', MINIGRAPH_BGP_SESSIONS],
                            stdout=subprocess.PIPE,
                            shell=False,
                            stderr=subprocess.STDOUT)
    stdout = proc.communicate()[0]
    proc.wait()
    bgp_session_list = json.loads(stdout.rstrip('\n'))

    for session in bgp_session_list:
        if session['addr'] == ipaddress:
            return True

    return False

# Returns list of strings containing IP addresses of all BGP neighbors
def _get_all_neighbor_ipaddresses():
    # Get BGP sessions from minigraph
    proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-m', MINIGRAPH_PATH, '--var-json', MINIGRAPH_BGP_SESSIONS],
                            stdout=subprocess.PIPE,
                            shell=False,
                            stderr=subprocess.STDOUT)
    stdout = proc.communicate()[0]
    proc.wait()
    bgp_session_list = json.loads(stdout.rstrip('\n'))

    bgp_neighbor_ip_list =[]

    for session in bgp_session_list:
        bgp_neighbor_ip_list.append(session['addr'])

    return bgp_neighbor_ip_list



# Returns string containing IP address of neighbor with hostname <hostname> or None if <hostname> not a neighbor
def _get_neighbor_ipaddress_by_hostname(hostname):
    # Get BGP sessions from minigraph
    proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-m', MINIGRAPH_PATH, '--var-json', MINIGRAPH_BGP_SESSIONS],
                            stdout=subprocess.PIPE,
                            shell=False,
                            stderr=subprocess.STDOUT)
    stdout = proc.communicate()[0]
    proc.wait()
    bgp_session_list = json.loads(stdout.rstrip('\n'))

    for session in bgp_session_list:
        if session['name'] == hostname:
            return session['addr']

    return None

# Shut down BGP session by IP address and modify bgp_admin.yml accordingly
def _bgp_session_shutdown(bgp_asn, ipaddress, verbose):
    click.echo("Shutting down BGP session with neighbor {}...".format(ipaddress))

    # Shut down the BGP session
    command = "vtysh -c 'configure terminal' -c 'router bgp {}' -c 'neighbor {} shutdown'".format(bgp_asn, ipaddress)
    run_command(command, display_cmd=verbose)

    if os.path.isfile(BGP_ADMIN_STATE_YML_PATH):
        # Remove existing item in bgp_admin.yml about the admin state of this neighbor
        command = "sed -i \"/^\s*{}:/d\" {}".format(ipaddress, BGP_ADMIN_STATE_YML_PATH)
        run_command(command, display_cmd=verbose)

        # and add a new line mark it as off
        command = "echo \"  {}: off\" >> {}".format(ipaddress, BGP_ADMIN_STATE_YML_PATH)
        run_command(command, display_cmd=verbose)

# Start up BGP session by IP address and modify bgp_admin.yml accordingly
def _bgp_session_startup(bgp_asn, ipaddress, verbose):
    click.echo("Starting up BGP session with neighbor {}...".format(ipaddress))

    # Start up the BGP session
    command = "vtysh -c 'configure terminal' -c 'router bgp {}' -c 'no neighbor {} shutdown'".format(bgp_asn, ipaddress)
    run_command(command, display_cmd=verbose)

    if os.path.isfile(BGP_ADMIN_STATE_YML_PATH):
        # Remove existing item in bgp_admin.yml about the admin state of this neighbor
        command = "sed -i \"/^\s*{}:/d\" {}".format(ipaddress, BGP_ADMIN_STATE_YML_PATH)
        run_command(command, display_cmd=verbose)

        # and add a new line mark it as on
        command = "echo \"  {}: on\" >> {}".format(ipaddress, BGP_ADMIN_STATE_YML_PATH)
        run_command(command, display_cmd=verbose)


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

    bgp_asn = _get_bgp_asn_from_minigraph()
    bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses()

    for ipaddress in bgp_neighbor_ip_list:
        _bgp_session_shutdown(bgp_asn, ipaddress, verbose)

# 'neighbor' subcommand
@shutdown.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Shut down BGP session by neighbor IP address or hostname"""
    bgp_asn = _get_bgp_asn_from_minigraph()

    if _is_neighbor_ipaddress(ipaddr_or_hostname):
        ipaddress = ipaddr_or_hostname
    else:
        # If <ipaddr_or_hostname> is not the IP address of a neighbor, check to see if it's a hostname
        ipaddress = _get_neighbor_ipaddress_by_hostname(ipaddr_or_hostname)

    if ipaddress == None:
        print "Error: could not locate neighbor '{}'".format(ipaddr_or_hostname)
        raise click.Abort

    _bgp_session_shutdown(bgp_asn, ipaddress, verbose)


@bgp.group()
def startup():
    """Start up BGP session(s)"""
    pass

# 'all' subcommand
@startup.command()
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def all(verbose):
    """Start up all BGP sessions"""
    bgp_asn = _get_bgp_asn_from_minigraph()
    bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses()

    for ipaddress in bgp_neighbor_ip_list:
        _bgp_session_startup(bgp_asn, ipaddress, verbose)

# 'neighbor' subcommand
@startup.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Start up BGP session by neighbor IP address or hostname"""
    bgp_asn = _get_bgp_asn_from_minigraph()

    if _is_neighbor_ipaddress(ipaddr_or_hostname):
        ipaddress = ipaddr_or_hostname
    else:
        # If <ipaddr_or_hostname> is not the IP address of a neighbor, check to see if it's a hostname
        ipaddress = _get_neighbor_ipaddress_by_hostname(ipaddr_or_hostname)

    if ipaddress == None:
        print "Error: could not locate neighbor '{}'".format(ipaddr_or_hostname)
        raise click.Abort

    _bgp_session_startup(bgp_asn, ipaddress, verbose)


if __name__ == '__main__':
    cli()
