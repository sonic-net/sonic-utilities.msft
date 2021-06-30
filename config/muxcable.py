import json
import os
import sys

import click
import re
import utilities_common.cli as clicommon
from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate
from utilities_common import platform_sfputil_helper

platform_sfputil = None

REDIS_TIMEOUT_MSECS = 0

CONFIG_SUCCESSFUL = 0
CONFIG_FAIL = 1

VENDOR_NAME = "Credo"
VENDOR_MODEL_REGEX = re.compile(r"CAC\w{3}321P2P\w{2}MS")

# Helper functions

def get_value_for_key_in_dict(mdict, port, key, table_name):
    value = mdict.get(key, None)
    if value is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table_name))
        sys.exit(CONFIG_FAIL)
    return value

#
# 'muxcable' command ("config muxcable")
#


def get_value_for_key_in_config_tbl(config_db, port, key, table):
    info_dict = {}
    info_dict = config_db.get_entry(table, port)
    if info_dict is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table))
        sys.exit(CONFIG_FAIL)

    value = get_value_for_key_in_dict(info_dict, port, key, table)

    return value


@click.group(name='muxcable', cls=clicommon.AliasedGroup)
def muxcable():
    """SONiC command line - 'show muxcable' command"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(CONFIG_FAIL)

    global platform_sfputil
    # Load platform-specific sfputil class
    platform_sfputil_helper.load_platform_sfputil()

    # Load port info
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings()

    platform_sfputil = platform_sfputil_helper.platform_sfputil


def lookup_statedb_and_update_configdb(per_npu_statedb, config_db, port, state_cfg_val, port_status_dict):

    muxcable_statedb_dict = per_npu_statedb.get_all(per_npu_statedb.STATE_DB, 'MUX_CABLE_TABLE|{}'.format(port))
    configdb_state = get_value_for_key_in_config_tbl(config_db, port, "state", "MUX_CABLE")
    ipv4_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv4", "MUX_CABLE")
    ipv6_value = get_value_for_key_in_config_tbl(config_db, port, "server_ipv6", "MUX_CABLE")

    state = get_value_for_key_in_dict(muxcable_statedb_dict, port, "state", "MUX_CABLE_TABLE")

    if str(state_cfg_val) == str(configdb_state):
        port_status_dict[port] = 'OK'
    else:
        config_db.set_entry("MUX_CABLE", port, {"state": state_cfg_val,
                                                "server_ipv4": ipv4_value, "server_ipv6": ipv6_value})
        if str(state_cfg_val) == 'active' and str(state) != 'active':
            port_status_dict[port] = 'INPROGRESS'
        else:
            port_status_dict[port] = 'OK'


# 'muxcable' command ("config muxcable mode <port|all> active|auto")
@muxcable.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["active", "auto", "manual"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.option('--json', 'json_output', required=False, is_flag=True, type=click.BOOL)
@clicommon.pass_db
def mode(db, state, port, json_output):
    """Config muxcable mode"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    port_table_keys = {}
    y_cable_asic_table_keys = {}
    per_npu_configdb = {}
    per_npu_statedb = {}
    mux_tbl_cfg_db = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_configdb[asic_id] = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        per_npu_configdb[asic_id].connect()
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        mux_tbl_cfg_db[asic_id] = per_npu_configdb[asic_id].get_table("MUX_CABLE")

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')

    if port is not None and port != "all":

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

        if per_npu_statedb[asic_index] is not None:
            y_cable_asic_table_keys = port_table_keys[asic_index]
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            if logical_key in y_cable_asic_table_keys:
                port_status_dict = {}
                lookup_statedb_and_update_configdb(
                    per_npu_statedb[asic_index], per_npu_configdb[asic_index], port, state, port_status_dict)

                if json_output:
                    click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
                else:
                    headers = ['port', 'state']
                    data = sorted([(k, v) for k, v in port_status_dict.items()])
                    click.echo(tabulate(data, headers=headers))

                sys.exit(CONFIG_SUCCESSFUL)

            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        port_status_dict = {}
        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            for key in port_table_keys[asic_id]:
                logical_port = key.split("|")[1]
                lookup_statedb_and_update_configdb(
                    per_npu_statedb[asic_id], per_npu_configdb[asic_id], logical_port, state, port_status_dict)

            if json_output:
                click.echo("{}".format(json.dumps(port_status_dict, indent=4)))
            else:
                data = sorted([(k, v) for k, v in port_status_dict.items()])

                headers = ['port', 'state']
                click.echo(tabulate(data, headers=headers))

        sys.exit(CONFIG_SUCCESSFUL)


