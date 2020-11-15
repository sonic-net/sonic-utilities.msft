#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with PSU in SONiC
#

try:
    import imp
    import os
    import sys

    import click
    from sonic_py_common import device_info, logger
    from tabulate import tabulate
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SYSLOG_IDENTIFIER = "psuutil"
PLATFORM_SPECIFIC_MODULE_NAME = "psuutil"
PLATFORM_SPECIFIC_CLASS_NAME = "PsuUtil"

# Global platform-specific psuutil class instance
platform_psuutil = None


# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)


# ==================== Methods for initialization ====================

# Loads platform specific psuutil module from source
def load_platform_psuutil():
    global platform_psuutil

    # Load platform module from source
    platform_path, _ = device_info.get_paths_to_platform_and_hwsku_dirs()

    try:
        module_file = os.path.join(platform_path, "plugins", PLATFORM_SPECIFIC_MODULE_NAME + ".py")
        module = imp.load_source(PLATFORM_SPECIFIC_MODULE_NAME, module_file)
    except IOError as e:
        log.log_error("Failed to load platform module '%s': %s" % (PLATFORM_SPECIFIC_MODULE_NAME, str(e)), True)
        return -1

    try:
        platform_psuutil_class = getattr(module, PLATFORM_SPECIFIC_CLASS_NAME)
        platform_psuutil = platform_psuutil_class()
    except AttributeError as e:
        log.log_error("Failed to instantiate '%s' class: %s" % (PLATFORM_SPECIFIC_CLASS_NAME, str(e)), True)
        return -2

    return 0


# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'psuutil' command
@click.group()
def cli():
    """psuutil - Command line utility for providing PSU status"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load platform-specific psuutil class
    err = load_platform_psuutil()
    if err != 0:
        sys.exit(2)

# 'version' subcommand


@cli.command()
def version():
    """Display version info"""
    click.echo("psuutil version {0}".format(VERSION))

# 'numpsus' subcommand


@cli.command()
def numpsus():
    """Display number of supported PSUs on device"""
    click.echo(str(platform_psuutil.get_num_psus()))

# 'status' subcommand


@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
def status(index):
    """Display PSU status"""
    supported_psu = list(range(1, platform_psuutil.get_num_psus() + 1))
    psu_ids = []
    if (index < 0):
        psu_ids = supported_psu
    else:
        psu_ids = [index]

    header = ['PSU', 'Status']
    status_table = []

    for psu in psu_ids:
        msg = ""
        psu_name = "PSU {}".format(psu)
        if psu not in supported_psu:
            click.echo("Error! The {} is not available on the platform.\n"
                       "Number of supported PSU - {}.".format(psu_name, platform_psuutil.get_num_psus()))
            continue
        presence = platform_psuutil.get_psu_presence(psu)
        if presence:
            oper_status = platform_psuutil.get_psu_status(psu)
            msg = 'OK' if oper_status else "NOT OK"
        else:
            msg = 'NOT PRESENT'
        status_table.append([psu_name, msg])

    if status_table:
        click.echo(tabulate(status_table, header, tablefmt="simple"))


if __name__ == '__main__':
    cli()
