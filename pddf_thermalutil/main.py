#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with Thermal sensors in PDDF mode in SONiC
#

try:
    import sys
    import os
    import subprocess
    import click
    import imp
    import syslog
    import types
    import traceback
    from tabulate import tabulate
    from utilities_common import util_base
    from utilities_common.util_base import UtilLogger
    from utilities_common.util_base import UtilHelper
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SYSLOG_IDENTIFIER = "thermalutil"
PLATFORM_SPECIFIC_MODULE_NAME = "thermalutil"
PLATFORM_SPECIFIC_CLASS_NAME = "ThermalUtil"

# Global platform-specific thermalutil class instance
platform_thermalutil = None

#logger = UtilLogger(SYSLOG_IDENTIFIER)

# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'thermalutil' command
@click.group()
def cli():
    """pddf_thermalutil - Command line utility for providing Temp Sensors information"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load the helper class
    helper = UtilHelper()

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(1)

    # Load platform-specific fanutil class
    global platform_thermalutil
    try:
        platform_thermalutil = helper.load_platform_util(PLATFORM_SPECIFIC_MODULE_NAME, PLATFORM_SPECIFIC_CLASS_NAME)
    except Exception as e:
        click.echo("Failed to load {}: {}".format(PLATFORM_SPECIFIC_MODULE_NAME, str(e)))
        sys.exit(2)


# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("PDDF thermalutil version {0}".format(VERSION))

# 'numthermals' subcommand
@cli.command()
def numthermals():
    """Display number of Thermal Sensors installed """
    click.echo(str(platform_thermalutil.get_num_thermals()))

# 'gettemp' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of Temp Sensor")
def gettemp(index):
    """Display Temperature values of thermal sensors"""
    supported_thermal = range(1, platform_thermalutil.get_num_thermals() + 1)
    thermal_ids = []
    if (index < 0):
        thermal_ids = supported_thermal
    else:
        thermal_ids = [index]

    header = ['Temp Sensor', 'Label', 'Value']
    status_table = []

    for thermal in thermal_ids:
        msg = ""
        thermal_name = "TEMP{}".format(thermal)
        if thermal not in supported_thermal:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported Temp - {}.".format(thermal_name, platform_thermalutil.get_num_thermals()))
            ##continue
        label, value = platform_thermalutil.show_thermal_temp_values(thermal)
        status_table.append([thermal_name, label, value])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt="simple"))

@cli.group()
def debug():
    """pddf_thermalutil debug commands"""
    pass

@debug.command('dump-sysfs')
def dump_sysfs():
    """Dump all Temp Sensor related SysFS paths"""
    status = platform_thermalutil.dump_sysfs()

    if status:
        for i in status:
            click.echo(i)


if __name__ == '__main__':
    cli()
