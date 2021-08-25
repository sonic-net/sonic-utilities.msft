#!/usr/sbin/env python

import click

import utilities_common.cli as clicommon

#
# 'chassis_modules' group ('config chassis_modules ...')
#
@click.group(cls=clicommon.AliasedGroup)
def chassis():
    """Configure chassis commands group"""
    pass

@chassis.group()
def modules():
    """Configure chassis modules"""
    pass

#
# 'shutdown' subcommand ('config chassis_modules shutdown ...')
#
@modules.command('shutdown')
@clicommon.pass_db
@click.argument('chassis_module_name', metavar='<module_name>', required=True)
def shutdown_chassis_module(db, chassis_module_name):
    """Chassis-module shutdown of module"""
    config_db = db.cfgdb
    ctx = click.get_current_context()

    if not chassis_module_name.startswith("SUPERVISOR") and \
       not chassis_module_name.startswith("LINE-CARD") and \
       not chassis_module_name.startswith("FABRIC-CARD"):
        ctx.fail("'module_name' has to begin with 'SUPERVISOR', 'LINE-CARD' or 'FABRIC-CARD'")

    fvs = {'admin_status': 'down'}
    config_db.set_entry('CHASSIS_MODULE', chassis_module_name, fvs)

#
# 'startup' subcommand ('config chassis_modules startup ...')
#
@modules.command('startup')
@clicommon.pass_db
@click.argument('chassis_module_name', metavar='<module_name>', required=True)
def startup_chassis_module(db, chassis_module_name):
    """Chassis-module startup of module"""
    config_db = db.cfgdb

    config_db.set_entry('CHASSIS_MODULE', chassis_module_name, None)
