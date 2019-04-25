#! /usr/bin/python -u

import click
import swsssdk
import os
from tabulate import tabulate
from natsort import natsorted

# Default configuration
DEFAULT_DETECTION_TIME = 200
DEFAULT_RESTORATION_TIME = 200
DEFAULT_POLL_INTERVAL = 200
DEFAULT_PORT_NUM = 32
DEFAULT_ACTION = 'drop'

STATS_DESCRIPTION = [
    ('STORM DETECTED/RESTORED', 'PFC_WD_QUEUE_STATS_DEADLOCK_DETECTED', 'PFC_WD_QUEUE_STATS_DEADLOCK_RESTORED'),
    ('TX OK/DROP',              'PFC_WD_QUEUE_STATS_TX_PACKETS',        'PFC_WD_QUEUE_STATS_TX_DROPPED_PACKETS'),
    ('RX OK/DROP',              'PFC_WD_QUEUE_STATS_RX_PACKETS',        'PFC_WD_QUEUE_STATS_RX_DROPPED_PACKETS'),
    ('TX LAST OK/DROP',         'PFC_WD_QUEUE_STATS_TX_PACKETS_LAST',   'PFC_WD_QUEUE_STATS_TX_DROPPED_PACKETS_LAST'),
    ('RX LAST OK/DROP',         'PFC_WD_QUEUE_STATS_RX_PACKETS_LAST',   'PFC_WD_QUEUE_STATS_RX_DROPPED_PACKETS_LAST'),
]

CONFIG_DESCRIPTION = [
    ('ACTION',           'action',           'drop'),
    ('DETECTION TIME',   'detection_time',   'N/A'),
    ('RESTORATION TIME', 'restoration_time', 'infinite')
]

STATS_HEADER = ('QUEUE', 'STATUS',) + zip(*STATS_DESCRIPTION)[0]
CONFIG_HEADER = ('PORT',) + zip(*CONFIG_DESCRIPTION)[0]

CONFIG_DB_PFC_WD_TABLE_NAME = 'PFC_WD'

# Main entrypoint
@click.group()
def cli():
    """ SONiC PFC Watchdog """

def get_all_queues(db):
    queue_names = db.get_all(db.COUNTERS_DB, 'COUNTERS_QUEUE_NAME_MAP')
    return natsorted(queue_names.keys())

def get_all_ports(db):
    port_names = db.get_all(db.COUNTERS_DB, 'COUNTERS_PORT_NAME_MAP')
    return natsorted(port_names.keys())

def get_server_facing_ports(db):
    candidates = db.get_table('DEVICE_NEIGHBOR')
    server_facing_ports = []
    for port in candidates.keys():
        neighbor = db.get_entry('DEVICE_NEIGHBOR_METADATA', candidates[port]['name'])
        if neighbor and neighbor['type'].lower() == 'server':
            server_facing_ports.append(port)
    if not server_facing_ports:
        server_facing_ports = [p[1] for p in db.get_table('VLAN_MEMBER').keys()]
    return server_facing_ports

# Show commands
@cli.group()
def show():
    """ Show PFC Watchdog information"""

# Show stats
@show.command()
@click.option('-e', '--empty', is_flag = True)
@click.argument('queues', nargs = -1)
def stats(empty, queues):
    """ Show PFC Watchdog stats per queue """
    db = swsssdk.SonicV2Connector(host='127.0.0.1')
    db.connect(db.COUNTERS_DB)
    table = []

    if len(queues) == 0:
        queues = get_all_queues(db)

    for queue in queues:
        stats_list = []
        queue_oid = db.get(db.COUNTERS_DB, 'COUNTERS_QUEUE_NAME_MAP', queue)
        stats = db.get_all(db.COUNTERS_DB, 'COUNTERS:' + queue_oid)
        if stats is None:
            continue
        for stat in STATS_DESCRIPTION:
            line = stats.get(stat[1], '0') + '/' + stats.get(stat[2], '0')
            stats_list.append(line)
        if stats_list != ['0/0'] * len(STATS_DESCRIPTION) or empty:
            table.append([queue, stats['PFC_WD_STATUS']] + stats_list)

    click.echo(tabulate(table, STATS_HEADER, stralign='right', numalign='right', tablefmt='simple'))

# Show stats
@show.command()
@click.argument('ports', nargs = -1)
def config(ports):
    """ Show PFC Watchdog configuration """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    countersdb = swsssdk.SonicV2Connector(host='127.0.0.1')
    countersdb.connect(countersdb.COUNTERS_DB)
    table = []

    all_ports = get_all_ports(countersdb)

    if len(ports) == 0:
        ports = all_ports

    for port in ports:
        config_list = []
        config_entry = configdb.get_entry(CONFIG_DB_PFC_WD_TABLE_NAME, port)
        if config_entry is None or config_entry == {}:
            continue
        for config in CONFIG_DESCRIPTION:
            line = config_entry.get(config[1], config[2])
            config_list.append(line)
        table.append([port] + config_list)
    poll_interval = configdb.get_entry( CONFIG_DB_PFC_WD_TABLE_NAME, 'GLOBAL').get('POLL_INTERVAL')
    if poll_interval is not None:
        click.echo("Changed polling interval to " + poll_interval + "ms")

    big_red_switch = configdb.get_entry( CONFIG_DB_PFC_WD_TABLE_NAME, 'GLOBAL').get('BIG_RED_SWITCH')
    if big_red_switch is not None:
        click.echo("BIG_RED_SWITCH status is " + big_red_switch)

    click.echo(tabulate(table, CONFIG_HEADER, stralign='right', numalign='right', tablefmt='simple'))

