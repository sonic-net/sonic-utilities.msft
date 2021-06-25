#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with SFP transceivers within SONiC
#

import os
import sys
import natsort
import ast

import subprocess
import click
import sonic_platform
import sonic_platform_base.sonic_sfp.sfputilhelper
from swsscommon.swsscommon import SonicV2Connector
from natsort import natsorted
from sonic_py_common import device_info, logger, multi_asic
from tabulate import tabulate

VERSION = '3.0'

SYSLOG_IDENTIFIER = "sfputil"

PLATFORM_JSON = 'platform.json'
PORT_CONFIG_INI = 'port_config.ini'

ERROR_PERMISSIONS = 1
ERROR_CHASSIS_LOAD = 2
ERROR_SFPUTILHELPER_LOAD = 3
ERROR_PORT_CONFIG_LOAD = 4
ERROR_NOT_IMPLEMENTED = 5
ERROR_INVALID_PORT = 6

# TODO: We should share these maps and the formatting functions between sfputil and sfpshow
QSFP_DATA_MAP = {
    'model': 'Vendor PN',
    'vendor_oui': 'Vendor OUI',
    'vendor_date': 'Vendor Date Code(YYYY-MM-DD Lot)',
    'manufacturer': 'Vendor Name',
    'hardware_rev': 'Vendor Rev',
    'serial': 'Vendor SN',
    'type': 'Identifier',
    'ext_identifier': 'Extended Identifier',
    'ext_rateselect_compliance': 'Extended RateSelect Compliance',
    'cable_length': 'cable_length',
    'cable_type': 'Length',
    'nominal_bit_rate': 'Nominal Bit Rate(100Mbs)',
    'specification_compliance': 'Specification compliance',
    'encoding': 'Encoding',
    'connector': 'Connector',
    'application_advertisement': 'Application Advertisement'
}

SFP_DOM_CHANNEL_MONITOR_MAP = {
    'rx1power': 'RXPower',
    'tx1bias': 'TXBias',
    'tx1power': 'TXPower'
}

SFP_DOM_CHANNEL_THRESHOLD_MAP = {
    'txpowerhighalarm':   'TxPowerHighAlarm',
    'txpowerlowalarm':    'TxPowerLowAlarm',
    'txpowerhighwarning': 'TxPowerHighWarning',
    'txpowerlowwarning':  'TxPowerLowWarning',
    'rxpowerhighalarm':   'RxPowerHighAlarm',
    'rxpowerlowalarm':    'RxPowerLowAlarm',
    'rxpowerhighwarning': 'RxPowerHighWarning',
    'rxpowerlowwarning':  'RxPowerLowWarning',
    'txbiashighalarm':    'TxBiasHighAlarm',
    'txbiaslowalarm':     'TxBiasLowAlarm',
    'txbiashighwarning':  'TxBiasHighWarning',
    'txbiaslowwarning':   'TxBiasLowWarning'
}

QSFP_DOM_CHANNEL_THRESHOLD_MAP = {
    'rxpowerhighalarm':   'RxPowerHighAlarm',
    'rxpowerlowalarm':    'RxPowerLowAlarm',
    'rxpowerhighwarning': 'RxPowerHighWarning',
    'rxpowerlowwarning':  'RxPowerLowWarning',
    'txbiashighalarm':    'TxBiasHighAlarm',
    'txbiaslowalarm':     'TxBiasLowAlarm',
    'txbiashighwarning':  'TxBiasHighWarning',
    'txbiaslowwarning':   'TxBiasLowWarning'
}

DOM_MODULE_THRESHOLD_MAP = {
    'temphighalarm':  'TempHighAlarm',
    'templowalarm':   'TempLowAlarm',
    'temphighwarning': 'TempHighWarning',
    'templowwarning': 'TempLowWarning',
    'vcchighalarm':   'VccHighAlarm',
    'vcclowalarm':    'VccLowAlarm',
    'vcchighwarning': 'VccHighWarning',
    'vcclowwarning':  'VccLowWarning'
}

