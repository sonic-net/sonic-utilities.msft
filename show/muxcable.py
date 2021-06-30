import json
import os
import sys

import click
import re
import utilities_common.cli as clicommon
from natsort import natsorted
from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from swsscommon import swsscommon
from tabulate import tabulate
from utilities_common import platform_sfputil_helper

platform_sfputil = None

REDIS_TIMEOUT_MSECS = 0

CONFIG_SUCCESSFUL = 0
CONFIG_FAIL = 1
EXIT_FAIL = 1
EXIT_SUCCESS = 0
STATUS_FAIL = 1
STATUS_SUCCESSFUL = 0

VENDOR_NAME = "Credo"
VENDOR_MODEL_REGEX = re.compile(r"CAC\w{3}321P2P\w{2}MS")

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

    switch_name = get_value_for_key_in_dict(info_dict, "localhost", "peer_switch", "DEVICE_METADATA")
    if switch_name is not None:
        return switch_name
    else:
        click.echo("could not retreive switch name")
        sys.exit(STATUS_FAIL)


def create_json_dump_per_port_status(port_status_dict, muxcable_info_dict, muxcable_health_dict, asic_index, port):

    status_value = get_value_for_key_in_dict(muxcable_info_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    port_status_dict["MUX_CABLE"][port] = {}
    port_status_dict["MUX_CABLE"][port]["STATUS"] = status_value
    health_value = get_value_for_key_in_dict(muxcable_health_dict[asic_index], port, "state", "MUX_LINKMGR_TABLE")
    port_status_dict["MUX_CABLE"][port]["HEALTH"] = health_value


def create_table_dump_per_port_status(print_data, muxcable_info_dict, muxcable_health_dict, asic_index, port):

    print_port_data = []

    status_value = get_value_for_key_in_dict(muxcable_info_dict[asic_index], port, "state", "MUX_CABLE_TABLE")
    #status_value = get_value_for_key_in_tbl(y_cable_asic_table, port, "status")
    health_value = get_value_for_key_in_dict(muxcable_health_dict[asic_index], port, "state", "MUX_LINKMGR_TABLE")
    print_port_data.append(port)
    print_port_data.append(status_value)
    print_port_data.append(health_value)
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
@clicommon.pass_db
def status(db, port, json_output):
    """Show muxcable status information"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    port_table_keys = {}
    port_health_table_keys = {}
    per_npu_statedb = {}
    muxcable_info_dict = {}
    muxcable_health_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')
        port_health_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_LINKMGR_TABLE|*')

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
        muxcable_health_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'MUX_LINKMGR_TABLE|{}'.format(port))
        if muxcable_info_dict[asic_index] is not None:
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            logical_health_key = "MUX_LINKMGR_TABLE|{}".format(port)
            if logical_key in port_table_keys[asic_index] and logical_health_key in port_health_table_keys[asic_index]:

                if json_output:
                    port_status_dict = {}
                    port_status_dict["MUX_CABLE"] = {}

                    create_json_dump_per_port_status(port_status_dict, muxcable_info_dict,
                                                     muxcable_health_dict, asic_index, port)

                    click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
                    sys.exit(STATUS_SUCCESSFUL)
                else:
                    print_data = []

                    create_table_dump_per_port_status(print_data, muxcable_info_dict,
                                                      muxcable_health_dict, asic_index, port)

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
                for key in natsorted(port_table_keys[asic_id]):
                    port = key.split("|")[1]
                    muxcable_info_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
                    muxcable_health_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_LINKMGR_TABLE|{}'.format(port))
                    create_json_dump_per_port_status(port_status_dict, muxcable_info_dict,
                                                     muxcable_health_dict, asic_id, port)

            click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
        else:
            print_data = []
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for key in natsorted(port_table_keys[asic_id]):
                    port = key.split("|")[1]
                    muxcable_health_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_LINKMGR_TABLE|{}'.format(port))
                    muxcable_info_dict[asic_id] = per_npu_statedb[asic_id].get_all(
                        per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))

                    create_table_dump_per_port_status(print_data, muxcable_info_dict,
                                                      muxcable_health_dict, asic_id, port)

            headers = ['PORT', 'STATUS', 'HEALTH']
            click.echo(tabulate(print_data, headers=headers))

        sys.exit(STATUS_SUCCESSFUL)


@muxcable.command()
@click.argument('port', required=False, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def config(db, port, json_output):
    """Show muxcable config information"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

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
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=False, namespace=namespace)
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
                for port in natsorted(port_mux_tbl_keys[asic_id]):
                    create_json_dump_per_port_config(port_status_dict, per_npu_configdb, asic_id, port)

            click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
        else:
            print_data = []
            print_peer_tor = []
            for namespace in namespaces:
                asic_id = multi_asic.get_asic_index_from_namespace(namespace)
                for port in natsorted(port_mux_tbl_keys[asic_id]):
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


