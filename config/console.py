#!/usr/bin/env python

import click

import utilities_common.cli as clicommon

#
# 'console' group ('config console ...')
#
@click.group('console')
def console():
    """Console-related configuration tasks"""
    pass

#
# 'console add' group ('config console add ...')
#
@console.command('add')
@clicommon.pass_db
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
@click.option('--baud', '-b', metavar='<baud>', required=True, type=click.INT)
@click.option('--flowcontrol', '-f', metavar='<flow_control>', required=False, is_flag=True)
@click.option('--devicename', '-d', metavar='<device_name>', required=False)
def add_console_setting(db, linenum, baud, flowcontrol, devicename):
    """Add Console-realted configuration tasks"""
    config_db = db.cfgdb

    table = "CONSOLE_PORT"
    dataKey1 = 'baud_rate'
    dataKey2 = 'flow_control'
    dataKey3 = 'remote_device'

    ctx = click.get_current_context()
    data = config_db.get_entry(table, linenum)
    if data:
        ctx.fail("Trying to add console port setting, which is already exists.")
    else:
        console_entry = { dataKey1: baud }
        console_entry[dataKey2] = "1" if flowcontrol else "0"

        if devicename:
            if isExistingSameDevice(config_db, devicename, table):
                ctx.fail("Given device name {} has been used. Please enter a valid device name or remove the existing one !!".format(devicename))
            console_entry[dataKey3] = devicename

        config_db.set_entry(table, linenum, console_entry)


#
# 'console del' group ('config console del ...')
#
@console.command('del')
@clicommon.pass_db
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
def remove_console_setting(db, linenum):
    """Remove Console-related configuration tasks"""
    config_db = db.cfgdb

    table = "CONSOLE_PORT"

    data = config_db.get_entry(table, linenum)
    if data:
        config_db.mod_entry(table, linenum, None)
    else:
        ctx = click.get_current_context()
        ctx.fail("Trying to delete console port setting, which is not present.")


def isExistingSameDevice(config_db, deviceName, table):
    """Check if the given device name is conflict with existing device"""
    settings = config_db.get_table(table)
    for key,values in settings.items():
        if "remote_device" in values and deviceName == values["remote_device"]:
            return True

    return False