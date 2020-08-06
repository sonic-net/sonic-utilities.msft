#!/usr/bin/env python
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

SYSLOG_IDENTIFIER = "thermalutil"
PLATFORM_SPECIFIC_MODULE_NAME = "thermalutil"
PLATFORM_SPECIFIC_CLASS_NAME = "ThermalUtil"

# Global platform-specific thermalutil class instance
platform_thermalutil = None
platform_chassis = None

#logger = UtilLogger(SYSLOG_IDENTIFIER)

# Wrapper APIs so that this util is suited to both 1.0 and 2.0 platform APIs
def _wrapper_get_num_thermals():
    if platform_chassis is not None:
        try:
            return platform_chassis.get_num_thermals()
        except NotImplementedError:
            pass
    return platform_thermalutil.get_num_thermals()

def _wrapper_get_thermal_name(idx):
    if platform_chassis is not None:
        try:
            return platform_chassis.get_thermal(idx-1).get_name()
        except NotImplementedError:
            pass
    return "TEMP{}".format(idx)


# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'thermalutil' command
@click.group()
def cli():
    """pddf_thermalutil - Command line utility for providing Temp Sensors information"""

    global platform_thermalutil
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


    # Load platform-specific fanutil class
    if platform_chassis is None:
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
    click.echo(_wrapper_get_num_thermals())

# 'gettemp' subcommand
@cli.command()
@click.option('-i', '--index', default=-1, type=int, help="the index of Temp Sensor")
def gettemp(index):
    """Display Temperature values of thermal sensors"""
    supported_thermal = range(1,  _wrapper_get_num_thermals()+ 1)
    thermal_ids = []
    if (index < 0):
        thermal_ids = supported_thermal
    else:
        thermal_ids = [index]

    header=[]
    status_table = []

    for thermal in thermal_ids:
        thermal_name = _wrapper_get_thermal_name(thermal)
        if thermal not in supported_thermal:
            click.echo("Error! The {} is not available on the platform.\n" \
            "Number of supported Temp - {}.".format(thermal_name, len(supported_thermal)))
            continue
        # TODO: Provide a wrapper API implementation for the below function
        if platform_chassis is not None:
            try:
               temp = platform_chassis.get_thermal(thermal-1).get_temperature()
               if temp:
                   value = "temp1\t %+.1f C ("%temp
               high = platform_chassis.get_thermal(thermal-1).get_high_threshold()
               if high:
                   value += "high = %+.1f C"%high
               crit = platform_chassis.get_thermal(thermal-1).get_high_critical_threshold()
               if high and crit:
                   value += ", "
               if crit:
                   value += "crit = %+.1f C"%crit

               
               label = platform_chassis.get_thermal(thermal-1).get_temp_label()
               value +=")"

            except NotImplementedError:
               pass
	else:
        	label, value = platform_thermalutil.show_thermal_temp_values(thermal)

	if label is None:
        	status_table.append([thermal_name, value])
	else:
        	status_table.append([thermal_name, label, value])

    if status_table:
	if label is None:
		header = ['Temp Sensor', 'Value']
	else:
    		header = ['Temp Sensor', 'Label', 'Value']
        click.echo(tabulate(status_table, header, tablefmt="simple"))

@cli.group()
def debug():
    """pddf_thermalutil debug commands"""
    pass

@debug.command()
def dump_sysfs():
    """Dump all Temp Sensor related SysFS paths"""
    if platform_chassis is not None:
    	supported_thermal = range(1,  _wrapper_get_num_thermals()+ 1)
    	for index in supported_thermal:
    	    status = platform_chassis.get_thermal(index-1).dump_sysfs()
    else:
    	status = platform_thermalutil.dump_sysfs()

    if status:
        for i in status:
            click.echo(i)


if __name__ == '__main__':
    cli()
