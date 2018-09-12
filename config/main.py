#!/usr/sbin/env python

import sys
import os
import click
import json
import subprocess
import netaddr
import re
from swsssdk import ConfigDBConnector
from natsort import natsorted
from minigraph import parse_device_desc_xml

import aaa
import mlnx

SONIC_CFGGEN_PATH = "sonic-cfggen"

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


def interface_alias_to_name(interface_alias):
    """Return default interface name if alias name is given as argument
    """

    cmd = 'sonic-cfggen -d --var-json "PORT"'
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

    port_dict = json.loads(p.stdout.read())

    if interface_alias is not None:
        for port_name in natsorted(port_dict.keys()):
            if interface_alias == port_dict[port_name]['alias']:
                return port_name
        print "Invalid interface {}".format(interface_alias)

    return None


def interface_name_to_alias(interface_name):
    """Return alias interface name if default name is given as argument
    """

    cmd = 'sonic-cfggen -d --var-json "PORT"'
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

    port_dict = json.loads(p.stdout.read())

    if interface_name is not None:
        for port_name in natsorted(port_dict.keys()):
            if interface_name == port_name:
                return port_dict[port_name]['alias']
        print "Invalid interface {}".format(interface_alias)

    return None


def set_interface_mode(mode):
    """Modify SONIC_CLI_IFACE_MODE env variable in user .bashrc
    """
    user = os.getenv('SUDO_USER')
    bashrc_ifacemode_line = "SONIC_CLI_IFACE_MODE={}".format(mode)

    if not user:
        user = os.getenv('USER')

    if user != "root":
        bashrc = "/home/{}/.bashrc".format(user)
    else:
        raise click.Abort()

    f = open(bashrc, 'r')
    filedata = f.read()
    f.close()

    if "SONIC_CLI_IFACE_MODE" not in filedata:
        newdata = filedata + bashrc_ifacemode_line
        newdata += "\n"
    else:
        newdata = re.sub(r"SONIC_CLI_IFACE_MODE=\w+",
                         bashrc_ifacemode_line, filedata)
    f = open(bashrc, 'w')
    f.write(newdata)
    f.close()
    print "Please logout and log back in for changes take effect."


def get_interface_mode():
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
        print "Error: could not locate neighbor '{}'".format(ipaddr_or_hostname)
        raise click.Abort

    for ip_addr in ip_addrs:
        _change_bgp_session_status_by_addr(ip_addr, status, verbose)

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

# Callback for confirmation prompt. Aborts if user enters "n"
def _abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()

def _stop_services():
    services = [
        'dhcp_relay',
        'swss',
        'snmp',
        'lldp',
        'pmon',
        'bgp',
        'teamd',
    ]
    for service in services:
        run_command("systemctl stop %s" % service, display_cmd=True)

def _restart_services():
    services = [
        'hostname-config',
        'interfaces-config',
        'ntp-config',
        'rsyslog-config',
        'swss',
        'bgp',
        'teamd',
        'pmon',
        'lldp',
        'snmp',
        'dhcp_relay',
    ]
    for service in services:
        run_command("systemctl restart %s" % service, display_cmd=True)


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
@click.option('-y', '--yes', is_flag=True)
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path(exists=True))
def load(filename, yes):
    """Import a previous saved config DB dump file."""
    if not yes:
        click.confirm('Load config from the file %s?' % filename, abort=True)
    command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)

@cli.command()
@click.option('-y', '--yes', is_flag=True)
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path(exists=True))
def reload(filename, yes):
    """Clear current configuration and import a previous saved config DB dump file."""
    if not yes:
        click.confirm('Clear current config and reload config from the file %s?' % filename, abort=True)
    #Stop services before config push
    _stop_services()
    config_db = ConfigDBConnector()
    config_db.connect()
    client = config_db.redis_clients[config_db.CONFIG_DB]
    client.flushdb()
    command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)
    client.set(config_db.INIT_INDICATOR, 1)
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
    #Stop services before config push
    _stop_services()

    config_db = ConfigDBConnector()
    config_db.connect()
    client = config_db.redis_clients[config_db.CONFIG_DB]
    client.flushdb()
    if os.path.isfile('/etc/sonic/init_cfg.json'):
        command = "{} -H -m -j /etc/sonic/init_cfg.json --write-to-db".format(SONIC_CFGGEN_PATH)
    else:
        command = "{} -H -m --write-to-db".format(SONIC_CFGGEN_PATH)
    run_command(command, display_cmd=True)
    client.set(config_db.INIT_INDICATOR, 1)
    run_command('pfcwd start_default', display_cmd=True)
    if os.path.isfile('/etc/sonic/acl.json'):
        run_command("acl-loader update full /etc/sonic/acl.json", display_cmd=True)
    run_command("config qos reload", display_cmd=True)
    #FIXME: After config DB daemon is implemented, we'll no longer need to restart every service.
    _restart_services()
    print "Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`."

#
# 'mirror' group
#
@cli.group()
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
def add(session_name, src_ip, dst_ip, dscp, ttl, gre_type, queue):
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
# 'qos' group
#
@cli.group()
@click.pass_context
def qos(ctx):
    pass

@qos.command('clear')
def clear():
    _clear_qos()