@muxcable.group(cls=clicommon.AbbreviationGroup)
def prbs():
    """Enable/disable PRBS mode on a port"""
    pass


@prbs.command()
@click.argument('port', required=True, default=None, type=click.INT)
@click.argument('target', required=True, default=None, type=click.INT)
@click.argument('mode_value', required=True, default=None, type=click.INT)
@click.argument('lane_map', required=True, default=None, type=click.INT)
def enable(port, target, mode_value, lane_map):
    """Enable PRBS mode on a port"""

    import sonic_y_cable.y_cable
    res = sonic_y_cable.y_cable.enable_prbs_mode(port, target, mode_value, lane_map)
    if res != True:
        click.echo("PRBS config unsuccesful")
        sys.exit(CONFIG_FAIL)
    click.echo("PRBS config sucessful")
    sys.exit(CONFIG_SUCCESSFUL)


@prbs.command()
@click.argument('port', required=True, default=None, type=click.INT)
@click.argument('target', required=True, default=None, type=click.INT)
def disable(port, target):
    """Disable PRBS mode on a port"""

    import sonic_y_cable.y_cable
    res = sonic_y_cable.y_cable.disable_prbs_mode(port, target)
    if res != True:
        click.echo("PRBS disable unsuccesful")
        sys.exit(CONFIG_FAIL)
    click.echo("PRBS disable sucessful")
    sys.exit(CONFIG_SUCCESSFUL)


@muxcable.group(cls=clicommon.AbbreviationGroup)
def loopback():
    """Enable/disable loopback mode on a port"""
    pass


@loopback.command()
@click.argument('port', required=True, default=None, type=click.INT)
@click.argument('target', required=True, default=None, type=click.INT)
@click.argument('lane_map', required=True, default=None, type=click.INT)
def enable(port, target, lane_map):
    """Enable loopback mode on a port"""

    import sonic_y_cable.y_cable
    res = sonic_y_cable.y_cable.enable_loopback_mode(port, target, lane_map)
    if res != True:
        click.echo("loopback config unsuccesful")
        sys.exit(CONFIG_FAIL)
    click.echo("loopback config sucessful")
    sys.exit(CONFIG_SUCCESSFUL)


@loopback.command()
@click.argument('port', required=True, default=None, type=click.INT)
@click.argument('target', required=True, default=None, type=click.INT)
def disable(port, target):
    """Disable loopback mode on a port"""

    import sonic_y_cable.y_cable
    res = sonic_y_cable.y_cable.disable_loopback_mode(port, target)
    if res != True:
        click.echo("loopback disable unsuccesful")
        sys.exit(CONFIG_FAIL)
    click.echo("loopback disable sucessful")
    sys.exit(CONFIG_SUCCESSFUL)


@muxcable.group(cls=clicommon.AbbreviationGroup)
def hwmode():
    """Configure muxcable hardware directly"""
    pass


