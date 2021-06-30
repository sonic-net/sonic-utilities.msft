import sys

import click

from . import cli as clicommon
from sonic_py_common import multi_asic, device_info

platform_sfputil = None


def load_platform_sfputil():

    global platform_sfputil
    try:
        import sonic_platform_base.sonic_sfp.sfputilhelper
        platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()
    except Exception as e:
        click.echo("Failed to instantiate platform_sfputil due to {}".format(repr(e)))
        sys.exit(1)

    return 0


def platform_sfputil_read_porttab_mappings():

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
        click.echo("Error reading port info (%s)" % str(e))
        sys.exit(1)

    return 0


def logical_port_name_to_physical_port_list(port_name):
    if port_name.startswith("Ethernet"):
        if platform_sfputil.is_logical_port(port_name):
            return platform_sfputil.get_logical_to_physical(port_name)
        else:
            click.echo("Invalid port '{}'".format(port_name))
            return None
    else:
        return [int(port_name)]


def get_logical_list():

    return platform_sfputil.logical


def get_asic_id_for_logical_port(port):

    return platform_sfputil.get_asic_id_for_logical_port(port)


def get_physical_to_logical():

    return platform_sfputil.physical_to_logical


def get_interface_alias(port, db):

    if port is not "all" and port is not None:
        alias = port
        iface_alias_converter = clicommon.InterfaceAliasConverter(db)
        port = iface_alias_converter.alias_to_name(alias)
        if port is None:
            click.echo("cannot find port name for alias {}".format(alias))
            sys.exit(1)

    return port