@qos.command('reload')
def reload():
    _clear_qos()
    platform = _get_platform()
    hwsku = _get_hwsku()
    buffer_template_file = os.path.join('/usr/share/sonic/device/', platform, hwsku, 'buffers.json.j2')
    if os.path.isfile(buffer_template_file):
        command = "{} -m -t {} >/tmp/buffers.json".format(SONIC_CFGGEN_PATH, buffer_template_file)
        run_command(command, display_cmd=True)

        qos_template_file = os.path.join('/usr/share/sonic/device/', platform, hwsku, 'qos.json.j2')
        if os.path.isfile(qos_template_file):
            command = "{} -m -t {} >/tmp/qos.json".format(SONIC_CFGGEN_PATH, qos_template_file)
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
# 'warm_restart' group
#
@cli.group()
@click.pass_context
@click.option('-s', '--redis-unix-socket-path', help='unix socket path for redis connection')
def warm_restart(ctx, redis_unix_socket_path):
    """warm_restart-related configuration tasks"""
    kwargs = {}
    if redis_unix_socket_path:
        kwargs['unix_socket_path'] = redis_unix_socket_path
    config_db = ConfigDBConnector(**kwargs)
    config_db.connect(wait_for_init=False)
    ctx.obj = {'db': config_db}
    pass

@warm_restart.command('enable')
@click.argument('module', metavar='<module>', default='system', required=False, type=click.Choice(["system", "swss"]))
@click.pass_context
def warm_restart_enable(ctx, module):
    db = ctx.obj['db']
    db.mod_entry('WARM_RESTART', module, {'enable': 'true'})

@warm_restart.command('disable')
@click.argument('module', metavar='<module>', default='system', required=False, type=click.Choice(["system", "swss"]))
@click.pass_context
def warm_restart_enable(ctx, module):
    db = ctx.obj['db']
    db.mod_entry('WARM_RESTART', module, {'enable': 'false'})

@warm_restart.command('neighsyncd_timer')
@click.argument('seconds', metavar='<seconds>', required=True, type=int)
@click.pass_context
def warm_restart_neighsyncd_timer(ctx, seconds):
    db = ctx.obj['db']
    if seconds not in range(1,9999):
        print "neighsyncd warm restart timer must be in range 1-9999"
        raise click.Abort
    db.mod_entry('WARM_RESTART', 'swss', {'neighsyncd_timer': seconds})

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

    if get_interface_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            raise click.Abort()

    if len(vlan) == 0:
        print "{} doesn't exist".format(vlan_name)
        raise click.Abort()
    members = vlan.get('members', [])
    if interface_name in members:
        if get_interface_mode() == "alias":
            interface_name = interface_name_to_alias(interface_name)
            if interface_name is None:
                raise click.Abort()
            print "{} is already a member of {}".format(interface_name,
                                                        vlan_name)
        else:
            print "{} is already a member of {}".format(interface_name,
                                                        vlan_name)
        raise click.Abort()
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

    if get_interface_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            raise click.Abort()

    if len(vlan) == 0:
        print "{} doesn't exist".format(vlan_name)
        raise click.Abort()
    members = vlan.get('members', [])
    if interface_name not in members:
        if get_interface_mode() == "alias":
            interface_name = interface_name_to_alias(interface_name)
            if interface_name is None:
                raise click.Abort()
            print "{} is not a member of {}".format(interface_name, vlan_name)
        else:
            print "{} is not a member of {}".format(interface_name, vlan_name)
        raise click.Abort()
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
        _change_bgp_session_status_by_addr(ipaddress, 'down', verbose)

# 'neighbor' subcommand
@shutdown.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Shut down BGP session by neighbor IP address or hostname"""
    _change_bgp_session_status(ipaddr_or_hostname, 'down', verbose)

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
        _change_bgp_session_status(ipaddress, 'up', verbose)

# 'neighbor' subcommand
@startup.command()
@click.argument('ipaddr_or_hostname', metavar='<ipaddr_or_hostname>', required=True)
@click.option('-v', '--verbose', is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Start up BGP session by neighbor IP address or hostname"""
    _change_bgp_session_status(ipaddr_or_hostname, 'up', verbose)

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
    if get_interface_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            raise click.Abort()

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
    if get_interface_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            raise click.Abort()


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
    if get_interface_mode() == "alias":
        interface_name = interface_alias_to_name(interface_name)
        if interface_name is None:
            raise click.Abort()

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


#
# 'pfc' group
#

@interface.group()
def pfc():
    """Set PFC configuration."""
    pass


#
# 'pfc asymmetric' command
#

@pfc.command()
@click.argument('status', type=click.Choice(['on', 'off']))
@click.argument('interface', type=click.STRING)
def asymmetric(status, interface):
    """Set asymmetric PFC configuration."""
    run_command("pfc config asymmetric {0} {1}".format(status, interface))


#
# 'platform' group
#
@cli.group()
def platform():
    """Platform-related configuration tasks"""
platform.add_command(mlnx.mlnx)


#
# 'interface_mode' group
#

@cli.group()
def interface_naming_mode():
    """Modify interface naming mode for interacting with SONiC CLI"""
    pass


@interface_naming_mode.command('default')
def interface_mode_default():
    """Set CLI interface naming mode to DEFAULT (SONiC port name)"""
    alias_mode = "default"
    set_interface_mode(alias_mode)


@interface_naming_mode.command('alias')
def interface_mode_alias():
    """Set CLI interface naming mode to ALIAS (Vendor port alias)"""
    alias_mode = "alias"
    set_interface_mode(alias_mode)


if __name__ == '__main__':
    cli()