QSFP_DOM_CHANNEL_MONITOR_MAP = {
    'rx1power': 'RX1Power',
    'rx2power': 'RX2Power',
    'rx3power': 'RX3Power',
    'rx4power': 'RX4Power',
    'tx1bias':  'TX1Bias',
    'tx2bias':  'TX2Bias',
    'tx3bias':  'TX3Bias',
    'tx4bias':  'TX4Bias',
    'tx1power': 'TX1Power',
    'tx2power': 'TX2Power',
    'tx3power': 'TX3Power',
    'tx4power': 'TX4Power'
}

QSFP_DD_DOM_CHANNEL_MONITOR_MAP = {
    'rx1power': 'RX1Power',
    'rx2power': 'RX2Power',
    'rx3power': 'RX3Power',
    'rx4power': 'RX4Power',
    'rx5power': 'RX5Power',
    'rx6power': 'RX6Power',
    'rx7power': 'RX7Power',
    'rx8power': 'RX8Power',
    'tx1bias':  'TX1Bias',
    'tx2bias':  'TX2Bias',
    'tx3bias':  'TX3Bias',
    'tx4bias':  'TX4Bias',
    'tx5bias':  'TX5Bias',
    'tx6bias':  'TX6Bias',
    'tx7bias':  'TX7Bias',
    'tx8bias':  'TX8Bias',
    'tx1power': 'TX1Power',
    'tx2power': 'TX2Power',
    'tx3power': 'TX3Power',
    'tx4power': 'TX4Power',
    'tx5power': 'TX5Power',
    'tx6power': 'TX6Power',
    'tx7power': 'TX7Power',
    'tx8power': 'TX8Power'
}

DOM_MODULE_MONITOR_MAP = {
    'temperature': 'Temperature',
    'voltage': 'Vcc'
}

DOM_CHANNEL_THRESHOLD_UNIT_MAP = {
    'txpowerhighalarm':   'dBm',
    'txpowerlowalarm':    'dBm',
    'txpowerhighwarning': 'dBm',
    'txpowerlowwarning':  'dBm',
    'rxpowerhighalarm':   'dBm',
    'rxpowerlowalarm':    'dBm',
    'rxpowerhighwarning': 'dBm',
    'rxpowerlowwarning':  'dBm',
    'txbiashighalarm':    'mA',
    'txbiaslowalarm':     'mA',
    'txbiashighwarning':  'mA',
    'txbiaslowwarning':   'mA'
}

DOM_MODULE_THRESHOLD_UNIT_MAP = {
    'temphighalarm':   'C',
    'templowalarm':    'C',
    'temphighwarning': 'C',
    'templowwarning':  'C',
    'vcchighalarm':    'Volts',
    'vcclowalarm':     'Volts',
    'vcchighwarning':  'Volts',
    'vcclowwarning':   'Volts'
}

DOM_VALUE_UNIT_MAP = {
    'rx1power': 'dBm',
    'rx2power': 'dBm',
    'rx3power': 'dBm',
    'rx4power': 'dBm',
    'tx1bias': 'mA',
    'tx2bias': 'mA',
    'tx3bias': 'mA',
    'tx4bias': 'mA',
    'tx1power': 'dBm',
    'tx2power': 'dBm',
    'tx3power': 'dBm',
    'tx4power': 'dBm',
    'temperature': 'C',
    'voltage': 'Volts'
}

QSFP_DD_DOM_VALUE_UNIT_MAP = {
    'rx1power': 'dBm',
    'rx2power': 'dBm',
    'rx3power': 'dBm',
    'rx4power': 'dBm',
    'rx5power': 'dBm',
    'rx6power': 'dBm',
    'rx7power': 'dBm',
    'rx8power': 'dBm',
    'tx1bias': 'mA',
    'tx2bias': 'mA',
    'tx3bias': 'mA',
    'tx4bias': 'mA',
    'tx5bias': 'mA',
    'tx6bias': 'mA',
    'tx7bias': 'mA',
    'tx8bias': 'mA',
    'tx1power': 'dBm',
    'tx2power': 'dBm',
    'tx3power': 'dBm',
    'tx4power': 'dBm',
    'tx5power': 'dBm',
    'tx6power': 'dBm',
    'tx7power': 'dBm',
    'tx8power': 'dBm',
    'temperature': 'C',
    'voltage': 'Volts'
}