# Start WD
@cli.command()
@click.option('--action', '-a', type=click.Choice(['drop', 'forward', 'alert']))
@click.option('--restoration-time', '-r', type=click.IntRange(100, 60000))
@click.argument('ports', nargs=-1)
@click.argument('detection-time', type=click.IntRange(100, 5000))
def start(action, restoration_time, ports, detection_time):
    """
    Start PFC watchdog on port(s). To config all ports, use all as input.

    Example:

    sudo pfcwd start --action drop ports all detection-time 400 --restoration-time 400

    """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
    allowed_strs = ['ports', 'all', 'detection-time']
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    countersdb = swsssdk.SonicV2Connector(host='127.0.0.1')
    countersdb.connect(countersdb.COUNTERS_DB)

    all_ports = get_all_ports(countersdb)
    allowed_strs = allowed_strs + all_ports
    for p in ports:
        if p not in allowed_strs:
            raise click.BadOptionUsage("Bad command line format. Try 'pfcwd start --help' for usage")

    if len(ports) == 0:
        ports = all_ports

    pfcwd_info = {
        'detection_time': detection_time,
    }
    if action is not None:
        pfcwd_info['action'] = action
    if restoration_time is not None:
        pfcwd_info['restoration_time'] = restoration_time
    else:
        pfcwd_info['restoration_time'] = 2 * detection_time
        print "restoration time not defined; default to 2 times detection time: %d ms" % (2 * detection_time)

    for port in ports:
        if port == "all":
            for p in all_ports:
                configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, p, None)
                configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, p, pfcwd_info)
        else:
            if port not in all_ports:
                continue
            configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, port, None)
            configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, port, pfcwd_info)

# Set WD poll interval
@cli.command()
@click.argument('poll_interval', type=click.IntRange(100, 3000))
def interval(poll_interval):
    """ Set PFC watchdog counter polling interval """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    pfcwd_info = {}
    if poll_interval is not None:
        pfcwd_info['POLL_INTERVAL'] = poll_interval

    configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL", pfcwd_info)

# Stop WD
@cli.command()
@click.argument('ports', nargs = -1)
def stop(ports):
    """ Stop PFC watchdog on port(s) """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    countersdb = swsssdk.SonicV2Connector(host='127.0.0.1')
    countersdb.connect(countersdb.COUNTERS_DB)

    all_ports = get_all_ports(countersdb)

    if len(ports) == 0:
        ports = all_ports

    for port in ports:
        if port not in all_ports:
            continue
        configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, port, None)

# Set WD default configuration on server facing ports when enable flag is on
@cli.command()
def start_default():
    """ Start PFC WD by default configurations  """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    enable = configdb.get_entry('DEVICE_METADATA', 'localhost').get('default_pfcwd_status')

    # Get active ports from Config DB
    active_ports = natsorted(configdb.get_table('DEVICE_NEIGHBOR').keys())

    if not enable or enable.lower() != "enable":
       return

    port_num = len(configdb.get_table('PORT').keys())

    # Paramter values positively correlate to the number of ports.
    multiply = max(1, (port_num-1)/DEFAULT_PORT_NUM+1)
    pfcwd_info = {
        'detection_time': DEFAULT_DETECTION_TIME * multiply,
        'restoration_time': DEFAULT_RESTORATION_TIME * multiply,
        'action': DEFAULT_ACTION
    }

    for port in active_ports:
        configdb.set_entry(CONFIG_DB_PFC_WD_TABLE_NAME, port, pfcwd_info)

    pfcwd_info = {}
    pfcwd_info['POLL_INTERVAL'] = DEFAULT_POLL_INTERVAL * multiply
    configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL", pfcwd_info)

# Enable/disable PFC WD counter polling
@cli.command()
@click.argument('counter_poll', type=click.Choice(['enable', 'disable']))
def counter_poll(counter_poll):
    """ Enable/disable counter polling """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    pfcwd_info = {}
    pfcwd_info['FLEX_COUNTER_STATUS'] = counter_poll
    configdb.mod_entry("FLEX_COUNTER_TABLE", "PFCWD", pfcwd_info)

# Enable/disable PFC WD BIG_RED_SWITCH mode
@cli.command()
@click.argument('big_red_switch', type=click.Choice(['enable', 'disable']))
def big_red_switch(big_red_switch):
    """ Enable/disable BIG_RED_SWITCH mode """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    pfcwd_info = {}
    if big_red_switch is not None:
        pfcwd_info['BIG_RED_SWITCH'] = big_red_switch

    configdb.mod_entry(CONFIG_DB_PFC_WD_TABLE_NAME, "GLOBAL", pfcwd_info)

if __name__ == '__main__':
    cli()
