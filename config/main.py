#!/usr/sbin/env python

import sys
import os
import click
import json
import subprocess
import netaddr
import re
import syslog

import sonic_device_util
import ipaddress
from swsssdk import ConfigDBConnector
from swsssdk import SonicV2Connector
from minigraph import parse_device_desc_xml

import aaa
import mlnx

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

SONIC_CFGGEN_PATH = '/usr/local/bin/sonic-cfggen'
SYSLOG_IDENTIFIER = "config"
VLAN_SUB_INTERFACE_SEPARATOR = '.'

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
    ]
    if asic_type == 'mellanox' and 'pmon' in services_to_stop:
        services_to_stop.remove('pmon')

    for service in services_to_stop:
        try:
            click.echo("Stopping service {} ...".format(service))
            run_command("systemctl stop {}".format(service))

        except SystemExit as e:
            log_error("Stopping {} failed with error {}".format(service, e))
            raise

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
        'teamd'
    ]

    for service in services_to_reset:
        try:
            click.echo("Resetting failed status for service {} ...".format(service))
            run_command("systemctl reset-failed {}".format(service))
        except SystemExit as e:
            log_error("Failed to reset failed status for service {}".format(service))
            raise

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
    ]
    if asic_type == 'mellanox' and 'pmon' in services_to_restart:
        services_to_restart.remove('pmon')

    for service in services_to_restart:
        try:
            click.echo("Restarting service {} ...".format(service))
            run_command("systemctl restart {}".format(service))
        except SystemExit as e:
            log_error("Restart {} failed with error {}".format(service, e))
            raise

def is_ipaddress(val):
    """ Validate if an entry is a valid IP """
    if not val:
        return False
    try:
        netaddr.IPAddress(str(val))
    except:
        return False
    return True


# This is our main entrypoint - the main 'config' command
@click.group(context_settings=CONTEXT_SETTINGS)
def config():
    """SONiC command line - 'config' command"""
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
config.add_command(aaa.aaa)
config.add_command(aaa.tacacs)

@config.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Existing file will be overwritten, continue?')
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path())
def save(filename):
    """Export current config DB to a file on disk."""
    command = "{} -d --print-data > {}".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)

@config.command()
@click.option('-y', '--yes', is_flag=True)
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path(exists=True))
def load(filename, yes):
    """Import a previous saved config DB dump file."""
    if not yes:
        click.confirm('Load config from the file %s?' % filename, abort=True)
    command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)

@config.command()
@click.option('-y', '--yes', is_flag=True)
@click.option('-l', '--load-sysinfo', is_flag=True, help='load system default information (mac, portmap etc) first.')
@click.argument('filename', default='/etc/sonic/config_db.json', type=click.Path(exists=True))
def reload(filename, yes, load_sysinfo):
    """Clear current configuration and import a previous saved config DB dump file."""
    if not yes:
        click.confirm('Clear current config and reload config from the file %s?' % filename, abort=True)

    log_info("'reload' executing...")

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
    _stop_services()
    config_db = ConfigDBConnector()
    config_db.connect()
    client = config_db.redis_clients[config_db.CONFIG_DB]
    client.flushdb()
    if load_sysinfo:
        command = "{} -H -k {} --write-to-db".format(SONIC_CFGGEN_PATH, cfg_hwsku)
        run_command(command, display_cmd=True)

    command = "{} -j {} --write-to-db".format(SONIC_CFGGEN_PATH, filename)
    run_command(command, display_cmd=True)
    client.set(config_db.INIT_INDICATOR, 1)

    # Migrate DB contents to latest version
    db_migrator='/usr/bin/db_migrator.py'
    if os.path.isfile(db_migrator) and os.access(db_migrator, os.X_OK):
        run_command(db_migrator + ' -o migrate')

    # We first run "systemctl reset-failed" to remove the "failed"
    # status from all services before we attempt to restart them
    _reset_failed_services()
    _restart_services()

@config.command()
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
    click.echo("Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.")

@config.command()
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false,
                expose_value=False, prompt='Reload config from minigraph?')
