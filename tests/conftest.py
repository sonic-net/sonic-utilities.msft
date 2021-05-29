import json
import os
import re
import sys
from unittest import mock


import pytest
from sonic_py_common import device_info
from swsscommon.swsscommon import ConfigDBConnector

from .mock_tables import dbconnector
from . import show_ip_route_common
from .bgp_commands_input.bgp_neighbor_test_vector import(
    mock_show_bgp_neighbor_single_asic,
    mock_show_bgp_neighbor_multi_asic,
    )
from .bgp_commands_input.bgp_network_test_vector import (
    mock_show_bgp_network_single_asic,
    mock_show_bgp_network_multi_asic
    )
from . import config_int_ip_common
import utilities_common.constants as constants

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

generated_services_list = [
    'ntp-config.service',
    'warmboot-finalizer.service',
    'watchdog-control.service',
    'rsyslog-config.service',
    'interfaces-config.service',
    'hostcfgd.service',
    'hostname-config.service',
    'topology.service',
    'updategraph.service',
    'config-setup.service',
    'caclmgrd.service',
    'procdockerstatsd.service',
    'pcie-check.service',
    'process-reboot-cause.service',
    'dhcp_relay.service',
    'snmp.service',
    'sflow.service',
    'bgp.service',
    'telemetry.service',
    'swss.service',
    'database.service',
    'database.service',
    'lldp.service',
    'lldp.service',
    'pmon.service',
    'radv.service',
    'mgmt-framework.service',
    'nat.service',
    'teamd.service',
    'syncd.service',
    'snmp.timer',
    'telemetry.timer']


@pytest.fixture
def get_cmd_module():
    import config.main as config
    import show.main as show

    return (config, show)

def set_mock_apis():
    import config.main as config
    cwd = os.path.dirname(os.path.realpath(__file__))
    config.asic_type = mock.MagicMock(return_value="broadcom")
    config._get_device_type = mock.MagicMock(return_value="ToRRouter")

@pytest.fixture
def setup_qos_mock_apis():
    cwd = os.path.dirname(os.path.realpath(__file__))
    device_info.get_paths_to_platform_and_hwsku_dirs = mock.MagicMock(
        return_value=(
            os.path.join(cwd, "."), os.path.join(cwd, "qos_config_input")
        )
    )
    device_info.get_sonic_version_file = mock.MagicMock(
        return_value=os.path.join(cwd, "qos_config_input/sonic_version.yml")
    )

@pytest.fixture
def setup_single_broadcom_asic():
    import config.main as config
    import show.main as show

    set_mock_apis()
    device_info.get_num_npus = mock.MagicMock(return_value=1)
    config._get_sonic_generated_services = \
        mock.MagicMock(return_value=(generated_services_list, []))


@pytest.fixture
def setup_multi_broadcom_masic():
    import config.main as config
    import show.main as show

    set_mock_apis()
    device_info.get_num_npus = mock.MagicMock(return_value=2)

    yield

    device_info.get_num_npus = mock.MagicMock(return_value=1)


@pytest.fixture
def setup_t1_topo():
    dbconnector.topo = "t1"
    yield
    dbconnector.topo = None

@pytest.fixture
def setup_single_bgp_instance(request):
    import utilities_common.bgp_util as bgp_util
    if request.param == 'v4':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv4_bgp_summary.json')
    elif request.param == 'v6':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv6_bgp_summary.json')
    else:
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'dummy.json')

    def mock_show_bgp_summary(vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.RVTYSH_COMMAND):
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        return ""
    
    def mock_run_bgp_command_for_static(vtysh_cmd, bgp_namespace="", vtysh_shell_cmd=constants.RVTYSH_COMMAND):
        if vtysh_cmd == "show ip route vrf all static":
            return config_int_ip_common.show_ip_route_with_static_expected_output
        elif vtysh_cmd == "show ipv6 route vrf all static":
            return config_int_ip_common.show_ipv6_route_with_static_expected_output
        else:
            return ""

    def mock_run_show_ip_route_commands(request):
        if request.param == 'ipv6_route_err':
            return show_ip_route_common.show_ipv6_route_err_expected_output
        elif request.param == 'ip_route':
            return show_ip_route_common.show_ip_route_expected_output
        elif request.param == 'ip_specific_route':
            return show_ip_route_common.show_specific_ip_route_expected_output
        elif request.param == 'ip_special_route':
            return show_ip_route_common.show_special_ip_route_expected_output
        elif request.param == 'ipv6_route':
            return show_ip_route_common.show_ipv6_route_expected_output
        elif request.param == 'ipv6_specific_route':
            return show_ip_route_common.show_ipv6_route_single_json_expected_output
        else:
            return ""

            
    if any ([request.param == 'ipv6_route_err', request.param == 'ip_route',\
             request.param == 'ip_specific_route', request.param == 'ip_special_route',\
             request.param == 'ipv6_route', request.param == 'ipv6_specific_route']):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_run_show_ip_route_commands(request))
    elif request.param.startswith('bgp_v4_neighbor') or \
            request.param.startswith('bgp_v6_neighbor'):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_show_bgp_neighbor_single_asic(request))
    elif request.param.startswith('bgp_v4_network') or \
        request.param.startswith('bgp_v6_network'):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_show_bgp_network_single_asic(request))
    elif request.param == 'ip_route_for_int_ip':
        _old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock_run_bgp_command_for_static
    else:
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_show_bgp_summary("", ""))

    yield

    if request.param == 'ip_route_for_int_ip':
        bgp_util.run_bgp_command = _old_run_bgp_command


