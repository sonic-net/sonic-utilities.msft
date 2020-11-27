import json
import sys

import click
import utilities_common.cli as clicommon
from sonic_py_common import multi_asic
from swsscommon import swsscommon
from swsssdk import ConfigDBConnector
from tabulate import tabulate
from utilities_common import platform_sfputil_helper

platform_sfputil = None

REDIS_TIMEOUT_MSECS = 0

CONFIG_SUCCESSFUL = 101
CONFIG_FAIL = 1
STATUS_FAIL = 1
STATUS_SUCCESSFUL = 102

#
# 'muxcable' command ("show muxcable")
#


@click.group(name='muxcable', cls=clicommon.AliasedGroup)
def muxcable():
    """SONiC command line - 'show muxcable' command"""

    global platform_sfputil
    # Load platform-specific sfputil class
    platform_sfputil_helper.load_platform_sfputil()

    # Load port info
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings()

    platform_sfputil = platform_sfputil_helper.platform_sfputil


def get_value_for_key_in_dict(mdict, port, key, table_name):
    value = mdict.get(key, None)
    if value is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table_name))
        sys.exit(STATUS_FAIL)

    return value


def get_value_for_key_in_config_tbl(config_db, port, key, table):
    info_dict = {}
    info_dict = config_db.get_entry(table, port)
    if info_dict is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table))
        sys.exit(STATUS_FAIL)

    value = get_value_for_key_in_dict(info_dict, port, key, table)

    return value


def get_switch_name(config_db):
    info_dict = {}
    info_dict = config_db.get_entry("DEVICE_METADATA", "localhost")
    #click.echo("{} ".format(info_dict))

    switch_name = get_value_for_key_in_dict(info_dict, "localhost", "hostname", "DEVICE_METADATA")
    if switch_name is not None:
        return switch_name
    else:
        click.echo("could not retreive switch name")
        sys.exit(STATUS_FAIL)


def create_json_dump_per_port_status(port_status_dict, muxcable_info_dict, asic_index, port):

    status_value = get_value_for_key_in_dict(muxcable_info_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    port_status_dict["MUX_CABLE"][port] = {}
    port_status_dict["MUX_CABLE"][port]["STATUS"] = status_value
    # TODO : Fix the health status of the port
    port_status_dict["MUX_CABLE"][port]["HEALTH"] = "HEALTHY"


def create_table_dump_per_port_status(print_data, muxcable_info_dict, asic_index, port):

    print_port_data = []

    status_value = get_value_for_key_in_dict(muxcable_info_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    #status_value = get_value_for_key_in_tbl(y_cable_asic_table, port, "status")
    print_port_data.append(port)
    print_port_data.append(status_value)
    print_port_data.append("HEALTHY")
    print_data.append(print_port_data)


def create_table_dump_per_port_config(print_data, per_npu_configdb, asic_id, port):

    port_list = []
    port_list.append(port)
    state_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "state", "MUX_CABLE")
    port_list.append(state_value)
    ipv4_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv4", "MUX_CABLE")
    port_list.append(ipv4_value)
    ipv6_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv6", "MUX_CABLE")
    port_list.append(ipv6_value)
    print_data.append(port_list)


def create_json_dump_per_port_config(port_status_dict, per_npu_configdb, asic_id, port):

    state_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "state", "MUX_CABLE")
    port_status_dict["MUX_CABLE"]["PORTS"][port] = {"STATE": state_value}
    port_status_dict["MUX_CABLE"]["PORTS"][port]["SERVER"] = {}
    ipv4_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv4", "MUX_CABLE")
    port_status_dict["MUX_CABLE"]["PORTS"][port]["SERVER"]["IPv4"] = ipv4_value
    ipv6_value = get_value_for_key_in_config_tbl(per_npu_configdb[asic_id], port, "server_ipv6", "MUX_CABLE")
    port_status_dict["MUX_CABLE"]["PORTS"][port]["SERVER"]["IPv6"] = ipv6_value


