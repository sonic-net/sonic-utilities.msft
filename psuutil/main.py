#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with PSU in SONiC
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
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SYSLOG_IDENTIFIER = "psuutil"
PLATFORM_SPECIFIC_MODULE_NAME = "psuutil"
PLATFORM_SPECIFIC_CLASS_NAME = "PsuUtil"

PLATFORM_ROOT_PATH = '/usr/share/sonic/device'
PLATFORM_ROOT_PATH_DOCKER = '/usr/share/sonic/platform'
SONIC_CFGGEN_PATH = '/usr/local/bin/sonic-cfggen'
MINIGRAPH_PATH = '/etc/sonic/minigraph.xml'
HWSKU_KEY = "DEVICE_METADATA['localhost']['hwsku']"
PLATFORM_KEY = 'platform'

# Global platform-specific psuutil class instance
platform_psuutil = None


# ========================== Syslog wrappers ==========================


def log_info(msg, also_print_to_console=False):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()

    if also_print_to_console:
        print msg


def log_warning(msg, also_print_to_console=False):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_WARNING, msg)
    syslog.closelog()

    if also_print_to_console:
        print msg


def log_error(msg, also_print_to_console=False):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()

    if also_print_to_console:
        print msg


# ==================== Methods for initialization ====================

# Returns platform and HW SKU
def get_platform_and_hwsku():
    try:
        proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-v', PLATFORM_KEY],
                                stdout=subprocess.PIPE,
                                shell=False,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        platform = stdout.rstrip('\n')

        proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-m', MINIGRAPH_PATH, '-v', HWSKU_KEY],
                                stdout=subprocess.PIPE,
                                shell=False,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        hwsku = stdout.rstrip('\n')
    except OSError, e:
        raise OSError("Cannot detect platform")

    return (platform, hwsku)


# Loads platform specific psuutil module from source
def load_platform_psuutil():
    global platform_psuutil

    # Get platform and hwsku
    (platform, hwsku) = get_platform_and_hwsku()

    # Load platform module from source
    platform_path = ''
    if len(platform) != 0:
        platform_path = "/".join([PLATFORM_ROOT_PATH, platform])
    else:
        platform_path = PLATFORM_ROOT_PATH_DOCKER
    hwsku_path = "/".join([platform_path, hwsku])

    try:
        module_file = "/".join([platform_path, "plugins", PLATFORM_SPECIFIC_MODULE_NAME + ".py"])
        module = imp.load_source(PLATFORM_SPECIFIC_MODULE_NAME, module_file)
    except IOError, e:
        log_error("Failed to load platform module '%s': %s" % (PLATFORM_SPECIFIC_MODULE_NAME, str(e)), True)
        return -1

    try:
        platform_psuutil_class = getattr(module, PLATFORM_SPECIFIC_CLASS_NAME)
        platform_psuutil = platform_psuutil_class()
    except AttributeError, e:
        log_error("Failed to instantiate '%s' class: %s" % (PLATFORM_SPECIFIC_CLASS_NAME, str(e)), True)
        return -2

    return 0


# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'psuutil' command
@click.group()
def cli():
    """psuutil - Command line utility for providing PSU status"""

    if os.geteuid() != 0:
        print "Root privileges are required for this operation"
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
    "Display the number of supported PSU in the device"
    print(str(platform_psuutil.get_num_psus()))

# 'status' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
@click.option('--textonly', is_flag=True, help="show the PSU status in a simple text format instead of table")
def status(index, textonly):
    """Display PSU status"""
    supported_psu = range(1, platform_psuutil.get_num_psus() + 1)
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
            status_table.append([psu_name, "NOT SUPPORTED"])
            continue
        presence = platform_psuutil.get_psu_presence(psu)
        if presence:
            oper_status = platform_psuutil.get_psu_status(psu)
            msg = 'OK' if oper_status else "NOT OK"
        else:
            msg = 'NOT PRESENT'
        status_table.append([psu_name, msg])

    if textonly:
        for status in status_table:
            print status[0] + ':' + status[1]
    else:
        print tabulate(status_table, header, tablefmt="grid")

if __name__ == '__main__':
    cli()
