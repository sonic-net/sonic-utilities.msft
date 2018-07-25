#! /usr/bin/python -u

import click
import swsssdk
from tabulate import tabulate

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

@cli.command()
def show():
    """ Show the counter configuration """
    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()
    queue_info = configdb.get_entry('FLEX_COUNTER_TABLE', 'QUEUE')
    port_info = configdb.get_entry('FLEX_COUNTER_TABLE', 'PORT')
    
    header = ("Type", "Interval (in ms)", "Status")
    data = []
    if queue_info:
        data.append(["QUEUE_STAT", queue_info["POLL_INTERVAL"] if 'POLL_INTERVAL' in queue_info else 'default (10000)', queue_info["FLEX_COUNTER_STATUS"] if 'FLEX_COUNTER_STATUS' in queue_info else 'disable' ])
    if port_info:
        data.append(["PORT_STAT", port_info["POLL_INTERVAL"] if 'POLL_INTERVAL' in port_info else 'default (1000)', port_info["FLEX_COUNTER_STATUS"] if 'FLEX_COUNTER_STATUS' in port_info else 'disable'])

    print tabulate(data, headers=header, tablefmt="simple", missingval="")

