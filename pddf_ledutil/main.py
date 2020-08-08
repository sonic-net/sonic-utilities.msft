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

VERSION = '2.0'

SYSLOG_IDENTIFIER = "ledutil"
PLATFORM_SPECIFIC_MODULE_NAME = "ledutil"
PLATFORM_SPECIFIC_CLASS_NAME = "LedUtil"

# Global platform-specific ledutil class instance
platform_ledutil = None
platform_chassis = None


# ==================== Wrapper APIs ====================
def _wrapper_getstatusled(device_name):
    if platform_chassis is not None:
        outputs=platform_chassis.get_system_led(device_name)
    else:
        outputs = platform_ledutil.get_status_led(device_name)
    click.echo(outputs)

def _wrapper_setstatusled(device_name, color, color_state):
    if platform_chassis is not None:
        outputs=platform_chassis.set_system_led(device_name, color)
    else:
        outputs = platform_ledutil.set_status_led(device_name, color, color_state)
    click.echo(outputs)


# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'ledutil' command
@click.group()
def cli():
    """pddf_ledutil - Command line utility for providing System LED information"""

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
    global platform_chassis

    # Load new platform api class
    try:
        import sonic_platform.platform
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
    except Exception as e:
        click.echo("Failed to load chassis due to {}".format(str(e)))

    # Load platform-specific psuutil class if 2.0 implementation is not present
    if platform_chassis is None:
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
def getstatusled(device_name):
    if device_name is None:
        click.echo("device_name is required")
        raise click.Abort()

    _wrapper_getstatusled(device_name)


# 'setstatusled' subcommand
@cli.command()
@click.argument('device_name', type=click.STRING)
@click.argument('color', type=click.STRING)
@click.argument('color_state', default='SOLID', type=click.STRING)
def setstatusled(device_name, color, color_state):
    if device_name is None:
        click.echo("device_name is required")
        raise click.Abort()

    _wrapper_setstatusled(device_name, color, color_state)


if __name__ == '__main__':
    cli()
