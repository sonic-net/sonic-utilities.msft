import os
import subprocess
import sys

import click
import utilities_common.cli as clicommon
from sonic_py_common import device_info, multi_asic


def get_hw_info_dict():
    """
    This function is used to get the HW info helper function
    """
    hw_info_dict = {}

    version_info = device_info.get_sonic_version_info()

    hw_info_dict['platform'] = device_info.get_platform()
    hw_info_dict['hwsku'] = device_info.get_hwsku()
    hw_info_dict['asic_type'] = version_info['asic_type']
    hw_info_dict['asic_count'] = multi_asic.get_num_asics()

    return hw_info_dict


#
# 'platform' group ("show platform ...")
#

@click.group(cls=clicommon.AliasedGroup)
def platform():
    """Show platform-specific hardware info"""
    pass


version_info = device_info.get_sonic_version_info()
if (version_info and version_info.get('asic_type') == 'mellanox'):
    from . import mlnx
    platform.add_command(mlnx.mlnx)


# 'summary' subcommand ("show platform summary")
@platform.command()
@click.option('--json', is_flag=True, help="Output in JSON format")
def summary(json):
    """Show hardware platform information"""

    hw_info_dict = {}
    hw_info_dict = get_hw_info_dict()

    if json:
        click.echo(clicommon.json_dump(hw_info_dict))
    else:
        click.echo("Platform: {}".format(hw_info_dict['platform']))
        click.echo("HwSKU: {}".format(hw_info_dict['hwsku']))
        click.echo("ASIC: {}".format(hw_info_dict['asic_type']))
        click.echo("ASIC Count: {}".format(hw_info_dict['asic_count']))


# 'syseeprom' subcommand ("show platform syseeprom")
@platform.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def syseeprom(verbose):
    """Show system EEPROM information"""
    cmd = "sudo decode-syseeprom -d"
    clicommon.run_command(cmd, display_cmd=verbose)


# 'psustatus' subcommand ("show platform psustatus")
@platform.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of PSU")
@click.option('--json', is_flag=True, help="Output in JSON format")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def psustatus(index, json, verbose):
    """Show PSU status information"""
    cmd = "psushow -s"

    if index >= 0:
        cmd += " -i {}".format(index)

    if json:
        cmd += " -j"

    clicommon.run_command(cmd, display_cmd=verbose)


# 'ssdhealth' subcommand ("show platform ssdhealth [--verbose/--vendor]")
@platform.command()
@click.argument('device', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--vendor', is_flag=True, help="Enable vendor specific output")
def ssdhealth(device, verbose, vendor):
    """Show SSD Health information"""
    if not device:
        device = os.popen("lsblk -o NAME,TYPE -p | grep disk").readline().strip().split()[0]
    cmd = "sudo ssdutil -d " + device
    options = " -v" if verbose else ""
    options += " -e" if vendor else ""
    clicommon.run_command(cmd + options, display_cmd=verbose)


@platform.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('-c', '--check', is_flag=True, help="Check the platfome pcie device")
def pcieinfo(check, verbose):
    """Show Device PCIe Info"""
    cmd = "sudo pcieutil show"
    if check:
        cmd = "sudo pcieutil check"
    clicommon.run_command(cmd, display_cmd=verbose)


# 'fan' subcommand ("show platform fan")
@platform.command()
def fan():
    """Show fan status information"""
    cmd = 'fanshow'
    clicommon.run_command(cmd)


# 'temperature' subcommand ("show platform temperature")
@platform.command()
def temperature():
    """Show device temperature information"""
    cmd = 'tempershow'
    clicommon.run_command(cmd)


# 'firmware' subcommand ("show platform firmware")
@platform.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True
    ),
    add_help_option=False
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def firmware(args):
    """Show firmware information"""
    cmd = "sudo fwutil show {}".format(" ".join(args))

    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
