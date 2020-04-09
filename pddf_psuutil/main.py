#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with PSU Controller in PDDF mode in SONiC
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

SYSLOG_IDENTIFIER = "psuutil"
PLATFORM_SPECIFIC_MODULE_NAME = "psuutil"
PLATFORM_SPECIFIC_CLASS_NAME = "PsuUtil"

# Global platform-specific psuutil class instance
platform_psuutil = None

#logger = UtilLogger(SYSLOG_IDENTIFIER)

# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'psuutil' command
@click.group()
def cli():
    """psuutil - Command line utility for providing PSU status"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load the helper class
    helper = UtilHelper()

    if not helper.check_pddf_mode():
        click.echo("PDDF mode should be supported and enabled for this platform for this operation")
        sys.exit(1)

    # Load platform-specific fanutil class
    global platform_psuutil
    try:
        platform_psuutil = helper.load_platform_util(PLATFORM_SPECIFIC_MODULE_NAME, PLATFORM_SPECIFIC_CLASS_NAME)
    except Exception as e:
        click.echo("Failed to load {}: {}".format(PLATFORM_SPECIFIC_MODULE_NAME, str(e)))
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
            click.echo("Error! The {} is not available on the platform.\n" \
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

# 'mfrinfo' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
def mfrinfo(index):
    """Display PSU manufacturer info"""
    supported_psu = range(1, platform_psuutil.get_num_psus() + 1)
    psu_ids = []
    if (index < 0):
        psu_ids = supported_psu
    else:
        psu_ids = [index]

    for psu in psu_ids:
        psu_name = "PSU {}".format(psu)
        if psu not in supported_psu:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported PSU - {}.".format(psu_name, platform_psuutil.get_num_psus()))
            continue
        status = platform_psuutil.get_psu_status(psu)
        if not status:
            click.echo("{} is Not OK\n".format(psu_name))
            continue

        model_name = platform_psuutil.get_model(psu)
        mfr_id = platform_psuutil.get_mfr_id(psu)
        serial_num = platform_psuutil.get_serial(psu)
        airflow_dir = platform_psuutil.get_direction(psu)
        
        click.echo("{} is OK\nManufacture Id: {}\n" \
                "Model: {}\nSerial Number: {}\n" \
                "Fan Direction: {}\n".format(psu_name, mfr_id, model_name, serial_num, airflow_dir))


# 'seninfo' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
def seninfo(index):
    """Display PSU sensor info"""
    supported_psu = range(1, platform_psuutil.get_num_psus() + 1)
    psu_ids = []
    if (index < 0):
        psu_ids = supported_psu
    else:
        psu_ids = [index]

    for psu in psu_ids:
        psu_name = "PSU {}".format(psu)
        if psu not in supported_psu:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported PSU - {}.".format(psu_name, platform_psuutil.get_num_psus()))
            continue
        oper_status = platform_psuutil.get_psu_status(psu)
        
        if not oper_status:
            click.echo("{} is Not OK\n".format(psu_name))
            continue

        v_out = platform_psuutil.get_output_voltage(psu)
        i_out = platform_psuutil.get_output_current(psu)
        p_out = platform_psuutil.get_output_power(psu)
        # p_out would be in micro watts, convert it into milli watts
        p_out = p_out/1000

        fan1_rpm = platform_psuutil.get_fan_speed(psu, 1)
        click.echo("{} is OK\nOutput Voltage: {} mv\n" \
                "Output Current: {} ma\nOutput Power: {} mw\n" \
                "Fan1 Speed: {} rpm\n".format(psu_name, v_out, i_out, p_out, fan1_rpm))

@cli.group()
def debug():
    """pddf_psuutil debug commands"""
    pass

@debug.command('dump-sysfs')
def dump_sysfs():
    """Dump all PSU related SysFS paths"""
    status = platform_psuutil.dump_sysfs()

    if status:
        for i in status:
            click.echo(i)


if __name__ == '__main__':
    cli()
