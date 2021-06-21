import os
import subprocess
import sys

import click
import utilities_common.cli as clicommon
from sonic_py_common import device_info

#
# Helper functions
#

def get_chassis_info():
    """
    Attempts to get the chassis info via STATE_DB and falls back to direct Platform API calls.
    """

    chassis_info = device_info.get_chassis_info()
    required_keys = ['serial', 'model', 'revision']
    failed_vals = ['', 'N/A']
    platform_chassis = None

    for k in required_keys:
        if chassis_info.get(k, '') in failed_vals:
            if platform_chassis is None:
                import sonic_platform
                platform_chassis = sonic_platform.platform.Platform().get_chassis()
            try:
                chassis_info[k] = getattr(platform_chassis, "get_".format(k))()
            except AttributeError:
                chassis_info[k] = 'N/A'

    return chassis_info

#
# 'platform' group ("show platform ...")
#

@click.group(cls=clicommon.AliasedGroup)
def platform():
    """Show platform-specific hardware info"""
    pass


# 'summary' subcommand ("show platform summary")
@platform.command()
@click.option('--json', is_flag=True, help="Output in JSON format")
def summary(json):
    """Show hardware platform information"""
    platform_info = device_info.get_platform_info()
    chassis_info = get_chassis_info()

    if json:
        click.echo(clicommon.json_dump({**platform_info, **chassis_info}))
    else:
        click.echo("Platform: {}".format(platform_info['platform']))
        click.echo("HwSKU: {}".format(platform_info['hwsku']))
        click.echo("ASIC: {}".format(platform_info['asic_type']))
        click.echo("ASIC Count: {}".format(platform_info['asic_count']))
        click.echo("Serial Number: {}".format(chassis_info['serial']))
        click.echo("Model Number: {}".format(chassis_info['model']))
        click.echo("Hardware Revision: {}".format(chassis_info['revision']))


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