@muxcable.command()
@click.argument('port', required=True, default=None, type=click.INT)
@click.argument('target', required=True, default=None, type=click.INT)
def berinfo(port, target):
    """Show muxcable BER (bit error rate) information"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(EXIT_FAIL)
    import sonic_y_cable.y_cable
    res = sonic_y_cable.y_cable.get_ber_info(port, target)
    if res == False or res == -1:
        click.echo("Unable to fetch ber info")
        sys.exit(EXIT_FAIL)
    headers = ['Lane1', 'Lane2', 'Lane3', 'Lane4']
    lane_data = []
    lane_data.append(res)
    click.echo(tabulate(lane_data, headers=headers))
    sys.exit(EXIT_SUCCESS)


@muxcable.command()
@click.argument('port', required=True, default=None, type=click.INT)
@click.argument('target', required=True, default=None, type=click.INT)
def eyeinfo(port, target):
    """Show muxcable eye information in mv"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(EXIT_FAIL)
    import sonic_y_cable.y_cable
    res = sonic_y_cable.y_cable.get_eye_info(port, target)
    if res == False or res == -1:
        click.echo("Unable to fetch eye info")
        sys.exit(EXIT_FAIL)
    headers = ['Lane1', 'Lane2', 'Lane3', 'Lane4']
    lane_data = []
    lane_data.append(res)
    click.echo(tabulate(lane_data, headers=headers))
    sys.exit(EXIT_SUCCESS)