@hwmode.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["active", "standby"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def state(db, state, port):
    """Configure the muxcable mux state {active/standby}"""

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

    if port is not None and port != "all":
        click.confirm(('Muxcable at port {} will be changed to {} state. Continue?'.format(port, state)), abort=True)
        logical_port_list = platform_sfputil_helper.get_logical_list()
        if port not in logical_port_list:
            click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
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
                    sys.exit(CONFIG_FAIL)

        if platform_sfputil is not None:
            physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

        if not isinstance(physical_port_list, list):
            click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
            sys.exit(CONFIG_FAIL)
        if len(physical_port_list) != 1:
            click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
                ", ".join(physical_port_list), port))
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
            sys.exit(CONFIG_FAIL)

        physical_port = physical_port_list[0]

        logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

        logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

        """ This check is required for checking whether or not this logical port is the one which is 
        actually mapped to physical port and by convention it is always the first port.
        TODO: this should be removed with more logic to check which logical port maps to actual physical port
        being used"""

        if port != logical_port_list_per_port[0]:
            click.echo("ERR: This logical Port {} is not on a muxcable".format(port))
            sys.exit(CONFIG_FAIL)

        import sonic_y_cable.y_cable
        read_side = sonic_y_cable.y_cable.check_read_side(physical_port)
        if read_side == False or read_side == -1:
            click.echo(("ERR: Unable to get read_side for the cable port {}".format(port)))
            sys.exit(CONFIG_FAIL)

        mux_direction = sonic_y_cable.y_cable.check_mux_direction(physical_port)
        if mux_direction == False or mux_direction == -1:
            click.echo(("ERR: Unable to get mux direction for the cable port {}".format(port)))
            sys.exit(CONFIG_FAIL)

        if int(read_side) == 1:
            if state == "active":
                res = sonic_y_cable.y_cable.toggle_mux_to_torA(physical_port)
            elif state == "standby":
                res = sonic_y_cable.y_cable.toggle_mux_to_torB(physical_port)
            click.echo("Success in toggling port {} to {}".format(port, state))
        elif int(read_side) == 2:
            if state == "active":
                res = sonic_y_cable.y_cable.toggle_mux_to_torB(physical_port)
            elif state == "standby":
                res = sonic_y_cable.y_cable.toggle_mux_to_torA(physical_port)
            click.echo("Success in toggling port {} to {}".format(port, state))

        if res == False:
            click.echo("ERR: Unable to toggle port {} to {}".format(port, state))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        click.confirm(('Muxcables at all ports will be changed to {} state. Continue?'.format(state)), abort=True)
        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc = True
        for port in logical_port_list:
            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

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

            if not isinstance(physical_port_list, list):
                click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
                continue

            if len(physical_port_list) != 1:
                click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
                    ", ".join(physical_port_list), port))
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
                click.echo(("ERR: Unable to get read side for the cable port {}".format(port)))
                rc = False
                continue

            mux_direction = sonic_y_cable.y_cable.check_mux_direction(physical_port)
            if mux_direction == False or mux_direction == -1:
                click.echo(("ERR: Unable to get mux direction for the cable port {}".format(port)))
                rc = False
                continue

            if int(read_side) == 1:
                if state == "active":
                    res = sonic_y_cable.y_cable.toggle_mux_to_torA(physical_port)
                elif state == "standby":
                    res = sonic_y_cable.y_cable.toggle_mux_to_torB(physical_port)
                click.echo("Success in toggling port {} to {}".format(port, state))
            elif int(read_side) == 2:
                if state == "active":
                    res = sonic_y_cable.y_cable.toggle_mux_to_torB(physical_port)
                elif state == "standby":
                    res = sonic_y_cable.y_cable.toggle_mux_to_torA(physical_port)
                click.echo("Success in toggling port {} to {}".format(port, state))

            if res == False:
                rc = False
                click.echo("ERR: Unable to toggle port {} to {}".format(port, state))

        if rc == False:
            click.echo("ERR: Unable to toggle one or more ports to {}".format(state))
            sys.exit(CONFIG_FAIL)


