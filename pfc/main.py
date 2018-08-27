#!/usr/bin/env python

import os
import click
import swsssdk
from tabulate import tabulate
from natsort import natsorted


def configPfcAsym(interface, pfc_asym):
    """
    PFC handler to configure asymmentric PFC.
    """

    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()

    configdb.mod_entry("PORT", interface, {'pfc_asym': pfc_asym})


def showPfcAsym(interface):
    """
    PFC handler to display asymmetric PFC information.
    """

    i = {}
    table = []
    key = []

    header = ('Interface', 'Asymmetric')

    configdb = swsssdk.ConfigDBConnector()
    configdb.connect()

    if interface:
        db_keys = configdb.keys(configdb.CONFIG_DB, 'PORT|{0}'.format(interface))
    else:
        db_keys = configdb.keys(configdb.CONFIG_DB, 'PORT|*')

    for i in db_keys or [None]:
        if i:
            key = i.split('|')[-1]

        if key and key.startswith('Ethernet'):
            entry = configdb.get_entry('PORT', key)
            table.append([key, entry.get('pfc_asym', 'N/A')])

    sorted_table = natsorted(table)

    print '\n'
    print tabulate(sorted_table, headers=header, tablefmt="simple", missingval="")
    print '\n'


@click.group()
def cli():
    """
    Utility entry point.
    """
    pass


@cli.group()
def config():
    """Config PFC information"""
    pass


@config.command()
@click.argument('status', type=click.Choice(['on', 'off']))
@click.argument('interface', type=click.STRING)
def asymmetric(status, interface):
    """Set asymmetric PFC configuration."""
    configPfcAsym(interface, status)


@cli.group()
def show():
    """Show PFC information"""
    pass


@show.command()
@click.argument('interface', type=click.STRING, required=False)
def asymmetric(interface):
    """Show asymmetric PFC information"""
    showPfcAsym(interface)