@muxcable.command()
@click.argument('port', required=True, default=None)
@clicommon.pass_db
def cableinfo(db, port):
    """Show muxcable cable information"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    if platform_sfputil is not None:
        physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

    if not isinstance(physical_port_list, list):
        click.echo("ERR: Unable to get a port on muxcable port")
        sys.exit(EXIT_FAIL)
        if len(physical_port_list) != 1:
            click.echo("ERR: Unable to get a single port on muxcable")
            sys.exit(EXIT_FAIL)

    physical_port = physical_port_list[0]
    import sonic_y_cable.y_cable
    part_num = sonic_y_cable.y_cable.get_part_number(physical_port)
    if part_num == False or part_num == -1:
        click.echo("ERR: Unable to get cable info part number")
        sys.exit(EXIT_FAIL)
    vendor = sonic_y_cable.y_cable.get_vendor(physical_port)
    if vendor == False or vendor == -1:
        click.echo("ERR: Unable to get cable info vendor name")
        sys.exit(EXIT_FAIL)
    headers = ['Vendor', 'Model']

    body = [[vendor, part_num]]
    click.echo(tabulate(body, headers=headers))


@muxcable.group(cls=clicommon.AbbreviationGroup)
def hwmode():
    """Shows the muxcable hardware information directly"""
    pass


@hwmode.command()
@click.argument('port', metavar='<port_name>', required=False, default=None)
@clicommon.pass_db
def muxdirection(db, port):
    """Shows the current direction of the muxcable {active/standy}"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    per_npu_statedb = {}
    transceiver_table_keys = {}
    transceiver_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        transceiver_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'TRANSCEIVER_INFO|*')

    if port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()
        if port not in logical_port_list:
            click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
            sys.exit(EXIT_FAIL)

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
                sys.exit(CONFIG_FAIL)

        transceiver_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'TRANSCEIVER_INFO|{}'.format(port))

        vendor_value = get_value_for_key_in_dict(transceiver_dict[asic_index], port, "manufacturer", "TRANSCEIVER_INFO")
        model_value = get_value_for_key_in_dict(transceiver_dict[asic_index], port, "model", "TRANSCEIVER_INFO")

        """ This check is required for checking whether or not this port is connected to a Y cable
        or not. The check gives a way to differentiate between non Y cable ports and Y cable ports.
        TODO: this should be removed once their is support for multiple vendors on Y cable"""

        if vendor_value != VENDOR_NAME or not re.match(VENDOR_MODEL_REGEX, model_value):
            click.echo("ERR: Got invalid vendor value and model for port {}".format(port))
            sys.exit(EXIT_FAIL)

        if platform_sfputil is not None:
            physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

        if not isinstance(physical_port_list, list):
            click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
            sys.exit(EXIT_FAIL)
        if len(physical_port_list) != 1:
            click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
                ", ".join(physical_port_list), port))
            sys.exit(EXIT_FAIL)

        physical_port = physical_port_list[0]

        logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

        logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

        """ This check is required for checking whether or not this logical port is the one which is
        actually mapped to physical port and by convention it is always the first port.
        TODO: this should be removed with more logic to check which logical port maps to actual physical port
        being used"""

        if port != logical_port_list_per_port[0]:
            click.echo("ERR: This logical Port {} is not on a muxcable".format(port))
            sys.exit(EXIT_FAIL)

        import sonic_y_cable.y_cable
        read_side = sonic_y_cable.y_cable.check_read_side(physical_port)
        if read_side == False or read_side == -1:
            click.echo(("ERR: Unable to get read_side for the cable port {}".format(port)))
            sys.exit(EXIT_FAIL)

        mux_direction = sonic_y_cable.y_cable.check_mux_direction(physical_port)
        if mux_direction == False or mux_direction == -1:
            click.echo(("ERR: Unable to get mux direction for the cable port {}".format(port)))
            sys.exit(EXIT_FAIL)

        if int(read_side) == 1:
            if mux_direction == 1:
                state = "active"
            elif mux_direction == 2:
                state = "standby"
        elif int(read_side) == 2:
            if mux_direction == 1:
                state = "standby"
            elif mux_direction == 2:
                state = "active"
        else:
            click.echo(("ERR: Unable to get mux direction, port {}".format(port)))
            state = "unknown"
        headers = ['Port', 'Direction']

        body = [[port, state]]
        click.echo(tabulate(body, headers=headers))

    else:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc = True
        body = []
        for port in logical_port_list:

            temp_list = []
            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            asic_index = None
            if platform_sfputil is not None:
                asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
            if asic_index is None:
                # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
                # is fully mocked
                import sonic_platform_base.sonic_sfp.sfputilhelper
                asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
                if asic_index is None:
                    continue

            transceiver_dict[asic_index] = per_npu_statedb[asic_index].get_all(
                per_npu_statedb[asic_index].STATE_DB, 'TRANSCEIVER_INFO|{}'.format(port))
            vendor_value = transceiver_dict[asic_index].get("manufacturer", None)
            model_value = transceiver_dict[asic_index].get("model", None)

            """ This check is required for checking whether or not this port is connected to a Y cable
            or not. The check gives a way to differentiate between non Y cable ports and Y cable ports.
            TODO: this should be removed once their is support for multiple vendors on Y cable"""

            if vendor_value != VENDOR_NAME or not re.match(VENDOR_MODEL_REGEX, model_value):
                continue

            physical_port = physical_port_list[0]
            logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

            logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

            """ This check is required for checking whether or not this logical port is the one which is
            actually mapped to physical port and by convention it is always the first port.
            TODO: this should be removed with more logic to check which logical port maps to actual physical port
            being used"""

            if port != logical_port_list_per_port[0]:
                continue

            import sonic_y_cable.y_cable
            read_side = sonic_y_cable.y_cable.check_read_side(physical_port)
            if read_side == False or read_side == -1:
                rc = False
                temp_list.append(port)
                temp_list.append("unknown")
                body.append(temp_list)
                continue

            mux_direction = sonic_y_cable.y_cable.check_mux_direction(physical_port)
            if mux_direction == False or mux_direction == -1:
                rc = False
                temp_list.append(port)
                temp_list.append("unknown")
                body.append(temp_list)
                continue

            if int(read_side) == 1:
                if mux_direction == 1:
                    state = "active"
                elif mux_direction == 2:
                    state = "standby"
            elif int(read_side) == 2:
                if mux_direction == 1:
                    state = "standby"
                elif mux_direction == 2:
                    state = "active"
            else:
                rc = False
                temp_list.append(port)
                temp_list.append("unknown")
                body.append(temp_list)
                continue
            temp_list.append(port)
            temp_list.append(state)
            body.append(temp_list)

        headers = ['Port', 'Direction']

        click.echo(tabulate(body, headers=headers))
        if rc == False:
            sys.exit(EXIT_FAIL)


