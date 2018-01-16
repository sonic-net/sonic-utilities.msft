#!/usr/sbin/env python

import sys
import os
import click
import json
import subprocess
import netaddr
from swsssdk import ConfigDBConnector
from minigraph import parse_device_desc_xml

import aaa

SONIC_CFGGEN_PATH = "sonic-cfggen"
MINIGRAPH_PATH = "/etc/sonic/minigraph.xml"
MINIGRAPH_BGP_SESSIONS = "minigraph_bgp"

#
# Helper functions
#

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

def _get_neighbor_ipaddress_by_hostname(hostname):
    """Returns string containing IP address of neighbor with hostname <hostname> or None if <hostname> not a neighbor
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    bgp_sessions = config_db.get_table('BGP_NEIGHBOR')
    for addr, session in bgp_sessions.iteritems():
        if session.has_key('name') and session['name'] == hostname:
            return addr
    return None

def _switch_bgp_session_status_by_addr(ipaddress, status, verbose):
    """Start up or shut down BGP session by IP address 
    """
    verb = 'Starting' if status == 'up' else 'Shutting'
    click.echo("{} {} BGP session with neighbor {}...".format(verb, status, ipaddress))
    config_db = ConfigDBConnector()
    config_db.connect()
    config_db.mod_entry('bgp_neighbor', ipaddress, {'admin_status': status})

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

def _change_hostname(hostname):
    current_hostname = os.uname()[1]
    if current_hostname != hostname:
        run_command('echo {} > /etc/hostname'.format(hostname), display_cmd=True)
        run_command('hostname -F /etc/hostname', display_cmd=True)
        run_command('sed -i "/\s{}$/d" /etc/hosts'.format(current_hostname), display_cmd=True)
        run_command('echo "127.0.0.1 {}" >> /etc/hosts'.format(hostname), display_cmd=True)

# Callback for confirmation prompt. Aborts if user enters "n"
def _abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()

def _restart_services():
    run_command("service hostname-config restart", display_cmd=True)
    run_command("service interfaces-config restart", display_cmd=True)
    run_command("service ntp-config restart", display_cmd=True)
    run_command("service rsyslog-config restart", display_cmd=True)
    run_command("service swss restart", display_cmd=True)
    run_command("service bgp restart", display_cmd=True)
    run_command("service teamd restart", display_cmd=True)
    run_command("service pmon restart", display_cmd=True)
    run_command("service lldp restart", display_cmd=True)
    run_command("service snmp restart", display_cmd=True)
    run_command("service dhcp_relay restart", display_cmd=True)

# This is our main entrypoint - the main 'config' command
@click.group()
def cli():
    """SONiC command line - 'config' command"""
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
cli.add_command(aaa.aaa)
cli.add_command(aaa.tacacs)

@cli.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Existing file will be overwritten, continue?')
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path())
def save(filename):
    """Export current config DB to a file on disk."""
    command = "{} -d --print-data > {}".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)

@cli.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload all config?')
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path(exists=True))
def load(filename):
    """Import a previous saved config DB dump file."""
    command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)

@cli.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Clear current and reload all config?')
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path(exists=True))
def reload(filename):
    """Clear current configuration and import a previous saved config DB dump file."""
    config_db = ConfigDBConnector()
    config_db.connect()
    client = config_db.redis_clients[config_db.CONFIG_DB]
    client.flushdb()
    command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)
    client.set(config_db.INIT_INDICATOR, True)
    _restart_services()

@cli.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload mgmt config?')
@click.argument('filename', default='/etc/sonic/device_desc.xml', type=click.Path(exists=True))
def load_mgmt_config(filename):
    """Reconfigure hostname and mgmt interface based on device description file."""
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
    print "Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`."

@cli.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload config from minigraph?')
def load_minigraph():
    """Reconfigure based on minigraph."""
    config_db = ConfigDBConnector()
    config_db.connect()
    client = config_db.redis_clients[config_db.CONFIG_DB]
    client.flushdb()
    if os.path.isfile('/etc/sonic/init_cfg.json'):
        command = "{} -m -j /etc/sonic/init_cfg.json --write-to-db".format(SONIC_CFGGEN_PATH)
    else:
        command = "{} -m --write-to-db".format(SONIC_CFGGEN_PATH)
    run_command(command, display_cmd=True)
    client.set(config_db.INIT_INDICATOR, True)
    #FIXME: After config DB daemon is implemented, we'll no longer need to restart every service.
    _restart_services()
    print "Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`."

#
# 'vlan' group
#
@cli.group()
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
    pass

@vlan.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.pass_context
def add_vlan(ctx, vid):
    db = ctx.obj['db']
    vlan = 'Vlan{}'.format(vid)
    if len(db.get_entry('VLAN', vlan)) != 0:
        print "{} already exists".format(vlan)
        raise click.Abort
    db.set_entry('VLAN', vlan, {'vlanid': vid})

@vlan.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.pass_context
def del_vlan(ctx, vid):
    db = ctx.obj['db']
    keys = [ (k, v) for k, v in db.get_table('VLAN_MEMBER') if k == 'Vlan{}'.format(vid) ]
    for k in keys:
        db.set_entry('VLAN_MEMBER', k, None)
    db.set_entry('VLAN', 'Vlan{}'.format(vid), None)

@vlan.group('member')
@click.pass_context
def vlan_member(ctx):
    pass

@vlan_member.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.option('-u', '--untagged', is_flag=True)
@click.pass_context
def add_vlan_member(ctx, vid, interface_name, untagged):
    db = ctx.obj['db']
    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.get_entry('VLAN', vlan_name)
    if len(vlan) == 0:
        print "{} doesn't exist".format(vlan_name)
        raise click.Abort
    members = vlan.get('members', [])
    if interface_name in members:
        print "{} is already a member of {}".format(interface_name, vlan_name)
        raise click.Abort
    members.append(interface_name)
    vlan['members'] = members
    db.set_entry('VLAN', vlan_name, vlan)
    db.set_entry('VLAN_MEMBER', (vlan_name, interface_name), {'tagging_mode': "untagged" if untagged else "tagged" })


@vlan_member.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.pass_context
def del_vlan_member(ctx, vid, interface_name):
    db = ctx.obj['db']
    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.get_entry('VLAN', vlan_name)
    if len(vlan) == 0:
        print "{} doesn't exist".format(vlan_name)
        raise click.Abort
    members = vlan.get('members', [])
    if interface_name not in members:
        print "{} is not a member of {}".format(interface_name, vlan_name)
        raise click.Abort
    members.remove(interface_name)
    if len(members) == 0:
        del vlan['members']
    else:
        vlan['members'] = members
    db.set_entry('VLAN', vlan_name, vlan)
    db.set_entry('VLAN_MEMBER', (vlan_name, interface_name), None)


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

#
# 'speed' subcommand
#

@interface.command()
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('interface_speed', metavar='<interface_speed>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def speed(interface_name, interface_speed, verbose):
    """Set interface speed"""
    command = "portconfig -p {} -s {}".format(interface_name, interface_speed)
    if verbose: command += " -vv"
    run_command(command, display_cmd=verbose)

#
# 'acl' group
#

@cli.group()
def acl():
    """ACL-related configuration tasks"""
    pass


#
# 'acl update' group
#

@acl.group()
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
    command = "acl-loader update full {}".format(file_name)
    run_command(command)


#
# 'incremental' subcommand
#

@update.command()
@click.argument('file_name', required=True)
def incremental(file_name):
    """Incremental update of ACL rule configuration."""
    command = "acl-loader update incremental {}".format(file_name)
    run_command(command)

#
# 'ecn' command
#
@cli.command()
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
    command = "ecnconfig -p %s" % profile
    if rmax is not None: command += " -rmax %d" % rmax
    if rmin is not None: command += " -rmin %d" % rmin
    if ymax is not None: command += " -ymax %d" % ymax
    if ymin is not None: command += " -ymin %d" % ymin
    if gmax is not None: command += " -gmax %d" % gmax
    if gmin is not None: command += " -gmin %d" % gmin
    if verbose: command += " -vv"
    run_command(command, display_cmd=verbose)

if __name__ == '__main__':
    cli()