# Global platform-specific Chassis class instance
platform_chassis = None

# Global platform-specific sfputil class instance
platform_sfputil = None

# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)


# ========================== Methods for formatting output ==========================

# Convert dict values to cli output string
def format_dict_value_to_string(sorted_key_table,
                                dom_info_dict, dom_value_map,
                                dom_unit_map, alignment=0):
    output = ''
    indent = ' ' * 8
    separator = ": "
    for key in sorted_key_table:
        if dom_info_dict is not None and key in dom_info_dict and dom_info_dict[key] != 'N/A':
            value = dom_info_dict[key]
            units = ''
            if type(value) != str or (value != 'Unknown' and not value.endswith(dom_unit_map[key])):
                units = dom_unit_map[key]
            output += '{}{}{}{}{}\n'.format((indent * 2),
                                            dom_value_map[key],
                                            separator.rjust(len(separator) + alignment - len(dom_value_map[key])),
                                            value,
                                            units)
    return output


def convert_sfp_info_to_output_string(sfp_info_dict):
    indent = ' ' * 8
    output = ''

    sorted_qsfp_data_map_keys = sorted(QSFP_DATA_MAP, key=QSFP_DATA_MAP.get)
    for key in sorted_qsfp_data_map_keys:
        if key == 'cable_type':
            output += '{}{}: {}\n'.format(indent, sfp_info_dict['cable_type'], sfp_info_dict['cable_length'])
        elif key == 'cable_length':
            pass
        elif key == 'specification_compliance':
            if sfp_info_dict['type'] == "QSFP-DD Double Density 8X Pluggable Transceiver":
                output += '{}{}: {}\n'.format(indent, QSFP_DATA_MAP[key], sfp_info_dict[key])
            else:
                output += '{}{}:\n'.format(indent, QSFP_DATA_MAP['specification_compliance'])
                spefic_compliance_dict = eval(sfp_info_dict['specification_compliance'])
                sorted_compliance_key_table = natsorted(spefic_compliance_dict)
                for compliance_key in sorted_compliance_key_table:
                    output += '{}{}: {}\n'.format((indent * 2), compliance_key, spefic_compliance_dict[compliance_key])
        else:
            output += '{}{}: {}\n'.format(indent, QSFP_DATA_MAP[key], sfp_info_dict[key])

    return output


