import json
import os
import sys
import time

import click
import re
import utilities_common.cli as clicommon
from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from swsscommon import swsscommon
from tabulate import tabulate
from utilities_common import platform_sfputil_helper

platform_sfputil = None

REDIS_TIMEOUT_MSECS = 0
SELECT_TIMEOUT = 1000

# The empty namespace refers to linux host namespace.
EMPTY_NAMESPACE = ''


CONFIG_SUCCESSFUL = 0
CONFIG_FAIL = 1

VENDOR_NAME = "Credo"
VENDOR_MODEL_REGEX = re.compile(r"CAC\w{3}321P2P\w{2}MS")

# Helper functions

def db_connect(db_name, namespace=EMPTY_NAMESPACE):
    return swsscommon.DBConnector(db_name, REDIS_TIMEOUT_MSECS, True, namespace)

def get_value_for_key_in_dict(mdict, port, key, table_name):
    value = mdict.get(key, None)
    if value is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table_name))
        sys.exit(CONFIG_FAIL)
    return value

def delete_all_keys_in_db_table(db_type, table_name):

    redis_db = {}
    table = {}
    table_keys = {}

    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        redis_db[asic_id] = db_connect(db_type, namespace)
        table[asic_id] = swsscommon.Table(redis_db[asic_id], table_name)
        table_keys[asic_id] = table[asic_id].getKeys()
        for key in table_keys[asic_id]:
            table[asic_id]._del(key)


def update_and_get_response_for_xcvr_cmd(cmd_name, rsp_name, exp_rsp, cmd_table_name, rsp_table_name, port, cmd_timeout_secs, arg=None):

    res_dict = {}
    state_db, appl_db = {}, {}
    firmware_rsp_tbl, firmware_rsp_tbl_keys = {}, {}
    firmware_rsp_sub_tbl = {}
    firmware_cmd_tbl = {}

    CMD_TIMEOUT_SECS = cmd_timeout_secs

    time_start = time.time()

    sel = swsscommon.Select()
    namespaces = multi_asic.get_front_end_namespaces()
    for namespace in namespaces:
        asic_id = multi_asic.get_asic_index_from_namespace(namespace)
        state_db[asic_id] = db_connect("STATE_DB", namespace)
        appl_db[asic_id] = db_connect("APPL_DB", namespace)
        firmware_cmd_tbl[asic_id] = swsscommon.Table(appl_db[asic_id], cmd_table_name)
        firmware_rsp_sub_tbl[asic_id] = swsscommon.SubscriberStateTable(state_db[asic_id], rsp_table_name)
        firmware_rsp_tbl[asic_id] = swsscommon.Table(state_db[asic_id], rsp_table_name)
        firmware_rsp_tbl_keys[asic_id] = firmware_rsp_tbl[asic_id].getKeys()
        for key in firmware_rsp_tbl_keys[asic_id]:
            firmware_rsp_tbl[asic_id]._del(key)
        sel.addSelectable(firmware_rsp_sub_tbl[asic_id])

    rc = CONFIG_FAIL
    res_dict[0] = CONFIG_FAIL
    res_dict[1] = 'unknown'

    logical_port_list = platform_sfputil_helper.get_logical_list()
    if port not in logical_port_list:
        click.echo("ERR: This is not a valid port, valid ports ({})".format(", ".join(logical_port_list)))
        res_dict[0] = rc
        return res_dict

    asic_index = None
    if platform_sfputil is not None:
        asic_index = platform_sfputil_helper.get_asic_id_for_logical_port(port)
    if asic_index is None:
        # TODO this import is only for unit test purposes, and should be removed once sonic_platform_base
        # is fully mocked
        import sonic_platform_base.sonic_sfp.sfputilhelper
        asic_index = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper().get_asic_id_for_logical_port(port)
        if asic_index is None:
            click.echo("Got invalid asic index for port {}, cant perform firmware cmd".format(port))
            res_dict[0] = rc
            return res_dict

    if arg is None:
        cmd_arg = "null"
    else:
        cmd_arg = str(arg)

    fvs = swsscommon.FieldValuePairs([(cmd_name, cmd_arg)])
    firmware_cmd_tbl[asic_index].set(port, fvs)

    # Listen indefinitely for changes to the HW_MUX_CABLE_TABLE in the Application DB's
    while True:
        # Use timeout to prevent ignoring the signals we want to handle
        # in signal_handler() (e.g. SIGTERM for graceful shutdown)

        (state, selectableObj) = sel.select(SELECT_TIMEOUT)

        time_now = time.time()
        time_diff = time_now - time_start
        if time_diff >= CMD_TIMEOUT_SECS:
            return res_dict

        if state == swsscommon.Select.TIMEOUT:
            # Do not flood log when select times out
            continue
        if state != swsscommon.Select.OBJECT:
            click.echo("sel.select() did not  return swsscommon.Select.OBJECT for sonic_y_cable updates")
            continue

        # Get the redisselect object  from selectable object
        redisSelectObj = swsscommon.CastSelectableToRedisSelectObj(
            selectableObj)
        # Get the corresponding namespace from redisselect db connector object
        namespace = redisSelectObj.getDbConnector().getNamespace()
        asic_index = multi_asic.get_asic_index_from_namespace(namespace)

        (port_m, op_m, fvp_m) = firmware_rsp_sub_tbl[asic_index].pop()

        if not port_m:
            click.echo("Did not receive a port response {}".format(port))
            res_dict[1] = 'unknown'
            res_dict[0] = CONFIG_FAIL
            firmware_rsp_tbl[asic_index]._del(port)
            break

        if port_m != port:

            res_dict[1] = 'unknown'
            res_dict[0] = CONFIG_FAIL
            firmware_rsp_tbl[asic_index]._del(port)
            continue

        if fvp_m:

            fvp_dict = dict(fvp_m)
            if rsp_name in fvp_dict:
                # check if xcvrd got a probe command
                result = fvp_dict[rsp_name]


                if result == exp_rsp:
                    res_dict[1] = result
                    res_dict[0] = 0
                else:
                    res_dict[1] = result
                    res_dict[0] = CONFIG_FAIL

                firmware_rsp_tbl[asic_index]._del(port)
                break
            else:
                res_dict[1] = 'unknown'
                res_dict[0] = CONFIG_FAIL
                firmware_rsp_tbl[asic_index]._del(port)
                break
        else:
            res_dict[1] = 'unknown'
            res_dict[0] = CONFIG_FAIL
            firmware_rsp_tbl[asic_index]._del(port)
            break

    delete_all_keys_in_db_table("STATE_DB", rsp_table_name)

    return res_dict

