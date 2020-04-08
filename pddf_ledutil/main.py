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
    from utilities_common.util_base import UtilHelper
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SYSLOG_IDENTIFIER = "ledutil"
PLATFORM_SPECIFIC_MODULE_NAME = "ledutil"
PLATFORM_SPECIFIC_CLASS_NAME = "LedUtil"

# Global platform-specific ledutil class instance
platform_ledutil = None

#logger = UtilLogger(SYSLOG_IDENTIFIER)

# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'ledutil' command
@click.group()
def cli():
    """pddf_ledutil - Command line utility for providing FAN information"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load the helper class
    helper = UtilHelper()

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(1)

    # Load platform-specific fanutil class
    global platform_ledutil
    try:
        platform_ledutil = helper.load_platform_util(PLATFORM_SPECIFIC_MODULE_NAME, PLATFORM_SPECIFIC_CLASS_NAME)
    except Exception as e:
        click.echo("Failed to load {}: {}".format(PLATFORM_SPECIFIC_MODULE_NAME, str(e)))
        sys.exit(2)

# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("PDDF ledutil version {0}".format(VERSION))

# 'getstatusled' subcommand
@cli.command()
@click.argument('device_name', type=click.STRING)
@click.argument('index', type=click.STRING)
def getstatusled(device_name, index):
    if device_name is None:
        click.echo("device_name is required")
        raise click.Abort()

    outputs = platform_ledutil.get_status_led(device_name, index)
    click.echo(outputs)


# 'setstatusled' subcommand
@cli.command()
@click.argument('device_name', type=click.STRING)
@click.argument('index', type=click.STRING)
@click.argument('color', type=click.STRING)
@click.argument('color_state', type=click.STRING)
def setstatusled(device_name, index, color, color_state):
    if device_name is None:
        click.echo("device_name is required")
        raise click.Abort()

    outputs = platform_ledutil.set_status_led(device_name, index, color, color_state)
    click.echo(outputs)

if __name__ == '__main__':
    cli()
