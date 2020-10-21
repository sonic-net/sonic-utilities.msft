#! /usr/bin/python -u

import click
import json
import swsssdk
from tabulate import tabulate

BUFFER_POOL_WATERMARK = "BUFFER_POOL_WATERMARK"
PORT_BUFFER_DROP = "PORT_BUFFER_DROP"
DISABLE = "disable"
ENABLE = "enable"
DEFLT_60_SEC= "default (60000)"
DEFLT_10_SEC= "default (10000)"
DEFLT_1_SEC = "default (1000)"

@click.group()
def cli():
    """ SONiC Static Counter Poll configurations """

# Queue counter commands
@cli.group()
def queue():
    """ Queue counter commands """

@queue.command()
@click.argument('poll_interval', type=click.IntRange(100, 30000))
def interval(poll_interval):
    """ Set queue counter query interval """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    queue_info = {}
    if poll_interval is not None:
        queue_info['POLL_INTERVAL'] = poll_interval
    configdb.mod_entry("FLEX_COUNTER_TABLE", "QUEUE", queue_info)

@queue.command()
def enable():
    """ Enable queue counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    queue_info = {}
    queue_info['FLEX_COUNTER_STATUS'] = 'enable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "QUEUE", queue_info)

@queue.command()
def disable():
    """ Disable queue counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    queue_info = {}
    queue_info['FLEX_COUNTER_STATUS'] = 'disable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "QUEUE", queue_info)

# Port counter commands
@cli.group()
def port():
    """ Queue counter commands """

@port.command()
@click.argument('poll_interval', type=click.IntRange(100, 30000))
def interval(poll_interval):
    """ Set queue counter query interval """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    port_info = {}
    if poll_interval is not None:
        port_info['POLL_INTERVAL'] = poll_interval
    configdb.mod_entry("FLEX_COUNTER_TABLE", "PORT", port_info)

@port.command()
def enable():
    """ Enable port counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    port_info = {}
    port_info['FLEX_COUNTER_STATUS'] = 'enable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "PORT", port_info)

@port.command()
def disable():
    """ Disable port counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    port_info = {}
    port_info['FLEX_COUNTER_STATUS'] = 'disable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "PORT", port_info)

# Port buffer drop counter commands
@cli.group()
def port_buffer_drop():
    """ Port buffer drop  counter commands """

@port_buffer_drop.command()
@click.argument('poll_interval', type=click.IntRange(30000, 300000))
def interval(poll_interval):
    """
    Set port_buffer_drop counter query interval
    This counter group causes high CPU usage when polled,
    hence the allowed interval is between 30s and 300s.
    This is a short term solution and
    should be changed once the performance is enhanced
    """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    port_info = {}
    if poll_interval:
        port_info['POLL_INTERVAL'] = poll_interval
    configdb.mod_entry("FLEX_COUNTER_TABLE", PORT_BUFFER_DROP, port_info)

@port_buffer_drop.command()
def enable():
    """ Enable port counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    port_info = {}
    port_info['FLEX_COUNTER_STATUS'] = ENABLE
    configdb.mod_entry("FLEX_COUNTER_TABLE", PORT_BUFFER_DROP, port_info)

@port_buffer_drop.command()
def disable():
    """ Disable port counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    port_info = {}
    port_info['FLEX_COUNTER_STATUS'] = DISABLE
    configdb.mod_entry("FLEX_COUNTER_TABLE", PORT_BUFFER_DROP, port_info)

# RIF counter commands
@cli.group()
def rif():
    """ RIF counter commands """

@rif.command()
@click.argument('poll_interval')
def interval(poll_interval):
    """ Set rif counter query interval """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    rif_info = {}
    if poll_interval is not None:
        rif_info['POLL_INTERVAL'] = poll_interval
    configdb.mod_entry("FLEX_COUNTER_TABLE", "RIF", rif_info)

@rif.command()
def enable():
    """ Enable rif counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    rif_info = {}
    rif_info['FLEX_COUNTER_STATUS'] = 'enable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "RIF", rif_info)

@rif.command()
def disable():
    """ Disable rif counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    rif_info = {}
    rif_info['FLEX_COUNTER_STATUS'] = 'disable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "RIF", rif_info)

# Watermark counter commands
@cli.group()
def watermark():
    """ Watermark counter commands """

@watermark.command()
@click.argument('poll_interval', type=click.IntRange(1000, 30000))
def interval(poll_interval):
    """ Set watermark counter query interval for both queue and PG watermarks """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    queue_wm_info = {}
    pg_wm_info = {}
    buffer_pool_wm_info = {}
    if poll_interval is not None:
        queue_wm_info['POLL_INTERVAL'] = poll_interval
        pg_wm_info['POLL_INTERVAL'] = poll_interval
        buffer_pool_wm_info['POLL_INTERVAL'] = poll_interval
    configdb.mod_entry("FLEX_COUNTER_TABLE", "QUEUE_WATERMARK", queue_wm_info)
    configdb.mod_entry("FLEX_COUNTER_TABLE", "PG_WATERMARK", pg_wm_info)
    configdb.mod_entry("FLEX_COUNTER_TABLE", BUFFER_POOL_WATERMARK, buffer_pool_wm_info)

