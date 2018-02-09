#! /usr/bin/python -u

import click
import swsssdk
from tabulate import tabulate
from natsort import natsorted

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

STATS_HEADER = ('QUEUE',) + zip(*STATS_DESCRIPTION)[0]
CONFIG_HEADER = ('PORT',) + zip(*CONFIG_DESCRIPTION)[0]

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
            table.append([queue] + stats_list)

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
        config_entry = configdb.get_entry('PFC_WD_TABLE', port)
        if config_entry is None or config_entry == {}:
            continue
        for config in CONFIG_DESCRIPTION:
            line = config_entry.get(config[1], config[2])
            config_list.append(line)
        table.append([port] + config_list)
    poll_interval = configdb.get_entry( 'PFC_WD_TABLE', 'GLOBAL').get('POLL_INTERVAL')
    if poll_interval is not None:
        click.echo("Changed polling interval to " + poll_interval + "ms")
    click.echo(tabulate(table, CONFIG_HEADER, stralign='right', numalign='right', tablefmt='simple'))

# Start WD
@cli.command()
@click.option('--action', '-a', type=click.Choice(['drop', 'forward', 'alert']))
@click.option('--restoration-time', '-r', type=click.IntRange(100, 60000))
@click.argument('ports', nargs = -1)
@click.argument('detection-time', type=click.IntRange(100, 5000))
def start(action, restoration_time, ports, detection_time):
    """ Start PFC watchdog on port(s) """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    countersdb = swsssdk.SonicV2Connector(host='127.0.0.1')
    countersdb.connect(countersdb.COUNTERS_DB)

    all_ports = get_all_ports(countersdb)

    if len(ports) == 0:
        ports = all_ports

    pfcwd_info = {
        'detection_time': detection_time,
    }
    if action is not None:
        pfcwd_info['action'] = action
    if restoration_time is not None:
        pfcwd_info['restoration_time'] = restoration_time

    for port in ports:
        if port not in all_ports:
            continue
        configdb.mod_entry("PFC_WD_TABLE", port, None)
        configdb.mod_entry("PFC_WD_TABLE", port, pfcwd_info)

# Set WD poll interval
@cli.command()
@click.argument('poll_interval', type=click.IntRange(100, 3000))
def interval(poll_interval):
    """ Set PFC watchdog counter polling interval """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    pfcwd_info = {}
    if poll_interval is not None:
        pfcwd_info['POLL_INTERVAL'] = poll_interval

    configdb.mod_entry("PFC_WD_TABLE", "GLOBAL", pfcwd_info)

# Stop WD
@cli.command()
@click.argument('ports', nargs = -1)
def stop(ports):
    """ Stop PFC watchdog on port(s) """
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
        configdb.mod_entry("PFC_WD_TABLE", port, None)

if __name__ == '__main__':
    cli()