@pytest.fixture
def setup_multi_asic_bgp_instance(request):
    import utilities_common.bgp_util as bgp_util

    if request.param == 'ip_route':
        m_asic_json_file = 'ip_route.json'
    elif request.param == 'ip_specific_route':
        m_asic_json_file = 'ip_specific_route.json'
    elif request.param == 'ipv6_specific_route':
        m_asic_json_file = 'ipv6_specific_route.json'
    elif request.param == 'ipv6_route':
        m_asic_json_file = 'ipv6_route.json'
    elif request.param == 'ip_special_route':
        m_asic_json_file = 'ip_special_route.json'
    elif request.param == 'ip_empty_route':
        m_asic_json_file = 'ip_empty_route.json'
    elif request.param == 'ip_specific_route_on_1_asic':
        m_asic_json_file = 'ip_special_route_asic0_only.json'
    elif request.param == 'ip_specific_recursive_route':
        m_asic_json_file = 'ip_special_recursive_route.json'
    elif request.param == 'ip_route_summary':
        m_asic_json_file = 'ip_route_summary.txt'
    elif request.param.startswith('bgp_v4_network') or \
        request.param.startswith('bgp_v6_network') or \
        request.param.startswith('bgp_v4_neighbor') or \
        request.param.startswith('bgp_v6_neighbor'):
        m_asic_json_file = request.param
    else:
        m_asic_json_file = os.path.join(
            test_path, 'mock_tables', 'dummy.json')

    def mock_run_bgp_command_for_static(vtysh_cmd, bgp_namespace="", vtysh_shell_cmd=constants.RVTYSH_COMMAND):
        if bgp_namespace != 'test_ns':
            return ""
        if vtysh_cmd == "show ip route vrf all static":
            return config_int_ip_common.show_ip_route_with_static_expected_output
        elif vtysh_cmd == "show ipv6 route vrf all static":
            return config_int_ip_common.show_ipv6_route_with_static_expected_output
        else:
            return ""

    def mock_run_bgp_command(vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.RVTYSH_COMMAND):
        if m_asic_json_file.startswith('bgp_v4_network') or \
            m_asic_json_file.startswith('bgp_v6_network'):
            return mock_show_bgp_network_multi_asic(m_asic_json_file)
        
        if m_asic_json_file.startswith('bgp_v4_neighbor') or \
            m_asic_json_file.startswith('bgp_v6_neighbor'):
            return mock_show_bgp_neighbor_multi_asic(m_asic_json_file, bgp_namespace)

        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', bgp_namespace, m_asic_json_file)
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        else:
            return ""

    _old_run_bgp_command = bgp_util.run_bgp_command
    if request.param == 'ip_route_for_int_ip':
        bgp_util.run_bgp_command = mock_run_bgp_command_for_static
    else:
        bgp_util.run_bgp_command = mock_run_bgp_command

    yield

    bgp_util.run_bgp_command = _old_run_bgp_command

@pytest.fixture
def setup_bgp_commands():
    import show.main as show
    from show.bgp_frr_v4 import bgp as bgpv4
    from show.bgp_frr_v6 import bgp as bgpv6

    show.ip.add_command(bgpv4)
    show.ipv6.add_command(bgpv6)
    return show


@pytest.fixture
def setup_ip_route_commands():
    import show.main as show

    return show

