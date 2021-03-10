#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with Thermal sensors in PDDF mode in SONiC
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

ERROR_PERMISSIONS = 1
ERROR_CHASSIS_LOAD = 2
ERROR_NOT_IMPLEMENTED = 3
ERROR_PDDF_NOT_SUPPORTED = 4

# Global platform-specific chassis class instance
platform_chassis = None

# Load the helper class
helper = UtilHelper()

# ==================== CLI commands and groups ====================

# This is our main entrypoint - the main 'thermalutil' command
@click.group()
def cli():
    """pddf_thermalutil - Command line utility for providing Temp Sensors information"""

    global platform_chassis

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(1)

    # Load platform-specific chassis 2.0 api class
    platform_chassis = helper.load_platform_chassis()
    if not platform_chassis:
        sys.exit(ERROR_CHASSIS_LOAD)


# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("PDDF thermalutil version {0}".format(VERSION))


# 'numthermals' subcommand
@cli.command()
def numthermals():
    """Display number of Thermal Sensors installed """
    num_thermals = platform_chassis.get_num_thermals()
    click.echo(num_thermals)


# 'gettemp' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="Index of Temp Sensor (1-based)")
def gettemp(index):
    """Display Temperature values of thermal sensors"""
    thermal_list = []
    if (index < 0):
        thermal_list = platform_chassis.get_all_thermals()
        default_index = 0
    else:
        thermal_list = platform_chassis.get_thermal(index-1)
        default_index = index-1

    header = []
    temp_table = []

    for idx, thermal in enumerate(thermal_list, default_index):
        thermal_name = helper.try_get(thermal.get_name, "TEMP{}".format(idx+1))
        # TODO: Provide a wrapper API implementation for the below function
        try:
            temp = thermal.get_temperature()
            if temp:
                value = "temp1\t %+.1f C (" % temp
            high = thermal.get_high_threshold()
            if high:
                value += "high = %+.1f C" % high
            crit = thermal.get_high_critical_threshold()
            if high and crit:
                value += ", "
            if crit:
                value += "crit = %+.1f C" % crit

            label = thermal.get_temp_label()
            value += ")"

        except NotImplementedError:
            pass

        if label is None:
            temp_table.append([thermal_name, value])
        else:
            temp_table.append([thermal_name, label, value])

    if temp_table:
        if label is None:
            header = ['Temp Sensor', 'Value']
        else:
            header = ['Temp Sensor', 'Label', 'Value']
        click.echo(tabulate(temp_table, header, tablefmt="simple"))


@cli.group()
def debug():
    """pddf_thermalutil debug commands"""
    pass


@debug.command()
def dump_sysfs():
    """Dump all Temp Sensor related SysFS paths"""
    thermal_list = platform_chassis.get_all_thermals()
    for idx, thermal in enumerate(thermal_list):
        status = thermal.dump_sysfs()

    if status:
        for i in status:
            click.echo(i)


if __name__ == '__main__':
    cli()