# Convert DOM sensor info in DB to CLI output string
def convert_dom_to_output_string(sfp_type, dom_info_dict):
    indent = ' ' * 8
    output_dom = ''
    channel_threshold_align = 18
    module_threshold_align = 15

    if sfp_type.startswith('QSFP'):
        # Channel Monitor
        if sfp_type.startswith('QSFP-DD'):
            output_dom += (indent + 'ChannelMonitorValues:\n')
            sorted_key_table = natsorted(QSFP_DD_DOM_CHANNEL_MONITOR_MAP)
            output_channel = format_dict_value_to_string(
                sorted_key_table, dom_info_dict,
                QSFP_DD_DOM_CHANNEL_MONITOR_MAP,
                QSFP_DD_DOM_VALUE_UNIT_MAP)
            output_dom += output_channel
        else:
            output_dom += (indent + 'ChannelMonitorValues:\n')
            sorted_key_table = natsorted(QSFP_DOM_CHANNEL_MONITOR_MAP)
            output_channel = format_dict_value_to_string(
                sorted_key_table, dom_info_dict,
                QSFP_DOM_CHANNEL_MONITOR_MAP,
                DOM_VALUE_UNIT_MAP)
            output_dom += output_channel

        # Channel Threshold
        if sfp_type.startswith('QSFP-DD'):
            dom_map = SFP_DOM_CHANNEL_THRESHOLD_MAP
        else:
            dom_map = QSFP_DOM_CHANNEL_THRESHOLD_MAP

        output_dom += (indent + 'ChannelThresholdValues:\n')
        sorted_key_table = natsorted(dom_map)
        output_channel_threshold = format_dict_value_to_string(
            sorted_key_table, dom_info_dict,
            dom_map,
            DOM_CHANNEL_THRESHOLD_UNIT_MAP,
            channel_threshold_align)
        output_dom += output_channel_threshold

        # Module Monitor
        output_dom += (indent + 'ModuleMonitorValues:\n')
        sorted_key_table = natsorted(DOM_MODULE_MONITOR_MAP)
        output_module = format_dict_value_to_string(
            sorted_key_table, dom_info_dict,
            DOM_MODULE_MONITOR_MAP,
            DOM_VALUE_UNIT_MAP)
        output_dom += output_module

        # Module Threshold
        output_dom += (indent + 'ModuleThresholdValues:\n')
        sorted_key_table = natsorted(DOM_MODULE_THRESHOLD_MAP)
        output_module_threshold = format_dict_value_to_string(
            sorted_key_table, dom_info_dict,
            DOM_MODULE_THRESHOLD_MAP,
            DOM_MODULE_THRESHOLD_UNIT_MAP,
            module_threshold_align)
        output_dom += output_module_threshold

    else:
        output_dom += (indent + 'MonitorData:\n')
        sorted_key_table = natsorted(SFP_DOM_CHANNEL_MONITOR_MAP)
        output_channel = format_dict_value_to_string(
            sorted_key_table, dom_info_dict,
            SFP_DOM_CHANNEL_MONITOR_MAP,
            DOM_VALUE_UNIT_MAP)
        output_dom += output_channel

        sorted_key_table = natsorted(DOM_MODULE_MONITOR_MAP)
        output_module = format_dict_value_to_string(
            sorted_key_table, dom_info_dict,
            DOM_MODULE_MONITOR_MAP,
            DOM_VALUE_UNIT_MAP)
        output_dom += output_module

        output_dom += (indent + 'ThresholdData:\n')

        # Module Threshold
        sorted_key_table = natsorted(DOM_MODULE_THRESHOLD_MAP)
        output_module_threshold = format_dict_value_to_string(
            sorted_key_table, dom_info_dict,
            DOM_MODULE_THRESHOLD_MAP,
            DOM_MODULE_THRESHOLD_UNIT_MAP,
            module_threshold_align)
        output_dom += output_module_threshold

        # Channel Threshold
        sorted_key_table = natsorted(SFP_DOM_CHANNEL_THRESHOLD_MAP)
        output_channel_threshold = format_dict_value_to_string(
            sorted_key_table, dom_info_dict,
            SFP_DOM_CHANNEL_THRESHOLD_MAP,
            DOM_CHANNEL_THRESHOLD_UNIT_MAP,
            channel_threshold_align)
        output_dom += output_channel_threshold

    return output_dom


# =============== Getting and printing SFP data ===============


#
def get_physical_port_name(logical_port, physical_port, ganged):
    """
        Returns:
          port_num if physical
          logical_port:port_num if logical port and is a ganged port
          logical_port if logical and not ganged
    """
    if logical_port == physical_port:
        return str(logical_port)
    elif ganged:
        return "{}:{} (ganged)".format(logical_port, physical_port)
    else:
        return logical_port


def logical_port_name_to_physical_port_list(port_name):
    if port_name.startswith("Ethernet"):
        if platform_sfputil.is_logical_port(port_name):
            return platform_sfputil.get_logical_to_physical(port_name)
        else:
            click.echo("Error: Invalid port '{}'".format(port_name))
            return None
    else:
        return [int(port_name)]


def print_all_valid_port_values():
    click.echo("Valid values for port: {}\n".format(str(platform_sfputil.logical)))


# ==================== Methods for initialization ====================