@hwmode.command()
@click.argument('port', metavar='<port_name>', required=False, default=None)
def switchmode(db, port):
    """Shows the current switching mode of the muxcable {auto/manual}"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    per_npu_statedb = {}
    transceiver_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

    if port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()
        if port not in logical_port_list:
            click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
            sys.exit(EXIT_FAIL)

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
        if asic_index is None:
            # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
            # is fully mocked
            import sonic_platform_base.sonic_sfp.sfputilhelper
            asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
            if asic_index is None:
                click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))
                sys.exit(CONFIG_FAIL)

        transceiver_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'TRANSCEIVER_INFO|{}'.format(port))

        vendor_value = get_value_for_key_in_dict(transceiver_dict[asic_index], port, "manufacturer", "TRANSCEIVER_INFO")
        model_value = get_value_for_key_in_dict(transceiver_dict[asic_index], port, "model", "TRANSCEIVER_INFO")

        """ This check is required for checking whether or not this port is connected to a Y cable
        or not. The check gives a way to differentiate between non Y cable ports and Y cable ports.
        TODO: this should be removed once their is support for multiple vendors on Y cable"""

        if vendor_value != VENDOR_NAME or not re.match(VENDOR_MODEL_REGEX, model_value):
            click.echo("ERR: Got invalid vendor value and model for port {}".format(port))
            sys.exit(EXIT_FAIL)

        if platform_sfputil is not None:
            physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

        if not isinstance(physical_port_list, list):
            click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
            sys.exit(EXIT_FAIL)
        if len(physical_port_list) != 1:
            click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
                ", ".join(physical_port_list), port))
            sys.exit(EXIT_FAIL)

        physical_port = physical_port_list[0]

        logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

        logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

        """ This check is required for checking whether or not this logical port is the one which is
        actually mapped to physical port and by convention it is always the first port.
        TODO: this should be removed with more logic to check which logical port maps to actual physical port
        being used"""

        if port != logical_port_list_per_port[0]:
            click.echo("ERR: This logical Port {} is not on a muxcable".format(port))
            sys.exit(EXIT_FAIL)

        import sonic_y_cable.y_cable
        switching_mode = sonic_y_cable.y_cable.get_switching_mode(physical_port)
        if switching_mode == -1:
            click.echo(("ERR: Unable to get switching mode for the cable port {}".format(port)))
            sys.exit(EXIT_FAIL)

        if switching_mode == sonic_y_cable.y_cable.SWITCHING_MODE_AUTO:
            state = "auto"
        elif switching_mode == sonic_y_cable.y_cable.SWITCHING_MODE_MANUAL:
            state = "manual"
        else:
            click.echo(("ERR: Unable to get switching state mode, port {}".format(port)))
            state = "unknown"
        headers = ['Port', 'Switching']

        body = [[port, state]]
        click.echo(tabulate(body, headers=headers))

    else:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc = True
        body = []
        for port in logical_port_list:

            temp_list = []
            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
                continue

            asic_index = None
            if platform_sfputil is not None:
                asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
            if asic_index is None:
                # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
                # is fully mocked
                import sonic_platform_base.sonic_sfp.sfputilhelper
                asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
                if asic_index is None:
                    continue

            transceiver_dict[asic_index] = per_npu_statedb[asic_index].get_all(
                per_npu_statedb[asic_index].STATE_DB, 'TRANSCEIVER_INFO|{}'.format(port))
            vendor_value = transceiver_dict[asic_index].get("manufacturer", None)
            model_value = transceiver_dict[asic_index].get("model", None)

            """ This check is required for checking whether or not this port is connected to a Y cable
            or not. The check gives a way to differentiate between non Y cable ports and Y cable ports.
            TODO: this should be removed once their is support for multiple vendors on Y cable"""

            if vendor_value != VENDOR_NAME or not re.match(VENDOR_MODEL_REGEX, model_value):
                continue

            physical_port = physical_port_list[0]
            logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

            logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

            """ This check is required for checking whether or not this logical port is the one which is
            actually mapped to physical port and by convention it is always the first port.
            TODO: this should be removed with more logic to check which logical port maps to actual physical port
            being used"""

            if port != logical_port_list_per_port[0]:
                continue

            import sonic_y_cable.y_cable
            switching_mode = sonic_y_cable.y_cable.get_switching_mode(physical_port)
            if switching_mode == -1:
                rc = False
                temp_list.append(port)
                temp_list.append("unknown")
                body.append(temp_list)
                continue

            if switching_mode == sonic_y_cable.y_cable.SWITCHING_MODE_AUTO:
                state = "auto"
            elif switching_mode == sonic_y_cable.y_cable.SWITCHING_MODE_MANUAL:
                state = "manual"
            else:
                rc = False
                temp_list.append(port)
                temp_list.append("unknown")
                body.append(temp_list)
                continue
            temp_list.append(port)
            temp_list.append(state)
            body.append(temp_list)

        headers = ['Port', 'Switching']

        click.echo(tabulate(body, headers=headers))
        if rc == False:
            sys.exit(EXIT_FAIL)


def get_firmware_dict(physical_port, target, side, mux_info_dict):

    import sonic_y_cable.y_cable
    result = sonic_y_cable.y_cable.get_firmware_version(physical_port, target)

    if result is not None and isinstance(result, dict):
        mux_info_dict[("version_{}_active".format(side))] = result.get("version_active", None)
        mux_info_dict[("version_{}_inactive".format(side))] = result.get("version_inactive", None)
        mux_info_dict[("version_{}_next".format(side))] = result.get("version_next", None)

    else:
        mux_info_dict[("version_{}_active".format(side))] = "N/A"
        mux_info_dict[("version_{}_inactive".format(side))] = "N/A"
        mux_info_dict[("version_{}_next".format(side))] = "N/A"


@muxcable.group(cls=clicommon.AbbreviationGroup)
def firmware():
    """Show muxcable firmware command"""
    pass


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--active', 'active', required=False, is_flag=True, type=click.BOOL, help="display the firmware version of only active bank within MCU's")
@clicommon.pass_db
def version(db, port, active):
    """Show muxcable firmware version"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    port_table_keys = {}
    y_cable_asic_table_keys = {}
    per_npu_statedb = {}
    physical_port_list = []

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_statedb[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')

    if port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        if port not in logical_port_list:
            click.echo(("ERR: Not a valid logical port for muxcable firmware {}".format(port)))
            sys.exit(CONFIG_FAIL)

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
            if asic_index is None:
                # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
                # is fully mocked
                import sonic_platform_base.sonic_sfp.sfputilhelper
                asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
                if asic_index is None:
                    click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))

        if platform_sfputil is not None:
            physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

        if not isinstance(physical_port_list, list):
            click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
            sys.exit(CONFIG_FAIL)

        if len(physical_port_list) != 1:
            click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
                ", ".join(physical_port_list), port))
            sys.exit(CONFIG_FAIL)

        mux_info_dict = {}
        mux_info_active_dict = {}
        physical_port = physical_port_list[0]
        if per_npu_statedb[asic_index] is not None:
            y_cable_asic_table_keys = port_table_keys[asic_index]
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            import sonic_y_cable.y_cable
            read_side = sonic_y_cable.y_cable.check_read_side(physical_port)
            if logical_key in y_cable_asic_table_keys:
                if read_side == 1:
                    get_firmware_dict(physical_port, 1, "self", mux_info_dict)
                    get_firmware_dict(physical_port, 2, "peer", mux_info_dict)
                    get_firmware_dict(physical_port, 0, "nic", mux_info_dict)
                    if active is True:
                        for key in mux_info_dict:
                            if key.endswith("_active"):
                                mux_info_active_dict[key] = mux_info_dict[key]
                        click.echo("{}".format(json.dumps(mux_info_active_dict, indent=4)))
                    else:
                        click.echo("{}".format(json.dumps(mux_info_dict, indent=4)))
                elif read_side == 2:
                    get_firmware_dict(physical_port, 2, "self", mux_info_dict)
                    get_firmware_dict(physical_port, 1, "peer", mux_info_dict)
                    get_firmware_dict(physical_port, 0, "nic", mux_info_dict)
                    if active is True:
                        for key in mux_info_dict:
                            if key.endswith("_active"):
                                mux_info_active_dict[key] = mux_info_dict[key]
                        click.echo("{}".format(json.dumps(mux_info_active_dict, indent=4)))
                    else:
                        click.echo("{}".format(json.dumps(mux_info_dict, indent=4)))
                else:
                    click.echo("Did not get a valid read_side for muxcable".format(port))
                    sys.exit(CONFIG_FAIL)

            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))