@watermark.command()
def enable():
    """ Enable watermark counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    fc_info = {}
    fc_info['FLEX_COUNTER_STATUS'] = 'enable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "QUEUE_WATERMARK", fc_info)
    configdb.mod_entry("FLEX_COUNTER_TABLE", "PG_WATERMARK", fc_info)
    configdb.mod_entry("FLEX_COUNTER_TABLE", BUFFER_POOL_WATERMARK, fc_info)

@watermark.command()
def disable():
    """ Disable watermark counter query """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    fc_info = {}
    fc_info['FLEX_COUNTER_STATUS'] = 'disable'
    configdb.mod_entry("FLEX_COUNTER_TABLE", "QUEUE_WATERMARK", fc_info)
    configdb.mod_entry("FLEX_COUNTER_TABLE", "PG_WATERMARK", fc_info)
    configdb.mod_entry("FLEX_COUNTER_TABLE", BUFFER_POOL_WATERMARK, fc_info)

@cli.command()
def show():
    """ Show the counter configuration """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    queue_info = configdb.get_entry('FLEX_COUNTER_TABLE', 'QUEUE')
    port_info = configdb.get_entry('FLEX_COUNTER_TABLE', 'PORT')
    port_drop_info = configdb.get_entry('FLEX_COUNTER_TABLE', PORT_BUFFER_DROP)
    rif_info = configdb.get_entry('FLEX_COUNTER_TABLE', 'RIF')
    queue_wm_info = configdb.get_entry('FLEX_COUNTER_TABLE', 'QUEUE_WATERMARK')
    pg_wm_info = configdb.get_entry('FLEX_COUNTER_TABLE', 'PG_WATERMARK')
    buffer_pool_wm_info = configdb.get_entry('FLEX_COUNTER_TABLE', BUFFER_POOL_WATERMARK)
    
    header = ("Type", "Interval (in ms)", "Status")
    data = []
    if queue_info:
        data.append(["QUEUE_STAT", queue_info.get("POLL_INTERVAL", DEFLT_10_SEC), queue_info.get("FLEX_COUNTER_STATUS", DISABLE)])
    if port_info:
        data.append(["PORT_STAT", port_info.get("POLL_INTERVAL", DEFLT_1_SEC), port_info.get("FLEX_COUNTER_STATUS", DISABLE)])
    if port_drop_info:
        data.append([PORT_BUFFER_DROP, port_drop_info.get("POLL_INTERVAL", DEFLT_60_SEC), port_drop_info.get("FLEX_COUNTER_STATUS", DISABLE)])
    if rif_info:
        data.append(["RIF_STAT", rif_info.get("POLL_INTERVAL", DEFLT_1_SEC), rif_info.get("FLEX_COUNTER_STATUS", DISABLE)])
    if queue_wm_info:
        data.append(["QUEUE_WATERMARK_STAT", queue_wm_info.get("POLL_INTERVAL", DEFLT_10_SEC), queue_wm_info.get("FLEX_COUNTER_STATUS", DISABLE)])
    if pg_wm_info:
        data.append(["PG_WATERMARK_STAT", pg_wm_info.get("POLL_INTERVAL", DEFLT_10_SEC), pg_wm_info.get("FLEX_COUNTER_STATUS", DISABLE)])
    if buffer_pool_wm_info:
        data.append(["BUFFER_POOL_WATERMARK_STAT", buffer_pool_wm_info.get("POLL_INTERVAL", DEFLT_10_SEC), buffer_pool_wm_info.get("FLEX_COUNTER_STATUS", DISABLE)])

    click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))

def _update_config_db(status, filename):
    """ Update counter configuration in config_db file """
    with open(filename) as config_db_file:
        config_db = json.load(config_db_file)

    write_config_db = False
    if "FLEX_COUNTER_TABLE" in config_db:
        for counter, counter_config in config_db["FLEX_COUNTER_TABLE"].items():
            if "FLEX_COUNTER_STATUS" in counter_config and \
                counter_config["FLEX_COUNTER_STATUS"] is not status:
                counter_config["FLEX_COUNTER_STATUS"] = status
                write_config_db = True

    if write_config_db:
        with open(filename, 'w') as config_db_file:
            json.dump(config_db, config_db_file, indent=4)

# Working on Config DB
@cli.group()
def config_db():
    """ Config DB counter commands """

@config_db.command()
@click.argument("filename", default="/etc/sonic/config_db.json", type=click.Path(exists=True))
def enable(filename):
    """ Enable counter configuration in config_db file """
    _update_config_db("enable", filename)

@config_db.command()
@click.argument("filename", default="/etc/sonic/config_db.json", type=click.Path(exists=True))
def disable(filename):
    """ Disable counter configuration in config_db file """
    _update_config_db("disable", filename)