def get_value_for_key_in_config_tbl(config_db, port, key, table):
    info_dict = {}
    info_dict = config_db.get_entry(table, port)
    if info_dict is None:
        click.echo("could not retrieve key {} value for port {} inside table {}".format(key, port, table))
        sys.exit(CONFIG_FAIL)

    value = get_value_for_key_in_dict(info_dict, port, key, table)

    return value

#
# 'muxcable' command ("config muxcable")
#

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
        if (str(state_cfg_val) == 'active' and str(state) != 'active') or (str(state_cfg_val) == 'standby' and str(state) != 'standby'):
            port_status_dict[port] = 'INPROGRESS'
        else:
            port_status_dict[port] = 'OK'


# 'muxcable' command ("config muxcable mode <port|all> active|auto")
@muxcable.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["active", "auto", "manual", "standby"]))
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

    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_DIR_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_DIR_RSP")

    if port is not None and port != "all":
        click.confirm(('Muxcable at port {} will be changed to {} state. Continue?'.format(port, state)), abort=True)

        res_dict = {}
        res_dict [0] = CONFIG_FAIL
        res_dict [1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd("config","result", "True", "XCVRD_CONFIG_HWMODE_DIR_CMD", "XCVRD_CONFIG_HWMODE_DIR_RSP", port, 1, state)

        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_DIR_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_DIR_RSP")

        if rc == 0:
            click.echo("Success in toggling port {} to {}".format(port, state))
        else:
            click.echo("ERR: Unable to toggle port {} to {}".format(port, state))
            sys.exit(CONFIG_FAIL)

    elif port == "all":
        click.confirm(('Muxcable at all ports will be changed to {} state. Continue?'.format(state)), abort=True)

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = 0

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
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

            res_dict = {}
            res_dict [0] = CONFIG_FAIL
            res_dict [1] = 'unknown'

            res_dict = update_and_get_response_for_xcvr_cmd("config","result", "True", "XCVRD_CONFIG_HWMODE_DIR_CMD", "XCVRD_CONFIG_HWMODE_DIR_RSP", port, 1, state)

            rc = res_dict[0]

            delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_DIR_CMD")
            delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_DIR_RSP")

            if rc == 0:
                click.echo("Success in toggling port {} to {}".format(port, state))
            else:
                click.echo("ERR: Unable to toggle port {} to {}".format(port, state))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@hwmode.command()
@click.argument('state', metavar='<operation_status>', required=True, type=click.Choice(["auto", "manual"]))
@click.argument('port', metavar='<port_name>', required=True, default=None)
@clicommon.pass_db
def setswitchmode(db, state, port):
    """Configure the muxcable mux switching mode {auto/manual}"""

    port = platform_sfputil_helper.get_interface_alias(port, db)


    delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_SWMODE_CMD")
    delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_SWMODE_RSP")

    if port is not None and port != "all":
        click.confirm(('Muxcable at port {} will be changed to {} switching mode. Continue?'.format(port, state)), abort=True)

        res_dict = {}
        res_dict [0] = CONFIG_FAIL
        res_dict [1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd("config", "result", "True", "XCVRD_CONFIG_HWMODE_SWMODE_CMD", "XCVRD_CONFIG_HWMODE_SWMODE_RSP", port, 1, state)


        rc = res_dict[0]

        delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_SWMODE_CMD")
        delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_SWMODE_RSP")

        if rc == 0:
            click.echo("Success in switch muxcable mode port {} to {}".format(port, state))
        else:
            click.echo("ERR: Unable to switch muxcable mode port {} to {}".format(port, state))
            sys.exit(CONFIG_FAIL)

    elif port == "all":
        click.confirm(('Muxcable at all ports will be changed to {} switching mode. Continue?'.format(state)), abort=True)

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = 0

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
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

            res_dict = {}
            res_dict [0] = CONFIG_FAIL
            res_dict [1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd("config", "result", "True", "XCVRD_CONFIG_HWMODE_SWMODE_CMD", "XCVRD_CONFIG_HWMODE_SWMODE_RSP", port, 1, state)

            rc = res_dict[0]

            delete_all_keys_in_db_table("APPL_DB", "XCVRD_CONFIG_HWMODE_SWMODE_CMD")
            delete_all_keys_in_db_table("STATE_DB", "XCVRD_CONFIG_HWMODE_SWMODE_RSP")

            if rc == 0:
                click.echo("Success in toggling port {} to {}".format(port, state))
            else:
                click.echo("ERR: Unable to toggle port {} to {}".format(port, state))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


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

    delete_all_keys_in_db_table("STATE_DB", "XCVRD_DOWN_FW_RSP")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_DOWN_FW_CMD")

    if port is not None and port != "all":

        res_dict = {}
        res_dict [0] = CONFIG_FAIL
        res_dict [1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd("download_firmware", "status", "0", "XCVRD_DOWN_FW_CMD", "XCVRD_DOWN_FW_RSP", port, 1000, fwfile)

        rc = res_dict[0]

        delete_all_keys_in_db_table("STATE_DB", "XCVRD_DOWN_FW_RSP")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_DOWN_FW_CMD")

        if rc == 0:
            click.echo("Success in downloading firmware port {} {}".format(port, fwfile))
        else:
            click.echo("ERR: Unable to download firmware port {} {}".format(port, fwfile))
            sys.exit(CONFIG_FAIL)

    elif port == "all":
        click.confirm(('Muxcable at all ports will be changed to {} switching mode. Continue?'.format(state)), abort=True)

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
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

            res_dict = {}

            res_dict [0] = CONFIG_FAIL
            res_dict [1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd("download_firmware", "status", "0", "XCVRD_DOWN_FW_CMD", "XCVRD_DOWN_FW_RSP", port, 1000, fwfile)

            rc = res_dict[0]

            delete_all_keys_in_db_table("STATE_DB", "XCVRD_DOWN_FW_RSP")
            delete_all_keys_in_db_table("APPL_DB", "XCVRD_DOWN_FW_CMD")

            if rc == 0:
                click.echo("Success in downloading firmware port {} {}".format(port, fwfile))
            else:
                click.echo("ERR: Unable to download firmware port {} {}".format(port, fwfile))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('fwfile', metavar='<firmware_file>', required=False, default=None)
@clicommon.pass_db
def activate(db, port, fwfile):
    """Config muxcable firmware activate"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    delete_all_keys_in_db_table("STATE_DB", "XCVRD_ACTI_FW_RSP")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD")

    if port is not None and port != "all":

        res_dict = {}
        res_dict [0] = CONFIG_FAIL
        res_dict [1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd("activate_firmware", "status", "0", "XCVRD_ACTI_FW_CMD", "XCVRD_ACTI_FW_RSP", port, 60, fwfile)

        rc = res_dict[0]

        delete_all_keys_in_db_table("STATE_DB", "XCVRD_ACTI_FW_RSP")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD")

        if rc == 0:
            click.echo("Success in activate firmware port {} fwfile {}".format(port, fwfile))
        else:
            click.echo("ERR: Unable to activate firmware port {} fwfile {}".format(port, fwfile))
            sys.exit(CONFIG_FAIL)

    elif port == "all":

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
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

            res_dict = {}

            res_dict [0] = CONFIG_FAIL
            res_dict [1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd("activate_firmware", "status", "0", "XCVRD_ACTI_FW_CMD", "XCVRD_ACTI_FW_RSP", port, 60, fwfile)

            delete_all_keys_in_db_table("STATE_DB", "XCVRD_ACTI_FW_RSP")
            delete_all_keys_in_db_table("APPL_DB", "XCVRD_ACTI_FW_CMD")

            rc = res_dict[0]

            if rc == 0:
                click.echo("Success in activate firmware port {} fwfile {}".format(port, fwfile))
            else:
                click.echo("ERR: Unable to activate firmware port {} fwfile {}".format(port, fwfile))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)


@firmware.command()
@click.argument('port', metavar='<port_name>', required=True, default=None)
@click.argument('fwfile', metavar='<firmware_file>', required=False, default=None)
@clicommon.pass_db
def rollback(db, port, fwfile):
    """Config muxcable firmware rollback"""

    port = platform_sfputil_helper.get_interface_alias(port, db)

    delete_all_keys_in_db_table("STATE_DB", "XCVRD_ROLL_FW_RSP")
    delete_all_keys_in_db_table("APPL_DB", "XCVRD_ROLL_FW_CMD")

    if port is not None and port != "all":

        res_dict = {}
        res_dict [0] = CONFIG_FAIL
        res_dict [1] = "unknown"
        res_dict = update_and_get_response_for_xcvr_cmd("rollback_firmware", "status", "0", "XCVRD_ROLL_FW_CMD", "XCVRD_ROLL_FW_RSP", port, 60, fwfile)

        delete_all_keys_in_db_table("STATE_DB", "XCVRD_ROLL_FW_RSP")
        delete_all_keys_in_db_table("APPL_DB", "XCVRD_ROLL_FW_CMD")

        rc = res_dict[0]
        if rc == 0:
            click.echo("Success in rollback firmware port {} fwfile {}".format(port, fwfile))
        else:
            click.echo("ERR: Unable to rollback firmware port {} fwfile {}".format(port, fwfile))
            sys.exit(CONFIG_FAIL)

    elif port == "all":

        logical_port_list = platform_sfputil_helper.get_logical_list()

        rc_exit = True

        for port in logical_port_list:

            if platform_sfputil is not None:
                physical_port_list = platform_sfputil_helper.logical_port_name_to_physical_port_list(port)

            if not isinstance(physical_port_list, list):
                continue
            if len(physical_port_list) != 1:
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

            res_dict = {}

            res_dict [0] = CONFIG_FAIL
            res_dict [1] = "unknown"
            res_dict = update_and_get_response_for_xcvr_cmd("rollback_firmware", "status", "0", "XCVRD_ROLL_FW_CMD", "XCVRD_ROLL_FW_RSP", port, 60, fwfile)

            delete_all_keys_in_db_table("STATE_DB", "XCVRD_ROLL_FW_RSP")
            delete_all_keys_in_db_table("APPL_DB", "XCVRD_ROLL_FW_CMD")

            rc = res_dict[0]

            if rc == 0:
                click.echo("Success in rollback firmware port {} fwfile {}".format(port, fwfile))
            else:
                click.echo("ERR: Unable to rollback firmware port {} fwfile {}".format(port, fwfile))
                rc_exit = CONFIG_FAIL

        sys.exit(rc_exit)