@muxcable.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL, help="display the output in json format")
@clicommon.pass_db
def metrics(db, port, json_output):
    """Show muxcable metrics <port>"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    metrics_table_keys = {}
    per_npu_statedb = {}
    metrics_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_statedb[asic_id] = swsscommon.SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        metrics_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_METRICS_TABLE|*')

    if port is not None:

        logical_port_list = platform_sfputil_helper.get_logical_list()

        if port not in logical_port_list:
            click.echo(("ERR: Not a valid logical port for muxcable firmware {}".format(port)))
            sys.exit(CONFIG_FAIL)

        asic_index = None
        if platform_sfputil is not None:
            asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
            if asic_index is None:
                # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
                # is fully mocked
                import sonic_platform_base.sonic_sfp.sfputilhelper
                asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
                if asic_index is None:
                    click.echo("Got invalid asic index for port {}, cant retreive mux status".format(port))

        metrics_dict[asic_index] = per_npu_statedb[asic_index].get_all(
            per_npu_statedb[asic_index].STATE_DB, 'MUX_METRICS_TABLE|{}'.format(port))

        if json_output:
            click.echo("{}".format(json.dumps(metrics_dict[asic_index], indent=4)))
        else:
            print_data = []
            for key, val in metrics_dict[asic_index].items():
                print_port_data = []
                print_port_data.append(port)
                print_port_data.append(key)
                print_port_data.append(val)
                print_data.append(print_port_data)

            headers = ['PORT', 'EVENT', 'TIME']

            click.echo(tabulate(print_data, headers=headers))
