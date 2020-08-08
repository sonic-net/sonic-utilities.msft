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

VERSION = '2.0'

SYSLOG_IDENTIFIER = "fanutil"
PLATFORM_SPECIFIC_MODULE_NAME = "fanutil"
PLATFORM_SPECIFIC_CLASS_NAME = "FanUtil"

# Global platform-specific fanutil class instance
platform_fanutil = None
platform_chassis = None


def _wrapper_get_num_fans():
    if platform_chassis is not None:
        try:
            return platform_chassis.get_num_fans()
        except NotImplementedError:
            pass
    return platform_fanutil.get_num_fans()

def _wrapper_get_fan_name(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_fan(idx-1).get_name()
        except NotImplementedError:
            pass
    return "FAN {}".format(idx)

def _wrapper_get_fan_presence(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_fan(idx-1).get_presence()
        except NotImplementedError:
            pass
    return platform_fanutil.get_presence(idx)

def _wrapper_get_fan_status(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_fan(idx-1).get_status()
        except NotImplementedError:
            pass
    return platform_fanutil.get_status(idx)

def _wrapper_get_fan_direction(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_fan(idx-1).get_direction()
        except NotImplementedError:
            pass
    return platform_fanutil.get_direction(idx)

def _wrapper_get_fan_speed(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_fan(idx-1).get_speed_rpm()
        except NotImplementedError:
            pass
    return platform_fanutil.get_speed(idx)

def _wrapper_get_fan_speed_rear(idx):
    if platform_chassis is not None:
        # This wrapper API is invalid for Pl API 2.0 as every fan 
        # is treated as a separate fan
        return 0
    return platform_fanutil.get_speed_rear(idx)

def _wrapper_set_fan_speed(idx, percent):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_fan(idx-1).set_speed(percent)
        except NotImplementedError:
            pass
    return platform_fanutil.set_speed(percent)

def _wrapper_dump_sysfs(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_fan(idx).dump_sysfs()
        except NotImplementedError:
            pass
    return platform_fanutil.dump_sysfs()


# This is our main entrypoint - the main 'fanutil' command
@click.group()
def cli():
    """pddf_fanutil - Command line utility for providing FAN information"""

    global platform_fanutil
    global platform_chassis

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load the helper class
    helper = UtilHelper()

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(1)

    # Load new platform api class
    try:
        import sonic_platform.platform
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
    except Exception as e:
        click.echo("Failed to load chassis due to {}".format(str(e)))


    # Load platform-specific fanutil class if new platform object class is not found
    if platform_chassis is None:
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
    click.echo(_wrapper_get_num_fans())

# 'status' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of FAN")
def status(index):
    """Display FAN status"""
    supported_fan = range(1, _wrapper_get_num_fans()+1)
    fan_ids = []
    if (index < 0):
        fan_ids = supported_fan
    else:
        fan_ids = [index]

    header = ['FAN', 'Status']
    status_table = []

    for fan in fan_ids:
        msg = ""
        fan_name = _wrapper_get_fan_name(fan)
        if fan not in supported_fan:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported FAN - {}.".format(fan_name, len(supported_fan)))
            continue
        presence = _wrapper_get_fan_presence(fan)
        if presence:
            oper_status = _wrapper_get_fan_status(fan)
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
    supported_fan = range(1, _wrapper_get_num_fans() + 1)
    fan_ids = []
    if (index < 0):
        fan_ids = supported_fan
    else:
        fan_ids = [index]

    header = ['FAN', 'Direction']
    status_table = []

    for fan in fan_ids:
        fan_name = _wrapper_get_fan_name(fan)
        if fan not in supported_fan:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported FAN - {}.".format(fan_name, len(supported_fan)))
            continue
        direction = _wrapper_get_fan_direction(fan)
        status_table.append([fan_name, direction.capitalize()])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt="simple"))

# 'speed' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of FAN")
def getspeed(index):
    """Display FAN speed in RPM"""
    supported_fan = range(1, _wrapper_get_num_fans() + 1)
    fan_ids = []
    if (index < 0):
        fan_ids = supported_fan
    else:
        fan_ids = [index]

    if platform_chassis is not None:
        header = ['FAN', 'SPEED (RPM)']
    else:
        header = ['FAN', 'Front Fan RPM', 'Rear Fan RPM']
    
    status_table = []

    for fan in fan_ids:
        fan_name = _wrapper_get_fan_name(fan)
        if fan not in supported_fan:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported FAN - {}.".format(fan_name, len(supported_fan)))
            continue
        front = _wrapper_get_fan_speed(fan)
        rear = _wrapper_get_fan_speed_rear(fan)

        if platform_chassis is not None:
            status_table.append([fan_name, front])
        else:
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

    for fan in range(_wrapper_get_num_fans()):
        status = _wrapper_set_fan_speed(fan, speed)
        if not status:
            click.echo("Failed")
            sys.exit(1)

    click.echo("Successful")

@cli.group()
def debug():
    """pddf_fanutil debug commands"""
    pass

@debug.command()
def dump_sysfs():
    """Dump all Fan related SysFS paths"""
    for fan in range(_wrapper_get_num_fans()):
        status = _wrapper_dump_sysfs(fan)

    if status:
        for i in status:
            click.echo(i)



if __name__ == '__main__':
    cli()
