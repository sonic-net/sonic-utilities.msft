import os
import sys

import mock
import click
import pytest

import mock_tables.dbconnector

import sonic_device_util
from swsssdk import ConfigDBConnector

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


def _dummy_run_command(command, display_cmd=False, return_cmd=False):
    if display_cmd == True:
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

@pytest.fixture
def get_cmd_module():
    import config.main as config
    import show.main as show

    config.run_command = _dummy_run_command

    return (config, show)

@pytest.fixture
def setup_single_broacom_asic():
    import config.main as config
    import show.main as show

    sonic_device_util.get_num_npus = mock.MagicMock(return_value = 1)
    config._get_sonic_generated_services = \
            mock.MagicMock(return_value = (generated_services_list, []))

    config.asic_type = mock.MagicMock(return_value = "broadcom")
    config._get_device_type = mock.MagicMock(return_value = "ToRRouter")
