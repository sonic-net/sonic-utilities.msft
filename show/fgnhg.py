import ipaddress
from collections import OrderedDict

import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate


@click.group(cls=clicommon.AliasedGroup)
def fgnhg():
    """Show FGNHG information"""
    pass


@fgnhg.command()
@click.argument('nhg', required=False)
def active_hops(nhg):
    config_db = ConfigDBConnector()
    config_db.connect()
    fg_nhg_prefix_table = {}
    fg_nhg_alias = {}
    fg_nhg_prefix_table = config_db.get_table('FG_NHG_PREFIX')

    for key, value in fg_nhg_prefix_table.items():
        fg_nhg_alias[key] = value['FG_NHG']

    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)  # Make one attempt only STATE_DB

    TABLE_NAME_SEPARATOR = '|'
    prefix = 'FG_ROUTE_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(prefix, '*')
    table_keys = []
    table_keys = state_db.keys(state_db.STATE_DB, _hash)
    t_dict = {}
    header = ["FG_NHG_PREFIX", "Active Next Hops"]
    table = []
    output_dict = {}

    if nhg is None:
        for nhg_prefix in table_keys:
            t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)
            vals = sorted(set([val for val in t_dict.values()]))
            for nh_ip in vals:
                if nhg_prefix in output_dict:
                    output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                else:
                    output_dict[nhg_prefix] = [nh_ip.split("@")[0]]

            nhg_prefix_report = (nhg_prefix.split("|")[1])
            formatted_nhps = ','.replace(',', '\n').join(output_dict[nhg_prefix])
            table.append([nhg_prefix_report, formatted_nhps])

        click.echo(tabulate(table, header, tablefmt="grid"))

    else:
        for nhg_prefix, alias in fg_nhg_alias.items():
            if nhg == alias:
                if ":" in nhg_prefix:
                    for key in table_keys:
                        mod_key = key.split("|")[1].split("/")[0]
                        mod_nhg_prefix = nhg_prefix.split("/")[0]
                        if ipaddress.ip_address(mod_key).exploded == ipaddress.ip_address(mod_nhg_prefix).exploded:
                            t_dict = state_db.get_all(state_db.STATE_DB, key)
                    nhg_prefix = "FG_ROUTE_TABLE|" + nhg_prefix
                else:
                    nhg_prefix = "FG_ROUTE_TABLE|" + nhg_prefix
                    t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)

                vals = sorted(set([val for val in t_dict.values()]))

                for nh_ip in vals:
                    if nhg_prefix in output_dict:
                        output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                    else:
                        output_dict[nhg_prefix] = [nh_ip.split("@")[0]]

                nhg_prefix_report = (nhg_prefix.split("|")[1])
                formatted_nhps = ','.replace(',', '\n').join(output_dict[nhg_prefix])
                table.append([nhg_prefix_report, formatted_nhps])
                click.echo(tabulate(table, header, tablefmt="grid"))


@fgnhg.command()
@click.argument('nhg', required=False)
def hash_view(nhg):
    config_db = ConfigDBConnector()
    config_db.connect()
    fg_nhg_prefix_table = {}
    fg_nhg_alias = {}
    fg_nhg_prefix_table = config_db.get_table('FG_NHG_PREFIX')

    for key, value in fg_nhg_prefix_table.items():
        fg_nhg_alias[key] = value['FG_NHG']

    state_db = SonicV2Connector(host='127.0.0.1')
    state_db.connect(state_db.STATE_DB, False)  # Make one attempt only STATE_DB

    TABLE_NAME_SEPARATOR = '|'
    prefix = 'FG_ROUTE_TABLE' + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(prefix, '*')
    table_keys = []
    table_keys = state_db.keys(state_db.STATE_DB, _hash)
    t_dict = {}
    header = ["FG_NHG_PREFIX", "Next Hop", "Hash buckets"]
    table = []
    output_dict = {}
    bank_dict = {}

    if nhg is None:
        for nhg_prefix in table_keys:
            bank_dict = {}
            t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)
            vals = sorted(set([val for val in t_dict.values()]))

            for nh_ip in vals:
                bank_ids = sorted([int(k) for k, v in t_dict.items() if v == nh_ip])

                bank_ids = [str(x) for x in bank_ids]

                if nhg_prefix in output_dict:
                    output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                else:
                    output_dict[nhg_prefix] = [nh_ip.split("@")[0]]
                bank_dict[nh_ip.split("@")[0]] = bank_ids

            bank_dict = OrderedDict(sorted(bank_dict.items()))
            nhg_prefix_report = (nhg_prefix.split("|")[1])

            for nhip, val in bank_dict.items():
                formatted_banks = ','.replace(',', '\n').join(bank_dict[nhip])
                table.append([nhg_prefix_report, nhip, formatted_banks])

        click.echo(tabulate(table, header, tablefmt="grid"))

    else:
        for nhg_prefix, alias in fg_nhg_alias.items():
            if nhg == alias:
                if ":" in nhg_prefix:
                    for key in table_keys:
                        mod_key = key.split("|")[1].split("/")[0]
                        mod_nhg_prefix = nhg_prefix.split("/")[0]
                        if ipaddress.ip_address(mod_key).exploded == ipaddress.ip_address(mod_nhg_prefix).exploded:
                            t_dict = state_db.get_all(state_db.STATE_DB, key)
                    nhg_prefix = "FG_ROUTE_TABLE|" + nhg_prefix
                else:
                    nhg_prefix = "FG_ROUTE_TABLE|" + nhg_prefix
                    t_dict = state_db.get_all(state_db.STATE_DB, nhg_prefix)

                vals = sorted(set([val for val in t_dict.values()]))

                for nh_ip in vals:
                    bank_ids = sorted([int(k) for k, v in t_dict.items() if v == nh_ip])
                    bank_ids = [str(x) for x in bank_ids]
                    if nhg_prefix in output_dict:
                        output_dict[nhg_prefix].append(nh_ip.split("@")[0])
                    else:
                        output_dict[nhg_prefix] = [nh_ip.split("@")[0]]
                    bank_dict[nh_ip.split("@")[0]] = bank_ids

                nhg_prefix_report = (nhg_prefix.split("|")[1])
                bank_dict = OrderedDict(sorted(bank_dict.items()))

                for nhip, val in bank_dict.items():
                    formatted_banks = ','.replace(',', '\n').join(bank_dict[nhip])
                    table.append([nhg_prefix_report, nhip, formatted_banks])

                click.echo(tabulate(table, header, tablefmt="grid"))