def load_minigraph():
    """Reconfigure based on minigraph."""
    log_info("'load_minigraph' executing...")

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

    # Write latest db version string into db
    db_migrator='/usr/bin/db_migrator.py'
    if os.path.isfile(db_migrator) and os.access(db_migrator, os.X_OK):
        run_command(db_migrator + ' -o set_version')

    # We first run "systemctl reset-failed" to remove the "failed"
    # status from all services before we attempt to restart them
    _reset_failed_services()
    #FIXME: After config DB daemon is implemented, we'll no longer need to restart every service.
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
@config.group()
@click.pass_context
def portchannel(ctx):
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}
    pass

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

@portchannel.group('member')
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
@config.group()
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
# 'qos' group ('config qos ...')
#
@config.group()
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
@config.group()
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
    pass

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

#
# 'vlan' group ('config vlan ...')
#
@config.group()
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
        ctx.fail("{} already exists".format(vlan))
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


#
# 'member' group ('config vlan member ...')
#
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

def vrf_add_management_vrf():
    """Enable management vrf in config DB"""

    config_db = ConfigDBConnector()
    config_db.connect()
    entry = config_db.get_entry('MGMT_VRF_CONFIG', "vrf_global")
    if entry and entry['mgmtVrfEnabled'] == 'true' :
        click.echo("ManagementVRF is already Enabled.")
        return None
    config_db.mod_entry('MGMT_VRF_CONFIG',"vrf_global",{"mgmtVrfEnabled": "true"})
    mvrf_restart_services()

def vrf_delete_management_vrf():
    """Disable management vrf in config DB"""

    config_db = ConfigDBConnector()
    config_db.connect()
    entry = config_db.get_entry('MGMT_VRF_CONFIG', "vrf_global")
    if not entry or entry['mgmtVrfEnabled'] == 'false' :
        click.echo("ManagementVRF is already Disabled.")
        return None
    config_db.mod_entry('MGMT_VRF_CONFIG',"vrf_global",{"mgmtVrfEnabled": "false"})
    mvrf_restart_services()

#
# 'vrf' group ('config vrf ...')
#

@config.group('vrf')
def vrf():
    """VRF-related configuration tasks"""
    pass

@vrf.command('add')
@click.argument('vrfname', metavar='<vrfname>. Type mgmt for management VRF', required=True)
@click.pass_context
def vrf_add (ctx, vrfname):
    """Create management VRF and move eth0 into it"""
    if vrfname == 'mgmt' or vrfname == 'management':
        vrf_add_management_vrf()
    else:
        click.echo("Creation of data vrf={} is not yet supported".format(vrfname))

@vrf.command('del')
@click.argument('vrfname', metavar='<vrfname>. Type mgmt for management VRF', required=False)
@click.pass_context
def vrf_del (ctx, vrfname):
    """Delete management VRF and move back eth0 to default VRF"""
    if vrfname == 'mgmt' or vrfname == 'management':
        vrf_delete_management_vrf()
    else:
        click.echo("Deletion of data vrf={} is not yet supported".format(vrfname))

@config.group()
@click.pass_context
def snmpagentaddress(ctx):
    """SNMP agent listening IP address, port, vrf configuration"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}
    pass

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

@config.group()
@click.pass_context
def snmptrap(ctx):
    """SNMP Trap server configuration to send traps"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}
    pass

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

@vlan.group('dhcp_relay')
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
        db.set_entry('VLAN', vlan_name, {"dhcp_servers":dhcp_relay_dests})
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
        db.set_entry('VLAN', vlan_name, {"dhcp_servers":dhcp_relay_dests})
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

@config.group()
def bgp():
    """BGP-related configuration tasks"""
    pass

#
# 'shutdown' subgroup ('config bgp shutdown ...')
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
# 'remove' subgroup ('config bgp remove ...')
#

@bgp.group()
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

@config.group()
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
# 'ip' subgroup ('config interface ip ...')
#