@hwmode.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["auto", "manual"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def setswitchmode(db, state, port):
    """Configure the muxcable mux switching mode {auto/manual}"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    per_npu_statedb = {}
    transceiver_dict = {}

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

    if port is not None and port != "all":
        click.confirm(('Muxcable at port {} will be changed to {} switching mode. Continue?'.format(port, state)), abort=True)
        logical_port_list = platform_sfputil_helper.get_logical_list()
        if port not in logical_port_list:
            click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
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
                    sys.exit(CONFIG_FAIL)

        if platform_sfputil is not None:
            physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

        if not isinstance(physical_port_list, list):
            click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
            sys.exit(CONFIG_FAIL)
        if len(physical_port_list) != 1:
            click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
                ", ".join(physical_port_list), port))
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
            sys.exit(CONFIG_FAIL)

        physical_port = physical_port_list[0]

        logical_port_list_for_physical_port = platform_sfputil_helper.get_physical_to_logical()

        logical_port_list_per_port = logical_port_list_for_physical_port.get(physical_port, None)

        """ This check is required for checking whether or not this logical port is the one which is
        actually mapped to physical port and by convention it is always the first port.
        TODO: this should be removed with more logic to check which logical port maps to actual physical port
        being used"""

        if port != logical_port_list_per_port[0]:
            click.echo("ERR: This logical Port {} is not on a muxcable".format(port))
            sys.exit(CONFIG_FAIL)

        if state == "auto":
            mode = sonic_y_cable.y_cable.SWITCHING_MODE_AUTO
        elif state == "manual":
            mode = sonic_y_cable.y_cable.SWITCHING_MODE_MANUAL
        import sonic_y_cable.y_cable
        result = sonic_y_cable.y_cable.set_switching_mode(physical_port, mode)
        if result == False:
            click.echo(("ERR: Unable to set switching mode for the cable port {}".format(port)))
            sys.exit(CONFIG_FAIL)

        click.echo("Success in switching mode on port {} to {}".format(port, state))

    elif port == "all" and port is not None:

        click.confirm(('Muxcable at port {} will be changed to {} switching mode. Continue?'.format(port, state)), abort=True)
        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc = True
        for port in logical_port_list:
            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

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

            if not isinstance(physical_port_list, list):
                click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
                continue

            if len(physical_port_list) != 1:
                click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
                    ", ".join(physical_port_list), port))
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

            if state == "auto":
                mode = sonic_y_cable.y_cable.SWITCHING_MODE_AUTO
            elif state == "manual":
                mode = sonic_y_cable.y_cable.SWITCHING_MODE_MANUAL
            import sonic_y_cable.y_cable
            result = sonic_y_cable.y_cable.set_switching_mode(physical_port, mode)
            if result == False:
                rc = False
                click.echo("ERR: Unable to set switching mode on port {} to {}".format(port, state))

            click.echo("Success in switching mode on port {} to {}".format(port, state))

        if rc == False:
            click.echo("ERR: Unable to set switching mode one or more ports to {}".format(state))
            sys.exit(CONFIG_FAIL)


def get_per_npu_statedb(per_npu_statedb, port_table_keys):

    # Getting all front asic namespace and correspding config and state DB connector

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        # replace these with correct macros
        per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        per_npu_statedb[asic_id].connect(per_npu_statedb[asic_id].STATE_DB)

        port_table_keys[asic_id] = per_npu_statedb[asic_id].keys(
            per_npu_statedb[asic_id].STATE_DB, 'MUX_CABLE_TABLE|*')


def get_physical_port_list(port):

    physical_port_list = []
    if platform_sfputil is not None:
        physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

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

    if not isinstance(physical_port_list, list):
        click.echo(("ERR: Unable to locate physical port information for {}".format(port)))
        sys.exit(CONFIG_FAIL)

    if len(physical_port_list) != 1:
        click.echo("ERR: Found multiple physical ports ({}) associated with {}".format(
            ", ".join(physical_port_list), port))
        sys.exit(CONFIG_FAIL)

    return (physical_port_list, asic_index)


def perform_download_firmware(physical_port, fwfile, port):
    import sonic_y_cable.y_cable
    result = sonic_y_cable.y_cable.download_firmware(physical_port, fwfile)
    if result == sonic_y_cable.y_cable.FIRMWARE_DOWNLOAD_SUCCESS:
        click.echo("firmware download successful {}".format(port))
        return True
    else:
        click.echo("firmware download failure {}".format(port))
        return False


def perform_activate_firmware(physical_port, port):
    import sonic_y_cable.y_cable
    result = sonic_y_cable.y_cable.activate_firmware(physical_port)
    if result == sonic_y_cable.y_cable.FIRMWARE_ACTIVATE_SUCCESS:
        click.echo("firmware activate successful for {}".format(port))
        return True
    else:
        click.echo("firmware activate failure for {}".format(port))
        return False


def perform_rollback_firmware(physical_port, port):
    import sonic_y_cable.y_cable
    result = sonic_y_cable.y_cable.rollback_firmware(physical_port)
    if result == sonic_y_cable.y_cable.FIRMWARE_ROLLBACK_SUCCESS:
        click.echo("firmware rollback successful {}".format(port))
        return True
    else:
        click.echo("firmware rollback failure {}".format(port))
        return False


@muxcable.group(cls=clicommon.AbbreviationGroup)
def firmware():
    """Configure muxcable firmware command"""
    pass


@firmware.command()
@click.argument('fwfile', metavar='<firmware_file>', required=True)
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def download(db, fwfile, port):
    """Config muxcable firmware download"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    per_npu_statedb = {}
    y_cable_asic_table_keys = {}
    port_table_keys = {}

    get_per_npu_statedb(per_npu_statedb, port_table_keys)

    if port is not None and port != "all":

        physical_port_list = []
        physical_port_list, asic_index = get_physical_port_list(port)
        physical_port = physical_port_list[0]
        if per_npu_statedb[asic_index] is not None:
            y_cable_asic_table_keys = port_table_keys[asic_index]
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            if logical_key in y_cable_asic_table_keys:
                perform_download_firmware(physical_port, fwfile, port)

            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        rc = CONFIG_SUCCESSFUL
        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            for key in port_table_keys[asic_id]:
                port = key.split("|")[1]

                physical_port_list = []
                (physical_port_list, asic_index) = get_physical_port_list(port)

                physical_port = physical_port_list[0]

                status = perform_download_firmware(physical_port, fwfile, port)

                if status is not True:
                    rc = CONFIG_FAIL

        sys.exit(rc)


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def activate(db, port):
    """Config muxcable firmware activate"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    per_npu_statedb = {}
    y_cable_asic_table_keys = {}
    port_table_keys = {}

    get_per_npu_statedb(per_npu_statedb, port_table_keys)

    if port is not None and port != "all":

        physical_port_list = []
        (physical_port_list, asic_index) = get_physical_port_list(port)
        physical_port = physical_port_list[0]
        if per_npu_statedb[asic_index] is not None:
            y_cable_asic_table_keys = port_table_keys[asic_index]
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            if logical_key in y_cable_asic_table_keys:
                perform_activate_firmware(physical_port, port)

            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        rc = CONFIG_SUCCESSFUL
        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            for key in port_table_keys[asic_id]:
                port = key.split("|")[1]

                physical_port_list = []

                (physical_port_list, asic_index) = get_physical_port_list(port)
                physical_port = physical_port_list[0]
                status = perform_activate_firmware(physical_port, port)

                if status is not True:
                    rc = CONFIG_FAIL

        sys.exit(rc)


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def rollback(db, port):
    """Config muxcable firmware rollback"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    port_table_keys = {}
    y_cable_asic_table_keys = {}
    per_npu_statedb = {}

    get_per_npu_statedb(per_npu_statedb, port_table_keys)

    if port is not None and port != "all":

        physical_port_list = []
        (physical_port_list, asic_index) = get_physical_port_list(port)
        physical_port = physical_port_list[0]
        if per_npu_statedb[asic_index] is not None:
            y_cable_asic_table_keys = port_table_keys[asic_index]
            logical_key = "MUX_CABLE_TABLE|{}".format(port)
            if logical_key in y_cable_asic_table_keys:
                perform_rollback_firmware(physical_port, port)

            else:
                click.echo("this is not a valid port present on mux_cable".format(port))
                sys.exit(CONFIG_FAIL)
        else:
            click.echo("there is not a valid asic table for this asic_index".format(asic_index))
            sys.exit(CONFIG_FAIL)

    elif port == "all" and port is not None:

        rc = CONFIG_SUCCESSFUL
        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            for key in port_table_keys[asic_id]:
                port = key.split("|")[1]

                physical_port_list = []
                (physical_port_list, asic_index) = get_physical_port_list(port)
                physical_port = physical_port_list[0]
                status = perform_rollback_firmware(physical_port, port)

                if status is not True:
                    rc = CONFIG_FAIL

        sys.exit(rc)
