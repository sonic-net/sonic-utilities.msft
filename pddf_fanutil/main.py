#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with FAN Controller in PDDF mode in SONiC
#

try:
    import sys
    import os
    import click
    from tabulate import tabulate
    from utilities_common.util_base import UtilHelper
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SYSLOG_IDENTIFIER = "fanutil"
PLATFORM_SPECIFIC_MODULE_NAME = "fanutil"
PLATFORM_SPECIFIC_CLASS_NAME = "FanUtil"

# Global platform-specific fanutil class instance
platform_fanutil = None

#logger = UtilLogger(SYSLOG_IDENTIFIER)

# This is our main entrypoint - the main 'fanutil' command
@click.group()
def cli():
    """pddf_fanutil - Command line utility for providing FAN information"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load the helper class
    helper = UtilHelper()

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(1)

    # Load platform-specific fanutil class
    global platform_fanutil
    try:
        platform_fanutil = helper.load_platform_util(PLATFORM_SPECIFIC_MODULE_NAME, PLATFORM_SPECIFIC_CLASS_NAME)
    except Exception as e:
        click.echo("Failed to load {}: {}".format(PLATFORM_SPECIFIC_MODULE_NAME, str(e)))
        sys.exit(2)

# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("PDDF fanutil version {0}".format(VERSION))

# 'numfans' subcommand
@cli.command()
def numfans():
    """Display number of FANs installed on device"""
    click.echo(str(platform_fanutil.get_num_fans()))

# 'status' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of FAN")
def status(index):
    """Display FAN status"""
    supported_fan = range(1, platform_fanutil.get_num_fans() + 1)
    fan_ids = []
    if (index < 0):
        fan_ids = supported_fan
    else:
        fan_ids = [index]

    header = ['FAN', 'Status']
    status_table = []

    for fan in fan_ids:
        msg = ""
        fan_name = "FAN {}".format(fan)
        if fan not in supported_fan:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported FAN - {}.".format(fan_name, platform_fanutil.get_num_fans()))
            continue
        presence = platform_fanutil.get_presence(fan)
        if presence:
            oper_status = platform_fanutil.get_status(fan)
            msg = 'OK' if oper_status else "NOT OK"
        else:
            msg = 'NOT PRESENT'
        status_table.append([fan_name, msg])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt="simple"))

# 'direction' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of FAN")
def direction(index):
    """Display FAN airflow direction"""
    supported_fan = range(1, platform_fanutil.get_num_fans() + 1)
    fan_ids = []
    if (index < 0):
        fan_ids = supported_fan
    else:
        fan_ids = [index]

    header = ['FAN', 'Direction']
    status_table = []

    for fan in fan_ids:
        fan_name = "FAN {}".format(fan)
        if fan not in supported_fan:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported FAN - {}.".format(fan_name, platform_fanutil.get_num_fans()))
            continue
        direction = platform_fanutil.get_direction(fan)
        status_table.append([fan_name, direction])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt="simple"))

# 'speed' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of FAN")
def getspeed(index):
    """Display FAN speed in RPM"""
    supported_fan = range(1, platform_fanutil.get_num_fans() + 1)
    fan_ids = []
    if (index < 0):
        fan_ids = supported_fan
    else:
        fan_ids = [index]

    header = ['FAN', 'Front Fan RPM', 'Rear Fan RPM']
    status_table = []

    for fan in fan_ids:
        fan_name = "FAN {}".format(fan)
        if fan not in supported_fan:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported FAN - {}.".format(fan_name, platform_fanutil.get_num_fans()))
            continue
        front = platform_fanutil.get_speed(fan)
        rear = platform_fanutil.get_speed_rear(fan)
        status_table.append([fan_name, front, rear])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt="simple"))

# 'setspeed' subcommand
@cli.command()
@click.argument('speed', type=int)
def setspeed(speed):
    """Set FAN speed in percentage"""
    if speed is None:
        click.echo("speed value is required")
        raise click.Abort()

    status = platform_fanutil.set_speed(speed)
    if status:
        click.echo("Successful")
    else:
        click.echo("Failed")

@cli.group()
def debug():
    """pddf_fanutil debug commands"""
    pass

@debug.command('dump-sysfs')
def dump_sysfs():
    """Dump all Fan related SysFS paths"""
    status = platform_fanutil.dump_sysfs()

    if status:
        for i in status:
            click.echo(i)



if __name__ == '__main__':
    cli()