@muxcable.command()
@click.argument('port', required=False, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
def status(port, json_output):
    """Show muxcable status information"""

    port_table_keys = {}
    per_npu_statedb = {}
    muxcable_info_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        per_npu_statedb[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')

    if port is not None:
        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
                sys.exit(STATUS_FAIL)

        muxcable_info_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
        if muxcable_info_dict[asic_index] is not None:
            logical_key = "MUX_CABLE_TABLE"+"|"+port
            if logical_key in port_table_keys[asic_index]:

                if json_output:
                    port_status_dict = {}
                    port_status_dict["MUX_CABLE"] = {}

                    create_json_dump_per_port_status(port_status_dict, muxcable_info_dict, asic_index, port)

                    click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
                    sys.exit(STATUS_SUCCESSFUL)
                else:
                    print_data = []

                    create_table_dump_per_port_status(print_data, muxcable_info_dict, asic_index, port)

                    headers = ['PORT', 'STATUS', 'HEALTH']

                    click.echo(tabulate(print_data, headers=headers))
                    sys.exit(STATUS_SUCCESSFUL)
            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(STATUS_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(STATUS_FAIL)

    else:

        if json_output:
            port_status_dict = {}
            port_status_dict["MUX_CABLE"] = {}
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for key in port_table_keys[asic_id]:
                    port = key.split("|")[1]
                    muxcable_info_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
                    create_json_dump_per_port_status(port_status_dict, muxcable_info_dict, asic_id, port)

            click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
        else:
            print_data = []
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for key in port_table_keys[asic_id]:
                    port = key.split("|")[1]
                    muxcable_info_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))

                    create_table_dump_per_port_status(print_data, muxcable_info_dict, asic_id, port)

            headers = ['PORT', 'STATUS', 'HEALTH']
            click.echo(tabulate(print_data, headers=headers))

        sys.exit(STATUS_SUCCESSFUL)


@muxcable.command()
@click.argument('port', required=False, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
def config(port, json_output):
    """Show muxcable config information"""

    port_mux_tbl_keys = {}
    asic_start_idx = None
    per_npu_configdb = {}
    mux_tbl_cfg_db = {}
    peer_switch_tbl_cfg_db = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        if asic_start_idx is None:
            asic_start_idx = asic_id
        # TO-DO replace the macros with correct swsscommon names
        #config_db[asic_id] = swsscommon.DBConnector("CONFIG_DB", REDIS_TIMEOUT_MSECS, True, namespace)
        #mux_tbl_cfg_db[asic_id] = swsscommon.Table(config_db[asic_id], swsscommon.CFG_MUX_CABLE_TABLE_NAME)
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        per_npu_configdb[asic_id].connect()
        mux_tbl_cfg_db[asic_id] = per_npu_configdb[asic_id].get_table("MUX_CABLE")
        peer_switch_tbl_cfg_db[asic_id] = per_npu_configdb[asic_id].get_table("PEER_SWITCH")
        #peer_switch_tbl_cfg_db[asic_id] = swsscommon.Table(config_db[asic_id], swsscommon.CFG_PEER_SWITCH_TABLE_NAME)
        port_mux_tbl_keys[asic_id] = mux_tbl_cfg_db[asic_id].keys()

    if port is not None:
        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
                sys.exit(CONFIG_FAIL)

        port_status_dict = {}
        port_status_dict["MUX_CABLE"] = {}
        port_status_dict["MUX_CABLE"]["PEER_TOR"] = {}
        peer_switch_value = None

        switch_name = get_switch_name(per_npu_configdb[asic_start_idx])
        if asic_start_idx is not None:
            peer_switch_value = get_value_for_key_in_config_tbl(
                per_npu_configdb[asic_start_idx], switch_name, "address_ipv4", "PEER_SWITCH")
            port_status_dict["MUX_CABLE"]["PEER_TOR"] = peer_switch_value
        if port_mux_tbl_keys[asic_id] is not None:
            if port in port_mux_tbl_keys[asic_id]:

                if json_output:

                    port_status_dict["MUX_CABLE"] = {}
                    port_status_dict["MUX_CABLE"]["PORTS"] = {}
                    create_json_dump_per_port_config(port_status_dict, per_npu_configdb, asic_id, port)

                    click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
                    sys.exit(CONFIG_SUCCESSFUL)
                else:
                    print_data = []
                    print_peer_tor = []

                    create_table_dump_per_port_config(print_data, per_npu_configdb, asic_id, port)

                    headers = ['SWITCH_NAME', 'PEER_TOR']
                    peer_tor_data = []
                    peer_tor_data.append(switch_name)
                    peer_tor_data.append(peer_switch_value)
                    print_peer_tor.append(peer_tor_data)
                    click.echo(tabulate(print_peer_tor, headers=headers))
                    headers = ['port', 'state', 'ipv4', 'ipv6']
                    click.echo(tabulate(print_data, headers=headers))

                    sys.exit(CONFIG_SUCCESSFUL)

            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    else:

        port_status_dict = {}
        port_status_dict["MUX_CABLE"] = {}
        port_status_dict["MUX_CABLE"]["PEER_TOR"] = {}
        peer_switch_value = None

        switch_name = get_switch_name(per_npu_configdb[asic_start_idx])
        if asic_start_idx is not None:
            peer_switch_value = get_value_for_key_in_config_tbl(
                per_npu_configdb[asic_start_idx], switch_name, "address_ipv4", "PEER_SWITCH")
            port_status_dict["MUX_CABLE"]["PEER_TOR"] = peer_switch_value
        if json_output:
            port_status_dict["MUX_CABLE"]["PORTS"] = {}
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for port in port_mux_tbl_keys[asic_id]:
                    create_json_dump_per_port_config(port_status_dict, per_npu_configdb, asic_id, port)

            click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
        else:
            print_data = []
            print_peer_tor = []
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for port in port_mux_tbl_keys[asic_id]:
                    create_table_dump_per_port_config(print_data, per_npu_configdb, asic_id, port)

            headers = ['SWITCH_NAME', 'PEER_TOR']
            peer_tor_data = []
            peer_tor_data.append(switch_name)
            peer_tor_data.append(peer_switch_value)
            print_peer_tor.append(peer_tor_data)
            click.echo(tabulate(print_peer_tor, headers=headers))
            headers = ['port', 'state', 'ipv4', 'ipv6']
            click.echo(tabulate(print_data, headers=headers))

        sys.exit(CONFIG_SUCCESSFUL)
