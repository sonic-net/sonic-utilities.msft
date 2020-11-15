#!/usr/bin/env python3
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

VERSION = '2.0'

SYSLOG_IDENTIFIER = "psuutil"
PLATFORM_SPECIFIC_MODULE_NAME = "psuutil"
PLATFORM_SPECIFIC_CLASS_NAME = "PsuUtil"

# Global platform-specific psuutil class instance
platform_psuutil = None
platform_chassis = None


# Wrapper APIs so that this util is suited to both 1.0 and 2.0 platform APIs
def _wrapper_get_num_psus():
    if platform_chassis is not None:
        try:
            return platform_chassis.get_num_psus()
        except NotImplementedError:
            pass
    return platform_psuutil.get_num_psus()

def _wrapper_get_psu_name(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_name()
        except NotImplementedError:
            pass
    return "PSU {}".format(idx)

def _wrapper_get_psu_presence(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_presence()
        except NotImplementedError:
            pass
    return platform_psuutil.get_psu_presence(idx)

def _wrapper_get_psu_status(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_status()
        except NotImplementedError:
            pass
    return platform_psuutil.get_psu_status(idx)

def _wrapper_get_psu_model(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_model()
        except NotImplementedError:
            pass
    return platform_psuutil.get_model(idx)

def _wrapper_get_psu_mfr_id(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_mfr_id()
        except NotImplementedError:
            pass
    return platform_psuutil.get_mfr_id(idx)

def _wrapper_get_psu_serial(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_serial()
        except NotImplementedError:
            pass
    return platform_psuutil.get_serial(idx)

def _wrapper_get_psu_direction(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1)._fan_list[0].get_direction()
        except NotImplementedError:
            pass
    return platform_psuutil.get_direction(idx)

def _wrapper_get_output_voltage(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_voltage()
        except NotImplementedError:
            pass
    return platform_psuutil.get_output_voltage(idx)

def _wrapper_get_output_current(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_current()
        except NotImplementedError:
            pass
    return platform_psuutil.get_output_current(idx)

def _wrapper_get_output_power(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1).get_power()
        except NotImplementedError:
            pass
    return platform_psuutil.get_output_power(idx)

def _wrapper_get_fan_rpm(idx, fan_idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx-1)._fan_list[fan_idx-1].get_speed_rpm()
        except NotImplementedError:
            pass
    return platform_psuutil.get_fan_rpm(idx, fan_idx)

def _wrapper_dump_sysfs(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_psu(idx).dump_sysfs()
        except NotImplementedError:
            pass
    return platform_psuutil.dump_sysfs()

# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'psuutil' command
@click.group()
def cli():
    """psuutil - Command line utility for providing PSU status"""

    global platform_psuutil
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


    # Load platform-specific psuutil class if 2.0 implementation is not present
    if platform_chassis is None:
        try:
            platform_psuutil = helper.load_platform_util(PLATFORM_SPECIFIC_MODULE_NAME, PLATFORM_SPECIFIC_CLASS_NAME)
        except Exception as e:
            click.echo("Failed to load {}: {}".format(PLATFORM_SPECIFIC_MODULE_NAME, str(e)))
            sys.exit(2)

# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("PDDF psuutil version {0}".format(VERSION))

# 'numpsus' subcommand
@cli.command()
def numpsus():
    """Display number of supported PSUs on device"""
    click.echo(_wrapper_get_num_psus())

# 'status' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
def status(index):
    """Display PSU status"""
    supported_psu = list(range(1, _wrapper_get_num_psus() + 1))
    psu_ids = []
    if (index < 0):
        psu_ids = supported_psu
    else:
        psu_ids = [index]

    header = ['PSU', 'Status']
    status_table = []

    for psu in psu_ids:
        msg = ""
        psu_name = _wrapper_get_psu_name(psu)
        if psu not in supported_psu:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported PSU - {}.".format(psu_name, len(supported_psu)))
            continue
        presence = _wrapper_get_psu_presence(psu)
        if presence:
            oper_status = _wrapper_get_psu_status(psu)
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
    supported_psu = list(range(1, _wrapper_get_num_psus() + 1))
    psu_ids = []
    if (index < 0):
        psu_ids = supported_psu
    else:
        psu_ids = [index]

    for psu in psu_ids:
        psu_name = _wrapper_get_psu_name(psu)
        if psu not in supported_psu:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported PSU - {}.".format(psu_name, len(supported_psu)))
            continue
        status = _wrapper_get_psu_status(psu)
        if not status:
            click.echo("{} is Not OK\n".format(psu_name))
            continue

        model_name = _wrapper_get_psu_model(psu)
        mfr_id = _wrapper_get_psu_mfr_id(psu)
        serial_num = _wrapper_get_psu_serial(psu)
        airflow_dir = _wrapper_get_psu_direction(psu)
        
        click.echo("{} is OK\nManufacture Id: {}\n" \
                "Model: {}\nSerial Number: {}\n" \
                "Fan Direction: {}\n".format(psu_name, mfr_id, model_name, serial_num, airflow_dir.capitalize()))


# 'seninfo' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
def seninfo(index):
    """Display PSU sensor info"""
    supported_psu = list(range(1, _wrapper_get_num_psus() + 1))
    psu_ids = []
    if (index < 0):
        psu_ids = supported_psu
    else:
        psu_ids = [index]

    for psu in psu_ids:
        psu_name = _wrapper_get_psu_name(psu)
        if psu not in supported_psu:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported PSU - {}.".format(psu_name, len(supported_psu)))
            continue
        oper_status = _wrapper_get_psu_status(psu)
        
        if not oper_status:
            click.echo("{} is Not OK\n".format(psu_name))
            continue

        v_out = _wrapper_get_output_voltage(psu) * 1000
        i_out = _wrapper_get_output_current(psu) * 1000
        p_out = _wrapper_get_output_power(psu) * 1000

        fan1_rpm = _wrapper_get_fan_rpm(psu, 1)
        click.echo("{} is OK\nOutput Voltage: {} mv\n" \
                "Output Current: {} ma\nOutput Power: {} mw\n" \
                "Fan1 Speed: {} rpm\n".format(psu_name, v_out, i_out, p_out, fan1_rpm))

@cli.group()
def debug():
    """pddf_psuutil debug commands"""
    pass

@debug.command()
def dump_sysfs():
    """Dump all PSU related SysFS paths"""
    for psu in range(_wrapper_get_num_psus()):
        status = _wrapper_dump_sysfs(psu)

        if status:
            for i in status:
                click.echo(i)


if __name__ == '__main__':
    cli()