@interface.group()
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
        if interface_name.startswith("Ethernet"):
            if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
                config_db.set_entry("VLAN_SUB_INTERFACE", interface_name, {"admin_status": "up"})
                config_db.set_entry("VLAN_SUB_INTERFACE", (interface_name, ip_addr), {"NULL": "NULL"})
            else:
                config_db.set_entry("INTERFACE", (interface_name, ip_addr), {"NULL": "NULL"})
                config_db.set_entry("INTERFACE", interface_name, {"NULL": "NULL"})
        elif interface_name == 'eth0':

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

        elif interface_name.startswith("PortChannel"):
            if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
                config_db.set_entry("VLAN_SUB_INTERFACE", interface_name, {"admin_status": "up"})
                config_db.set_entry("VLAN_SUB_INTERFACE", (interface_name, ip_addr), {"NULL": "NULL"})
            else:
                config_db.set_entry("PORTCHANNEL_INTERFACE", (interface_name, ip_addr), {"NULL": "NULL"})
                config_db.set_entry("PORTCHANNEL_INTERFACE", interface_name, {"NULL": "NULL"})
        elif interface_name.startswith("Vlan"):
            config_db.set_entry("VLAN_INTERFACE", (interface_name, ip_addr), {"NULL": "NULL"})
            config_db.set_entry("VLAN_INTERFACE", interface_name, {"NULL": "NULL"})
        elif interface_name.startswith("Loopback"):
            config_db.set_entry("LOOPBACK_INTERFACE", (interface_name, ip_addr), {"NULL": "NULL"})
        else:
            ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")
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

    if_table = ""
    try:
        ipaddress.ip_network(unicode(ip_addr), strict=False)
        if interface_name.startswith("Ethernet"):
            if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
                config_db.set_entry("VLAN_SUB_INTERFACE", (interface_name, ip_addr), None)
                if_table = "VLAN_SUB_INTERFACE"
            else:
                config_db.set_entry("INTERFACE", (interface_name, ip_addr), None)
                if_table = "INTERFACE"
        elif interface_name == 'eth0':
            config_db.set_entry("MGMT_INTERFACE", (interface_name, ip_addr), None)
            mgmt_ip_restart_services()
        elif interface_name.startswith("PortChannel"):
            if VLAN_SUB_INTERFACE_SEPARATOR in interface_name:
                config_db.set_entry("VLAN_SUB_INTERFACE", (interface_name, ip_addr), None)
                if_table = "VLAN_SUB_INTERFACE"
            else:
                config_db.set_entry("PORTCHANNEL_INTERFACE", (interface_name, ip_addr), None)
                if_table = "PORTCHANNEL_INTERFACE"
        elif interface_name.startswith("Vlan"):
            config_db.set_entry("VLAN_INTERFACE", (interface_name, ip_addr), None)
            if_table = "VLAN_INTERFACE"
        elif interface_name.startswith("Loopback"):
            config_db.set_entry("LOOPBACK_INTERFACE", (interface_name, ip_addr), None)
        else:
            ctx.fail("'interface_name' is not valid. Valid names [Ethernet/PortChannel/Vlan/Loopback]")

        command = "ip neigh flush {}".format(ip_addr)
        run_command(command)
    except ValueError:
        ctx.fail("'ip_addr' is not valid.")

    exists = False
    if if_table:
        interfaces = config_db.get_table(if_table)
        for key in interfaces.keys():
            if not isinstance(key, tuple):
                continue
            if interface_name in key:
                exists = True
                break

    if not exists:
        config_db.set_entry(if_table, interface_name, None)

#
# 'acl' group ('config acl ...')
#

@config.group()
def acl():
    """ACL-related configuration tasks"""
    pass

#
# 'add' subgroup ('config acl add ...')
#

@acl.group()
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

@acl.group()
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
# 'pfc' group ('config pfc ...')
#

@interface.group()
@click.pass_context
def pfc(ctx):
    """Set PFC configuration."""
    pass


#
# 'pfc asymmetric' command
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
# 'platform' group ('config platform ...')
#

@config.group()
def platform():
    """Platform-related configuration tasks"""

if asic_type == 'mellanox':
    platform.add_command(mlnx.mlnx)

#
# 'watermark' group ("show watermark telemetry interval")
#

@config.group()
def watermark():
    """Configure watermark """
    pass

@watermark.group()
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

@config.group('interface_naming_mode')
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

#
# 'syslog' group ('config syslog ...')
#
@config.group('syslog')
@click.pass_context
def syslog_group(ctx):
    """Syslog server configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}
    pass

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
@config.group()
@click.pass_context
def ntp(ctx):
    """NTP server configuration tasks"""
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}
    pass

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

if __name__ == '__main__':
    config()