# Instantiate platform-specific Chassis class
def load_platform_chassis():
    global platform_chassis

    # Load new platform api class
    try:
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
    except Exception as e:
        log.log_error("Failed to instantiate Chassis due to {}".format(repr(e)))

    if not platform_chassis:
        return False

    return True


# Instantiate SfpUtilHelper class
def load_sfputilhelper():
    global platform_sfputil

    # we have to make use of sfputil for some features
    # even though when new platform api is used for all vendors.
    # in this sense, we treat it as a part of new platform api.
    # we have already moved sfputil to sonic_platform_base
    # which is the root of new platform api.
    platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()

    if not platform_sfputil:
        return False

    return True


def load_port_config():
    try:
        if multi_asic.is_multi_asic():
            # For multi ASIC platforms we pass DIR of port_config_file_path and the number of asics
            (platform_path, hwsku_path) = device_info.get_paths_to_platform_and_hwsku_dirs()

            # Load platform module from source
            platform_sfputil.read_all_porttab_mappings(hwsku_path, multi_asic.get_num_asics())
        else:
            # For single ASIC platforms we pass port_config_file_path and the asic_inst as 0
            port_config_file_path = device_info.get_path_to_port_config_file()
            platform_sfputil.read_porttab_mappings(port_config_file_path, 0)
    except Exception as e:
        log.log_error("Error reading port info ({})".format(str(e)), True)
        return False

    return True

# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'sfputil' command
@click.group()
def cli():
    """sfputil - Command line utility for managing SFP transceivers"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERROR_PERMISSIONS)

    # Load platform-specific Chassis class
    if not load_platform_chassis():
        sys.exit(ERROR_CHASSIS_LOAD)

    # Load SfpUtilHelper class
    if not load_sfputilhelper():
        sys.exit(ERROR_SFPUTILHELPER_LOAD)

    # Load port info
    if not load_port_config():
        sys.exit(ERROR_PORT_CONFIG_LOAD)


# 'show' subgroup
@cli.group()
def show():
    """Display status of SFP transceivers"""
    pass


# 'eeprom' subcommand
@show.command()
@click.option('-p', '--port', metavar='<port_name>', help="Display SFP EEPROM data for port <port_name> only")
@click.option('-d', '--dom', 'dump_dom', is_flag=True, help="Also display Digital Optical Monitoring (DOM) data")
@click.option('-n', '--namespace', default=None, help="Display interfaces for specific namespace")
def eeprom(port, dump_dom, namespace):
    """Display EEPROM data of SFP transceiver(s)"""
    logical_port_list = []
    output = ""

    # Create a list containing the logical port names of all ports we're interested in
    if port is None:
        logical_port_list = platform_sfputil.logical
    else:
        if platform_sfputil.is_logical_port(port) == 0:
            click.echo("Error: invalid port '{}'\n".format(port))
            print_all_valid_port_values()
            sys.exit(ERROR_INVALID_PORT)

        logical_port_list = [port]

    for logical_port_name in logical_port_list:
        ganged = False
        i = 1

        physical_port_list = logical_port_name_to_physical_port_list(logical_port_name)
        if physical_port_list is None:
            click.echo("Error: No physical ports found for logical port '{}'".format(logical_port_name))
            return

        if len(physical_port_list) > 1:
            ganged = True

        for physical_port in physical_port_list:
            port_name = get_physical_port_name(logical_port_name, i, ganged)

            try:
                presence = platform_chassis.get_sfp(physical_port).get_presence()
            except NotImplementedError:
                click.echo("Sfp.get_presence() is currently not implemented for this platform")
                sys.exit(ERROR_NOT_IMPLEMENTED)

            if not presence:
                output += "{}: SFP EEPROM not detected\n".format(port_name)
            else:
                output += "{}: SFP EEPROM detected\n".format(port_name)

                try:
                    xcvr_info = platform_chassis.get_sfp(physical_port).get_transceiver_info()
                except NotImplementedError:
                    click.echo("Sfp.get_transceiver_info() is currently not implemented for this platform")
                    sys.exit(ERROR_NOT_IMPLEMENTED)

                output += convert_sfp_info_to_output_string(xcvr_info)

                if dump_dom:
                    try:
                        xcvr_dom_info = platform_chassis.get_sfp(physical_port).get_transceiver_bulk_status()
                    except NotImplementedError:
                        click.echo("Sfp.get_transceiver_bulk_status() is currently not implemented for this platform")
                        sys.exit(ERROR_NOT_IMPLEMENTED)

                    try:
                        xcvr_dom_threshold_info = platform_chassis.get_sfp(physical_port).get_transceiver_threshold_info()
                        if xcvr_dom_threshold_info:
                            xcvr_dom_info.update(xcvr_dom_threshold_info)
                    except NotImplementedError:
                        click.echo("Sfp.get_transceiver_threshold_info() is currently not implemented for this platform")
                        sys.exit(ERROR_NOT_IMPLEMENTED)

                    output += convert_dom_to_output_string(xcvr_info['type'], xcvr_dom_info)

            output += '\n'

    click.echo(output)


# 'presence' subcommand
@show.command()
@click.option('-p', '--port', metavar='<port_name>', help="Display SFP presence for port <port_name> only")
def presence(port):
    """Display presence of SFP transceiver(s)"""
    logical_port_list = []
    output_table = []
    table_header = ["Port", "Presence"]

    # Create a list containing the logical port names of all ports we're interested in
    if port is None:
        logical_port_list = platform_sfputil.logical
    else:
        if platform_sfputil.is_logical_port(port) == 0:
            click.echo("Error: invalid port '{}'\n".format(port))
            print_all_valid_port_values()
            sys.exit(ERROR_INVALID_PORT)

        logical_port_list = [port]

    for logical_port_name in logical_port_list:
        ganged = False
        i = 1

        physical_port_list = logical_port_name_to_physical_port_list(logical_port_name)
        if physical_port_list is None:
            click.echo("Error: No physical ports found for logical port '{}'".format(logical_port_name))
            return

        if len(physical_port_list) > 1:
            ganged = True

        for physical_port in physical_port_list:
            port_name = get_physical_port_name(logical_port_name, i, ganged)

            try:
                presence = platform_chassis.get_sfp(physical_port).get_presence()
            except NotImplementedError:
                click.echo("This functionality is currently not implemented for this platform")
                sys.exit(ERROR_NOT_IMPLEMENTED)

            status_string = "Present" if presence else "Not present"
            output_table.append([port_name, status_string])

            i += 1

    click.echo(tabulate(output_table, table_header, tablefmt="simple"))


# 'error-status' subcommand
def fetch_error_status_from_platform_api(port):
    """Fetch the error status from platform API and return the output as a string
    Args:
        port: the port whose error status will be fetched.
              None represents for all ports.
    Returns:
        A string consisting of the error status of each port.
    """
    if port is None:
        logical_port_list = natsort.natsorted(platform_sfputil.logical)
        # Create a list containing the logical port names of all ports we're interested in
        generate_sfp_list_code = \
            "sfp_list = chassis.get_all_sfps()\n"
    else:
        physical_port_list = logical_port_name_to_physical_port_list(port)
        logical_port_list = [port]
        # Create a list containing the logical port names of all ports we're interested in
        generate_sfp_list_code = \
            "sfp_list = [chassis.get_sfp(x) for x in {}]\n".format(physical_port_list)

    # Code to initialize chassis object
    init_chassis_code = \
        "import sonic_platform.platform\n" \
        "platform = sonic_platform.platform.Platform()\n" \
        "chassis = platform.get_chassis()\n"

    # Code to fetch the error status
    get_error_status_code = \
        "try:\n"\
        "    errors=['{}:{}'.format(sfp.index, sfp.get_error_description()) for sfp in sfp_list]\n" \
        "except NotImplementedError as e:\n"\
        "    errors=['{}:{}'.format(sfp.index, 'OK (Not implemented)') for sfp in sfp_list]\n" \
        "print(errors)\n"

    get_error_status_command = "docker exec pmon python3 -c \"{}{}{}\"".format(
        init_chassis_code, generate_sfp_list_code, get_error_status_code)
    # Fetch error status from pmon docker
    try:
        output = subprocess.check_output(get_error_status_command, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        click.Abort("Error! Unable to fetch error status for SPF modules. Error code = {}, error messages: {}".format(e.returncode, e.output))
        return None

    output_list = output.split('\n')
    for output_str in output_list:
        # The output of all SFP error status are a list consisting of element with convention of '<sfp no>:<error status>'
        # Besides, there can be some logs captured during the platform API executing
        # So, first of all, we need to skip all the logs until find the output list of SFP error status
        if output_str[0] == '[' and output_str[-1] == ']':
            output_list = ast.literal_eval(output_str)
            break

    output_dict = {}
    for output in output_list:
        sfp_index, error_status = output.split(':')
        output_dict[int(sfp_index)] = error_status

    output = []
    for logical_port_name in logical_port_list:
        physical_port_list = logical_port_name_to_physical_port_list(logical_port_name)
        port_name = get_physical_port_name(logical_port_name, 1, False)

        output.append([port_name, output_dict.get(physical_port_list[0])])

    return output

def fetch_error_status_from_state_db(port, state_db):
    """Fetch the error status from STATE_DB and return them in a list.
    Args:
        port: the port whose error status will be fetched.
              None represents for all ports.
    Returns:
        A list consisting of tuples (port, description) and sorted by port.
    """
    status = {}
    if port:
        status[port] = state_db.get_all(state_db.STATE_DB, 'TRANSCEIVER_STATUS|{}'.format(port))
    else:
        ports = state_db.keys(state_db.STATE_DB, 'TRANSCEIVER_STATUS|*')
        for key in ports:
            status[key.split('|')[1]] = state_db.get_all(state_db.STATE_DB, key)

    sorted_ports = natsort.natsorted(status)
    output = []
    for port in sorted_ports:
        statestring = status[port].get('status')
        description = status[port].get('error')
        if statestring == '1':
            description = 'OK'
        elif statestring == '0':
            description = 'Unplugged'
        elif description == 'N/A':
            log.log_error("Inconsistent state found for port {}: state is {} but error description is N/A".format(port, statestring))
            description = 'Unknown state: {}'.format(statestring)

        output.append([port, description])

    return output

@show.command()
@click.option('-p', '--port', metavar='<port_name>', help="Display SFP error status for port <port_name> only")
@click.option('-hw', '--fetch-from-hardware', 'fetch_from_hardware', is_flag=True, default=False, help="Fetch the error status from hardware directly")
def error_status(port, fetch_from_hardware):
    """Display error status of SFP transceiver(s)"""
    output_table = []
    table_header = ["Port", "Error Status"]

    # Create a list containing the logical port names of all ports we're interested in
    if port and platform_sfputil.is_logical_port(port) == 0:
        click.echo("Error: invalid port '{}'\n".format(port))
        click.echo("Valid values for port: {}\n".format(str(platform_sfputil.logical)))
        sys.exit(ERROR_INVALID_PORT)

    if fetch_from_hardware:
        output_table = fetch_error_status_from_platform_api(port)
    else:
        # Connect to STATE_DB
        state_db = SonicV2Connector(host='127.0.0.1')
        if state_db is not None:
            state_db.connect(state_db.STATE_DB)
        else:
            click.echo("Failed to connect to STATE_DB")
            return

        output_table = fetch_error_status_from_state_db(port, state_db)

    click.echo(tabulate(output_table, table_header, tablefmt='simple'))


# 'lpmode' subcommand
@show.command()
@click.option('-p', '--port', metavar='<port_name>', help="Display SFP low-power mode status for port <port_name> only")
def lpmode(port):
    """Display low-power mode status of SFP transceiver(s)"""
    logical_port_list = []
    output_table = []
    table_header = ["Port", "Low-power Mode"]

    # Create a list containing the logical port names of all ports we're interested in
    if port is None:
        logical_port_list = platform_sfputil.logical
    else:
        if platform_sfputil.is_logical_port(port) == 0:
            click.echo("Error: invalid port '{}'\n".format(port))
            print_all_valid_port_values()
            sys.exit(ERROR_INVALID_PORT)

        logical_port_list = [port]

    for logical_port_name in logical_port_list:
        ganged = False
        i = 1

        physical_port_list = logical_port_name_to_physical_port_list(logical_port_name)
        if physical_port_list is None:
            click.echo("Error: No physical ports found for logical port '{}'".format(logical_port_name))
            return

        if len(physical_port_list) > 1:
            ganged = True

        for physical_port in physical_port_list:
            port_name = get_physical_port_name(logical_port_name, i, ganged)

            try:
                lpmode = platform_chassis.get_sfp(physical_port).get_lpmode()
            except NotImplementedError:
                click.echo("This functionality is currently not implemented for this platform")
                sys.exit(ERROR_NOT_IMPLEMENTED)

            if lpmode:
                output_table.append([port_name, "On"])
            else:
                output_table.append([port_name, "Off"])

            i += 1

    click.echo(tabulate(output_table, table_header, tablefmt='simple'))


# 'lpmode' subgroup
@cli.group()
def lpmode():
    """Enable or disable low-power mode for SFP transceiver"""
    pass


# Helper method for setting low-power mode
def set_lpmode(logical_port, enable):
    ganged = False
    i = 1

    if platform_sfputil.is_logical_port(logical_port) == 0:
        click.echo("Error: invalid port '{}'\n".format(logical_port))
        print_all_valid_port_values()
        sys.exit(ERROR_INVALID_PORT)

    physical_port_list = logical_port_name_to_physical_port_list(logical_port)
    if physical_port_list is None:
        click.echo("Error: No physical ports found for logical port '{}'".format(logical_port))
        return

    if len(physical_port_list) > 1:
        ganged = True

    for physical_port in physical_port_list:
        click.echo("{} low-power mode for port {} ... ".format(
            "Enabling" if enable else "Disabling",
            get_physical_port_name(logical_port, i, ganged)), nl=False)

        try:
            result = platform_chassis.get_sfp(physical_port).set_lpmode(enable)
        except NotImplementedError:
            click.echo("This functionality is currently not implemented for this platform")
            sys.exit(ERROR_NOT_IMPLEMENTED)

        if result:
            click.echo("OK")
        else:
            click.echo("Failed")

        i += 1


# 'off' subcommand
@lpmode.command()
@click.argument('port_name', metavar='<port_name>')
def off(port_name):
    """Disable low-power mode for SFP transceiver"""
    set_lpmode(port_name, False)


# 'on' subcommand
@lpmode.command()
@click.argument('port_name', metavar='<port_name>')
def on(port_name):
    """Enable low-power mode for SFP transceiver"""
    set_lpmode(port_name, True)


# 'reset' subcommand
@cli.command()
@click.argument('port_name', metavar='<port_name>')
def reset(port_name):
    """Reset SFP transceiver"""
    ganged = False
    i = 1

    if platform_sfputil.is_logical_port(port_name) == 0:
        click.echo("Error: invalid port '{}'\n".format(port_name))
        print_all_valid_port_values()
        sys.exit(ERROR_INVALID_PORT)

    physical_port_list = logical_port_name_to_physical_port_list(port_name)
    if physical_port_list is None:
        click.echo("Error: No physical ports found for logical port '{}'".format(port_name))
        return

    if len(physical_port_list) > 1:
        ganged = True

    for physical_port in physical_port_list:
        click.echo("Resetting port {} ... ".format(get_physical_port_name(port_name, i, ganged)), nl=False)

        try:
            result = platform_chassis.get_sfp(physical_port).reset()
        except NotImplementedError:
            click.echo("This functionality is currently not implemented for this platform")
            sys.exit(ERROR_NOT_IMPLEMENTED)

        if result:
            click.echo("OK")
        else:
            click.echo("Failed")

        i += 1


# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("sfputil version {0}".format(VERSION))


if __name__ == '__main__':
    cli()
