import copy
import pytest
import filecmp
import importlib
import os
import traceback
import json
import jsonpatch
import sys
import unittest
import ipaddress
from unittest import mock

import click
from click.testing import CliRunner

from sonic_py_common import device_info, multi_asic
from utilities_common.db import Db
from utilities_common.general import load_module_from_source
from unittest.mock import MagicMock, patch, mock_open

from generic_config_updater.generic_updater import ConfigFormat

import config.main as config

# Add Test, module and script path.
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)
sys.path.insert(0, scripts_path)
os.environ["PATH"] += os.pathsep + scripts_path

# Config Reload input Path
mock_db_path = os.path.join(test_path, "config_reload_input")

# Load minigraph input Path
load_minigraph_input_path = os.path.join(test_path, "load_minigraph_input")
load_minigraph_platform_path = os.path.join(load_minigraph_input_path, "platform")
load_minigraph_platform_false_path = os.path.join(load_minigraph_input_path, "platform_false")

load_minigraph_command_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""

load_minigraph_platform_plugin_command_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer --no-delay
Running command: pfcwd start_default
Running Platform plugin ............!
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv4_only_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: [ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv6_only_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: [ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv4_ipv6_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: [ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

RELOAD_CONFIG_DB_OUTPUT = """\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_YANG_CFG_OUTPUT = """\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen  -Y /tmp/config.json  --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_MASIC_CONFIG_DB_OUTPUT = """\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  --write-to-db
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  -n asic0  --write-to-db
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  -n asic1  --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

reload_config_with_sys_info_command_output="""\
Running command: /usr/local/bin/sonic-cfggen -H -k Seastone-DX010-25-50 --write-to-db"""

reload_config_with_disabled_service_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

config_temp = {
        "scope": {
            "ACL_TABLE": {
                "MY_ACL_TABLE": {
                    "policy_desc": "My ACL",
                    "ports": ["Ethernet1", "Ethernet2"],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            "PORT": {
                "Ethernet1": {
                    "alias": "fortyGigE0/0",
                    "description": "fortyGigE0/0",
                    "index": "0",
                    "lanes": "29,30,31,32",
                    "mtu": "9100",
                    "pfc_asym": "off",
                    "speed": "40000"
                },
                "Ethernet2": {
                    "alias": "fortyGigE0/100",
                    "description": "fortyGigE0/100",
                    "index": "25",
                    "lanes": "125,126,127,128",
                    "mtu": "9100",
                    "pfc_asym": "off",
                    "speed": "40000"
                }
            }
        }
    }

def mock_run_command_side_effect(*args, **kwargs):
    command = args[0]

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer' , 0
        elif command == "systemctl list-dependencies --plain sonic.target | sed '1d'":
            return 'swss', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled', 0
        else:
            return '', 0

def mock_run_command_side_effect_disabled_timer(*args, **kwargs):
    command = args[0]

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer', 0
        elif command == "systemctl list-dependencies --plain sonic.target | sed '1d'":
            return 'swss', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'masked', 0
        elif command == "systemctl show swss.service --property ActiveState --value":
            return 'active', 0
        elif command == "systemctl show swss.service --property ActiveEnterTimestampMonotonic --value":
            return '0', 0
        else:
            return '', 0

def mock_run_command_side_effect_untriggered_timer(*args, **kwargs):
    command = args[0]

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer', 0
        elif command == "systemctl list-dependencies --plain sonic.target | sed '1d'":
            return 'swss', 0
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled', 0
        elif command == "systemctl show snmp.timer --property=LastTriggerUSecMonotonic --value":
            return '0', 0
        else:
            return '', 0

# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')


class TestConfigReload(object):
    dummy_cfg_file = os.path.join(os.sep, "tmp", "config.json")

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

        import config.main
        importlib.reload(config.main)
        open(cls.dummy_cfg_file, 'w').close()

    def test_config_reload(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            jsonfile_config = os.path.join(mock_db_path, "config_db.json")
            jsonfile_init_cfg = os.path.join(mock_db_path, "init_cfg.json")

            # create object
            config.INIT_CFG_FILE = jsonfile_init_cfg
            config.DEFAULT_CONFIG_DB_FILE =  jsonfile_config

            db = Db()
            runner = CliRunner()
            obj = {'config_db': db.cfgdb}

            # simulate 'config reload' to provoke load_sys_info option
            result = runner.invoke(config.config.commands["reload"], ["-l", "-n", "-y"], obj=obj)

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0

            assert "\n".join([l.rstrip() for l in result.output.split('\n')][:1]) == reload_config_with_sys_info_command_output

    def test_config_reload_stdin(self, get_cmd_module, setup_single_broadcom_asic):
        def mock_json_load(f):
            device_metadata = {
                "DEVICE_METADATA": {
                    "localhost": {
                        "docker_routing_config_mode": "split",
                        "hostname": "sonic",
                        "hwsku": "Seastone-DX010-25-50",
                        "mac": "00:e0:ec:89:6e:48",
                        "platform": "x86_64-cel_seastone-r0",
                        "type": "ToRRouter"
                    }
                }
            }
            return device_metadata
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command,\
                mock.patch("json.load", mock.MagicMock(side_effect=mock_json_load)):
            (config, show) = get_cmd_module

            dev_stdin = "/dev/stdin"
            jsonfile_init_cfg = os.path.join(mock_db_path, "init_cfg.json")

            # create object
            config.INIT_CFG_FILE = jsonfile_init_cfg

            db = Db()
            runner = CliRunner()
            obj = {'config_db': db.cfgdb}

            # simulate 'config reload' to provoke load_sys_info option
            result = runner.invoke(config.config.commands["reload"], [dev_stdin, "-l", "-n", "-y"], obj=obj)

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0

            assert "\n".join([l.rstrip() for l in result.output.split('\n')][:1]) == reload_config_with_sys_info_command_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


class TestLoadMinigraph(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == load_minigraph_command_output
            # Verify "systemctl reset-failed" is called for services under sonic.target
            mock_run_command.assert_any_call('systemctl reset-failed swss')
            # Verify "systemctl reset-failed" is called for services under sonic-delayed.target
            mock_run_command.assert_any_call('systemctl reset-failed snmp')
            assert mock_run_command.call_count == 11

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=(load_minigraph_platform_path, None)))
    def test_load_minigraph_platform_plugin(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == load_minigraph_platform_plugin_command_output
            # Verify "systemctl reset-failed" is called for services under sonic.target
            mock_run_command.assert_any_call('systemctl reset-failed swss')
            assert mock_run_command.call_count == 11

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=(load_minigraph_platform_false_path, None)))
    def test_load_minigraph_platform_plugin_fail(self, get_cmd_module, setup_single_broadcom_asic):
        print(load_minigraph_platform_false_path)
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code != 0
            assert "Platform plugin failed" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_port_config_bad_format(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            # Not in an array
            port_config = {"PORT": {"Ethernet0": {"admin_status": "up"}}}
            self.check_port_config(None, config, port_config, "Failed to load port_config.json, Error: Bad format: port_config is not an array")

            # No PORT table
            port_config = [{}]
            self.check_port_config(None, config, port_config, "Failed to load port_config.json, Error: Bad format: PORT table not exists")

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_port_config_inconsistent_port(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            db = Db()
            db.cfgdb.set_entry("PORT", "Ethernet1", {"admin_status": "up"})
            port_config = [{"PORT": {"Eth1": {"admin_status": "up"}}}]
            self.check_port_config(db, config, port_config, "Failed to load port_config.json, Error: Port Eth1 is not defined in current device")

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_port_config(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            db = Db()

            # From up to down
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "up"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "down"}}}]
            self.check_port_config(db, config, port_config, "config interface shutdown Ethernet0")

            # From down to up
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "down"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "up"}}}]
            self.check_port_config(db, config, port_config, "config interface startup Ethernet0")

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def check_port_config(self, db, config, port_config, expected_output):
        def read_json_file_side_effect(filename):
            return port_config
        with mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=read_json_file_side_effect)):
            def is_file_side_effect(filename):
                return True if 'port_config' in filename else False
            with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
                runner = CliRunner()
                result = runner.invoke(config.config.commands["load_minigraph"], ["-y"], obj=db)
                print(result.exit_code)
                print(result.output)
                assert result.exit_code == 0
                assert expected_output in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_non_exist_golden_config_path(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command, \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "--golden_config_path", "non_exist.json", "-y"])
            assert result.exit_code != 0
            assert "Cannot find 'non_exist.json'" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_specified_golden_config_path(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command, \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "--golden_config_path",  "golden_config.json", "-y"])
            assert result.exit_code == 0
            assert "config override-config-table golden_config.json" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_default_golden_config_path(self, get_cmd_module):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command, \
                mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["--override_config", "-y"])
            assert result.exit_code == 0
            assert "config override-config-table /etc/sonic/golden_config_db.json" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_traffic_shift_away(self, get_cmd_module):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-ty"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "TSA" in result.output

    @mock.patch('sonic_py_common.device_info.get_paths_to_platform_and_hwsku_dirs', mock.MagicMock(return_value=("dummy_path", None)))
    def test_load_minigraph_with_traffic_shift_away_with_golden_config(self, get_cmd_module):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            def is_file_side_effect(filename):
                return True if 'golden_config' in filename else False
            with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
                (config, show) = get_cmd_module
                db = Db()
                golden_config = {}
                runner = CliRunner()
                result = runner.invoke(config.config.commands["load_minigraph"], ["-ty", "--override_config"])
                print(result.exit_code)
                print(result.output)
                traceback.print_tb(result.exc_info[2])
                assert result.exit_code == 0
                assert "TSA" in result.output
                assert "[WARNING] Golden configuration may override Traffic-shift-away state" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

class TestReloadConfig(object):
    dummy_cfg_file = os.path.join(os.sep, "tmp", "config.json")

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        importlib.reload(config.main)

    def add_sysinfo_to_cfg_file(self):
        with open(self.dummy_cfg_file, 'w') as f:
            device_metadata = {
                "DEVICE_METADATA": {
                    "localhost": {
                        "platform": "some_platform",
                        "mac": "02:42:f0:7f:01:05"
                    }
                }
            }
            f.write(json.dumps(device_metadata))

    def test_reload_config_invalid_input(self, get_cmd_module, setup_single_broadcom_asic):
        open(self.dummy_cfg_file, 'w').close()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"],
                [self.dummy_cfg_file, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code != 0

    def test_reload_config_no_sysinfo(self, get_cmd_module, setup_single_broadcom_asic):
        with open(self.dummy_cfg_file, 'w') as f:
            device_metadata = {
                "DEVICE_METADATA": {
                    "localhost": {
                        "hwsku": "some_hwsku"
                    }
                }
            }
            f.write(json.dumps(device_metadata))

        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"],
                [self.dummy_cfg_file, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0

    def test_reload_config(self, get_cmd_module, setup_single_broadcom_asic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(
                config.config.commands["reload"],
                [self.dummy_cfg_file, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) \
                == RELOAD_CONFIG_DB_OUTPUT

    def test_config_reload_disabled_service(self, get_cmd_module, setup_single_broadcom_asic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
               "utilities_common.cli.run_command",
               mock.MagicMock(side_effect=mock_run_command_side_effect_disabled_timer)
        ) as mock_run_command:
            (config, show) = get_cmd_module

            runner = CliRunner()
            result = runner.invoke(config.config.commands["reload"], [self.dummy_cfg_file, "-y"])

            print(result.exit_code)
            print(result.output)
            print(reload_config_with_disabled_service_output)
            traceback.print_tb(result.exc_info[2])

            assert result.exit_code == 0

            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == reload_config_with_disabled_service_output

    def test_reload_config_masic(self, get_cmd_module, setup_multi_broadcom_masic):
        self.add_sysinfo_to_cfg_file()
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            # 3 config files: 1 for host and 2 for asic
            cfg_files = "{},{},{}".format(
                            self.dummy_cfg_file,
                            self.dummy_cfg_file,
                            self.dummy_cfg_file)
            result = runner.invoke(
                config.config.commands["reload"],
                [cfg_files, '-y', '-f'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) \
                == RELOAD_MASIC_CONFIG_DB_OUTPUT

    def test_reload_yang_config(self, get_cmd_module,
                                        setup_single_broadcom_asic):
        with mock.patch(
                "utilities_common.cli.run_command",
                mock.MagicMock(side_effect=mock_run_command_side_effect)
        ) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()

            result = runner.invoke(config.config.commands["reload"],
                                    [self.dummy_cfg_file, '-y', '-f', '-t', 'config_yang'])

            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) \
                == RELOAD_YANG_CFG_OUTPUT

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.remove(cls.dummy_cfg_file)
        print("TEARDOWN")


class TestConfigCbf(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        import config.main
        importlib.reload(config.main)

    def test_cbf_reload_single(
            self, get_cmd_module, setup_cbf_mock_apis,
            setup_single_broadcom_asic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "cbf_config_output.json")
        print("Saving output in {}".format(output_file))
        try:
            os.remove(output_file)
        except OSError:
            pass
        result = runner.invoke(
           config.config.commands["cbf"],
             ["reload", "--dry_run", output_file]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))
        expected_result = os.path.join(
            cwd, "cbf_config_input", "config_cbf.json"
        )
        assert filecmp.cmp(output_file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestConfigCbfMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_cbf_reload_masic(
            self, get_cmd_module, setup_cbf_mock_apis,
            setup_multi_broadcom_masic
    ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "cbf_config_output.json")
        print("Saving output in {}<0,1,2..>".format(output_file))
        num_asic = device_info.get_num_npus()
        print(num_asic)
        for asic in range(num_asic):
            try:
                file = "{}{}".format(output_file, asic)
                os.remove(file)
            except OSError:
                pass
        result = runner.invoke(
            config.config.commands["cbf"],
            ["reload", "--dry_run", output_file]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))

        for asic in range(num_asic):
            expected_result = os.path.join(
                cwd, "cbf_config_input", str(asic), "config_cbf.json"
            )
            file = "{}{}".format(output_file, asic)
            assert filecmp.cmp(file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


class TestConfigQos(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        import config.main
        importlib.reload(config.main)

    def _keys(args, kwargs):
        if not TestConfigQos._keys_counter:
            return []
        TestConfigQos._keys_counter-=1
        return ["BUFFER_POOL_TABLE:egress_lossy_pool"]

    def test_qos_wait_until_clear_empty(self):
        from config.main import _wait_until_clear

        with mock.patch('swsscommon.swsscommon.SonicV2Connector.keys',  side_effect=TestConfigQos._keys):
            TestConfigQos._keys_counter = 1
            empty = _wait_until_clear(["BUFFER_POOL_TABLE:*"], 0.5,2)
        assert empty

    def test_qos_wait_until_clear_not_empty(self):
        from config.main import _wait_until_clear

        with mock.patch('swsscommon.swsscommon.SonicV2Connector.keys', side_effect=TestConfigQos._keys):
            TestConfigQos._keys_counter = 10
            empty = _wait_until_clear(["BUFFER_POOL_TABLE:*"], 0.5,2)
        assert not empty

    @mock.patch('config.main._wait_until_clear')
    def test_qos_clear_no_wait(self, _wait_until_clear):
        from config.main import _clear_qos
        _clear_qos(True, False)
        _wait_until_clear.assert_called_with(['BUFFER_*_TABLE:*', 'BUFFER_*_SET'], interval=0.5, timeout=0, verbose=False)

    def test_qos_reload_single(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_single_broadcom_asic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_output.json")
        print("Saving output in {}".format(output_file))
        try:
            os.remove(output_file)
        except OSError:
            pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--dry_run", output_file, "--json-data", json_data]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))
        expected_result = os.path.join(
            cwd, "qos_config_input", "config_qos.json"
        )
        assert filecmp.cmp(output_file, expected_result, shallow=False)

    def test_qos_update_single(
            self, get_cmd_module, setup_qos_mock_apis
        ):
        (config, show) = get_cmd_module
        json_data = '{"DEVICE_METADATA": {"localhost": {}}, "PORT": {"Ethernet0": {}}}'
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_update.json")
        cmd_vector = ["reload", "--ports", "Ethernet0", "--json-data", json_data, "--dry_run", output_file]
        result = runner.invoke(config.config.commands["qos"], cmd_vector)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        cwd = os.path.dirname(os.path.realpath(__file__))
        expected_result = os.path.join(
            cwd, "qos_config_input", "update_qos.json"
        )
        assert filecmp.cmp(output_file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestConfigQosMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_qos_reload_masic(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_multi_broadcom_masic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_output.json")
        print("Saving output in {}<0,1,2..>".format(output_file))
        num_asic = device_info.get_num_npus()
        for asic in range(num_asic):
            try:
                file = "{}{}".format(output_file, asic)
                os.remove(file)
            except OSError:
                pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--dry_run", output_file, "--json-data", json_data]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))

        for asic in range(num_asic):
            expected_result = os.path.join(
                cwd, "qos_config_input", str(asic), "config_qos.json"
            )
            file = "{}{}".format(output_file, asic)
            assert filecmp.cmp(file, expected_result, shallow=False)

    def test_qos_update_masic(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_multi_broadcom_masic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()

        output_file = os.path.join(os.sep, "tmp", "qos_update_output")
        print("Saving output in {}<0,1,2..>".format(output_file))
        num_asic = device_info.get_num_npus()
        for asic in range(num_asic):
            try:
                file = "{}{}".format(output_file, asic)
                os.remove(file)
            except OSError:
                pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}, "PORT": {"Ethernet0": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--ports", "Ethernet0,Ethernet4", "--json-data", json_data, "--dry_run", output_file]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))

        for asic in range(num_asic):
            expected_result = os.path.join(
                cwd, "qos_config_input", str(asic), "update_qos.json"
            )

            assert filecmp.cmp(output_file + "asic{}".format(asic), expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()

class TestGenericUpdateCommands(unittest.TestCase):
    def setUp(self):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        self.runner = CliRunner()
        self.any_patch_as_json = [{"op": "remove", "path": "/PORT"}]
        self.any_patch = jsonpatch.JsonPatch(self.any_patch_as_json)
        self.any_patch_as_text = json.dumps(self.any_patch_as_json)
        self.any_path = '/usr/admin/patch.json-patch'
        self.any_target_config = {"PORT": {}}
        self.any_target_config_as_text = json.dumps(self.any_target_config)
        self.any_checkpoint_name = "any_checkpoint_name"
        self.any_checkpoints_list = ["checkpoint1", "checkpoint2", "checkpoint3"]
        self.any_checkpoints_list_as_text = json.dumps(self.any_checkpoints_list, indent=4)

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"PATCH_FILE_PATH\""

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        expected_call_with_default_values = mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, False, False, ())
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"], [self.any_path], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call_with_default_values])

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(self.any_patch, ConfigFormat.SONICYANG, True, True, True, expected_ignore_path_tuple)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path,
                                             "--format", ConfigFormat.SONICYANG.name,
                                             "--dry-run",
                                             "--ignore-non-yang-tables",
                                             "--ignore-path", "/ANY_TABLE",
                                             "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                             "--ignore-path", "",
                                             "--verbose"],
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call_with_non_default_values])

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.apply_patch.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path],
                                            catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_apply_patch__optional_parameters_passed_correctly(self):
        self.validate_apply_patch_optional_parameter(
            ["--format", ConfigFormat.SONICYANG.name],
            mock.call(self.any_patch, ConfigFormat.SONICYANG, False, False, False, ()))
        self.validate_apply_patch_optional_parameter(
            ["--verbose"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, True, False, False, ()))
        self.validate_apply_patch_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, True, False, ()))
        self.validate_apply_patch_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, False, True, ()))
        self.validate_apply_patch_optional_parameter(
            ["--ignore-path", "/ANY_TABLE"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, False, False, ("/ANY_TABLE",)))

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def validate_apply_patch_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Patch applied successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path] + param_args,
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.apply_patch.assert_called_once()
        mock_generic_updater.apply_patch.assert_has_calls([expected_call])

    def test_replace__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"TARGET_FILE_PATH\""

        # Act
        result = self.runner.invoke(config.config.commands["replace"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_replace__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["replace"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_replace__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        expected_call_with_default_values = mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False, False, ())
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"], [self.any_path], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call_with_default_values])

    def test_replace__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(self.any_target_config, ConfigFormat.SONICYANG, True, True, True, expected_ignore_path_tuple)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.any_path,
                                             "--format", ConfigFormat.SONICYANG.name,
                                             "--dry-run",
                                             "--ignore-non-yang-tables",
                                             "--ignore-path", "/ANY_TABLE",
                                             "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                             "--ignore-path", "",
                                             "--verbose"],
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call_with_non_default_values])

    def test_replace__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.replace.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.any_path],
                                            catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_replace__optional_parameters_passed_correctly(self):
        self.validate_replace_optional_parameter(
            ["--format", ConfigFormat.SONICYANG.name],
            mock.call(self.any_target_config, ConfigFormat.SONICYANG, False, False, False, ()))
        self.validate_replace_optional_parameter(
            ["--verbose"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, True, False, False, ()))
        self.validate_replace_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, True, False, ()))
        self.validate_replace_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False, True, ()))
        self.validate_replace_optional_parameter(
            ["--ignore-path", "/ANY_TABLE"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False, False, ("/ANY_TABLE",)))

    def validate_replace_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config replaced successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.any_path] + param_args,
                                            catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.replace.assert_called_once()
        mock_generic_updater.replace.assert_has_calls([expected_call])

    def test_rollback__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"CHECKPOINT_NAME\""

        # Act
        result = self.runner.invoke(config.config.commands["rollback"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_rollback__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["rollback"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_rollback__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config rolled back successfully"
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False, False, False, ())
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["rollback"], [self.any_checkpoint_name], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.rollback.assert_called_once()
        mock_generic_updater.rollback.assert_has_calls([expected_call_with_default_values])

    def test_rollback__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config rolled back successfully"
        expected_ignore_path_tuple = ('/ANY_TABLE', '/ANY_OTHER_TABLE/ANY_FIELD', '')
        expected_call_with_non_default_values = \
            mock.call(self.any_checkpoint_name, True, True, True, expected_ignore_path_tuple)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["rollback"],
                                        [self.any_checkpoint_name,
                                            "--dry-run",
                                            "--ignore-non-yang-tables",
                                            "--ignore-path", "/ANY_TABLE",
                                            "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                            "--ignore-path", "",
                                            "--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.rollback.assert_called_once()
        mock_generic_updater.rollback.assert_has_calls([expected_call_with_non_default_values])

    def test_rollback__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.rollback.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["rollback"],
                                        [self.any_checkpoint_name],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_rollback__optional_parameters_passed_correctly(self):
        self.validate_rollback_optional_parameter(
            ["--verbose"],
            mock.call(self.any_checkpoint_name, True, False, False, ()))
        self.validate_rollback_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_checkpoint_name, False, True, False, ()))
        self.validate_rollback_optional_parameter(
            ["--ignore-non-yang-tables"],
            mock.call(self.any_checkpoint_name, False, False, True, ()))
        self.validate_rollback_optional_parameter(
            ["--ignore-path", "/ACL_TABLE"],
            mock.call(self.any_checkpoint_name, False, False, False, ("/ACL_TABLE",)))

    def validate_rollback_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Config rolled back successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["rollback"],
                                        [self.any_checkpoint_name] + param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.rollback.assert_called_once()
        mock_generic_updater.rollback.assert_has_calls([expected_call])

    def test_checkpoint__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"CHECKPOINT_NAME\""

        # Act
        result = self.runner.invoke(config.config.commands["checkpoint"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_checkpoint__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["checkpoint"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_checkpoint__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint created successfully"
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"], [self.any_checkpoint_name], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.checkpoint.assert_called_once()
        mock_generic_updater.checkpoint.assert_has_calls([expected_call_with_default_values])

    def test_checkpoint__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint created successfully"
        expected_call_with_non_default_values = mock.call(self.any_checkpoint_name, True)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"],
                                        [self.any_checkpoint_name,
                                            "--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.checkpoint.assert_called_once()
        mock_generic_updater.checkpoint.assert_has_calls([expected_call_with_non_default_values])

    def test_checkpoint__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.checkpoint.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"],
                                        [self.any_checkpoint_name],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_checkpoint__optional_parameters_passed_correctly(self):
        self.validate_checkpoint_optional_parameter(
            ["--verbose"],
            mock.call(self.any_checkpoint_name, True))

    def validate_checkpoint_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint created successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["checkpoint"],
                                        [self.any_checkpoint_name] + param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.checkpoint.assert_called_once()
        mock_generic_updater.checkpoint.assert_has_calls([expected_call])

    def test_delete_checkpoint__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"CHECKPOINT_NAME\""

        # Act
        result = self.runner.invoke(config.config.commands["delete-checkpoint"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_delete_checkpoint__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["delete-checkpoint"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_delete_checkpoint__only_required_params__default_values_used_for_optional_params(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint deleted successfully"
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"], [self.any_checkpoint_name], catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.delete_checkpoint.assert_called_once()
        mock_generic_updater.delete_checkpoint.assert_has_calls([expected_call_with_default_values])

    def test_delete_checkpoint__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint deleted successfully"
        expected_call_with_non_default_values = mock.call(self.any_checkpoint_name, True)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [self.any_checkpoint_name,
                                            "--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.delete_checkpoint.assert_called_once()
        mock_generic_updater.delete_checkpoint.assert_has_calls([expected_call_with_non_default_values])

    def test_delete_checkpoint__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.delete_checkpoint.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [self.any_checkpoint_name],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_delete_checkpoint__optional_parameters_passed_correctly(self):
        self.validate_delete_checkpoint_optional_parameter(
            ["--verbose"],
            mock.call(self.any_checkpoint_name, True))

    def validate_delete_checkpoint_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = "Checkpoint deleted successfully"
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [self.any_checkpoint_name] + param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.delete_checkpoint.assert_called_once()
        mock_generic_updater.delete_checkpoint.assert_has_calls([expected_call])

    def test_list_checkpoints__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["list-checkpoints"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_list_checkpoints__all_optional_params_non_default__non_default_values_used(self):
        # Arrange
        expected_exit_code = 0
        expected_output = self.any_checkpoints_list_as_text
        expected_call_with_non_default_values = mock.call(True)
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.return_value = self.any_checkpoints_list
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        ["--verbose"],
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.list_checkpoints.assert_called_once()
        mock_generic_updater.list_checkpoints.assert_has_calls([expected_call_with_non_default_values])

    def test_list_checkpoints__exception_thrown__error_displayed_error_code_returned(self):
        # Arrange
        unexpected_exit_code = 0
        any_error_message = "any_error_message"
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.side_effect = Exception(any_error_message)
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        catch_exceptions=False)

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(any_error_message in result.output)

    def test_list_checkpoints__optional_parameters_passed_correctly(self):
        self.validate_list_checkpoints_optional_parameter(
            ["--verbose"],
            mock.call(True))

    def validate_list_checkpoints_optional_parameter(self, param_args, expected_call):
        # Arrange
        expected_exit_code = 0
        expected_output = self.any_checkpoints_list_as_text
        mock_generic_updater = mock.Mock()
        mock_generic_updater.list_checkpoints.return_value = self.any_checkpoints_list
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            # Act
            result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                        param_args,
                                        catch_exceptions=False)

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)
        mock_generic_updater.list_checkpoints.assert_called_once()
        mock_generic_updater.list_checkpoints.assert_has_calls([expected_call])


class TestConfigLoadMgmtConfig(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

        import config.main
        importlib.reload(config.main)

    def test_config_load_mgmt_config_ipv4_only(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_only_output, 5)

    def test_config_load_mgmt_config_ipv6_only(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv6_only_output, 5)
    
    def test_config_load_mgmt_config_ipv4_ipv6(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                },
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_ipv6_output, 8)

    def check_output(self, get_cmd_module, parse_device_desc_xml_result, expected_output, expected_command_call_count):
        def parse_device_desc_xml_side_effect(filename):
            print("parse dummy device_desc.xml")
            return parse_device_desc_xml_result
        def change_hostname_side_effect(hostname):
            print("change hostname to {}".format(hostname))
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            with mock.patch('config.main.parse_device_desc_xml', mock.MagicMock(side_effect=parse_device_desc_xml_side_effect)):
                with mock.patch('config.main._change_hostname', mock.MagicMock(side_effect=change_hostname_side_effect)):
                    (config, show) = get_cmd_module
                    runner = CliRunner()
                    with runner.isolated_filesystem():
                        with open('device_desc.xml', 'w') as f:
                            f.write('dummy')
                            result = runner.invoke(config.config.commands["load_mgmt_config"], ["-y", "device_desc.xml"])
                            print(result.exit_code)
                            print(result.output)
                            traceback.print_tb(result.exc_info[2])
                            assert result.exit_code == 0
                            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == expected_output
                            assert mock_run_command.call_count == expected_command_call_count

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


class TestApplyPatchMultiAsic(unittest.TestCase):
    def setUp(self):
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        importlib.reload(config.main)
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

        self.runner = CliRunner()
        self.patch_file_path = 'path/to/patch.json'
        self.replace_file_path = 'path/to/replace.json'
        self.patch_content = [
            {
                "op": "add",
                "path": "/localhost/ACL_TABLE/NEW_ACL_TABLE",
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet1", "Ethernet2"],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            {
                "op": "add",
                "path": "/asic0/ACL_TABLE/NEW_ACL_TABLE",
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet3", "Ethernet4"],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            {
                "op": "replace",
                "path": "/asic1/PORT/Ethernet1/mtu",
                "value": "9200"
            }
        ]

        test_config = copy.deepcopy(config_temp)
        data = test_config.pop("scope")
        self.all_config = {}
        self.all_config["localhost"] = data
        self.all_config["asic0"] = data
        self.all_config["asic0"]["bgpraw"] = ""
        self.all_config["asic1"] = data
        self.all_config["asic1"]["bgpraw"] = ""

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_multiasic(self):
        # Mock open to simulate file reading
        with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with mock.patch('config.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = mock.MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"], [self.patch_file_path], catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertEqual(result.exit_code, 0, "Command should succeed")
                self.assertIn("Patch applied successfully.", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('config.main.validate_patch', mock.Mock(return_value=True))
    def test_apply_patch_dryrun_multiasic(self):
        # Mock open to simulate file reading
        with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with mock.patch('config.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = mock.MagicMock()

                # Mock ConfigDBConnector to ensure it's not called during dry-run
                with mock.patch('config.main.ConfigDBConnector') as mock_config_db_connector:

                    print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                    # Invocation of the command with the CliRunner
                    result = self.runner.invoke(config.config.commands["apply-patch"],
                                                [self.patch_file_path,
                                                "--format", ConfigFormat.SONICYANG.name,
                                                "--dry-run",
                                                "--ignore-non-yang-tables",
                                                "--ignore-path", "/ANY_TABLE",
                                                "--ignore-path", "/ANY_OTHER_TABLE/ANY_FIELD",
                                                "--ignore-path", "",
                                                "--verbose"],
                                                catch_exceptions=False)

                    print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                    # Assertions and verifications
                    self.assertEqual(result.exit_code, 0, "Command should succeed")
                    self.assertIn("Patch applied successfully.", result.output)

                    # Verify mocked_open was called as expected
                    mocked_open.assert_called_with(self.patch_file_path, 'r')

                    # Ensure ConfigDBConnector was never instantiated or called
                    mock_config_db_connector.assert_not_called()

    @patch('config.main.subprocess.Popen')
    @patch('config.main.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_multiasic(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 0)
        mock_subprocess_popen.return_value = mock_instance

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.patch_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertEqual(result.exit_code, 0, "Command should succeed.")
                self.assertIn("Patch applied successfully.", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('config.main.subprocess.Popen')
    @patch('config.main.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_with_badpath_multiasic(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 0)
        mock_subprocess_popen.return_value = mock_instance

        bad_patch = copy.deepcopy(self.patch_content)
        bad_patch.append({
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet3", "Ethernet4"],
                    "stage": "ingress",
                    "type": "L3"
                }
            })

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(bad_patch)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.patch_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertNotEqual(result.exit_code, 0, "Command should failed.")
                self.assertIn("Failed to apply patch", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('config.main.subprocess.Popen')
    @patch('config.main.SonicYangCfgDbGenerator.validate_config_db_json', mock.Mock(return_value=True))
    def test_apply_patch_validate_patch_with_wrong_fetch_config(self, mock_subprocess_popen):
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = (json.dumps(self.all_config), 2)
        mock_subprocess_popen.return_value = mock_instance

        # Mock open to simulate file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(self.patch_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.apply_patch = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.patch_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertNotEqual(result.exit_code, 0, "Command should failed.")
                self.assertIn("Failed to apply patch", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.patch_file_path, 'r')

    @patch('generic_config_updater.generic_updater.ConfigReplacer.replace', MagicMock())
    def test_replace_multiasic(self):
        # Mock open to simulate file reading
        mock_replace_content = copy.deepcopy(self.all_config)
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_replace_content)), create=True) as mocked_open:
            # Mock GenericUpdater to avoid actual patch application
            with patch('config.main.GenericUpdater') as mock_generic_updater:
                mock_generic_updater.return_value.replace_all = MagicMock()

                print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
                # Invocation of the command with the CliRunner
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.replace_file_path],
                                            catch_exceptions=True)

                print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
                # Assertions and verifications
                self.assertEqual(result.exit_code, 0, "Command should succeed")
                self.assertIn("Config replaced successfully.", result.output)

                # Verify mocked_open was called as expected
                mocked_open.assert_called_with(self.replace_file_path, 'r')

    @patch('generic_config_updater.generic_updater.ConfigReplacer.replace', MagicMock())
    def test_replace_multiasic_missing_scope(self):
        # Mock open to simulate file reading
        mock_replace_content = copy.deepcopy(self.all_config)
        mock_replace_content.pop("asic0")
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_replace_content)), create=True):
            print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
            # Invocation of the command with the CliRunner
            result = self.runner.invoke(config.config.commands["replace"],
                                        [self.replace_file_path],
                                        catch_exceptions=True)

            print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
            # Assertions and verifications
            self.assertNotEqual(result.exit_code, 0, "Command should failed")
            self.assertIn("Failed to replace config", result.output)

    @patch('generic_config_updater.generic_updater.subprocess.Popen')
    @patch('generic_config_updater.generic_updater.Util.ensure_checkpoints_dir_exists', mock.Mock(return_value=True))
    @patch('generic_config_updater.generic_updater.Util.save_json_file', MagicMock())
    def test_checkpoint_multiasic(self, mock_subprocess_popen):
        allconfigs = copy.deepcopy(self.all_config)

        # Create mock instances for each subprocess call
        mock_instance_localhost = MagicMock()
        mock_instance_localhost.communicate.return_value = (json.dumps(allconfigs["localhost"]), 0)
        mock_instance_localhost.returncode = 0

        mock_instance_asic0 = MagicMock()
        mock_instance_asic0.communicate.return_value = (json.dumps(allconfigs["asic0"]), 0)
        mock_instance_asic0.returncode = 0

        mock_instance_asic1 = MagicMock()
        mock_instance_asic1.communicate.return_value = (json.dumps(allconfigs["asic1"]), 0)
        mock_instance_asic1.returncode = 0

        # Setup side effect to return different mock instances based on input arguments
        def side_effect(*args, **kwargs):
            if "asic" not in args[0]:
                return mock_instance_localhost
            elif "asic0" in args[0]:
                return mock_instance_asic0
            elif "asic1" in args[0]:
                return mock_instance_asic1
            else:
                return MagicMock()  # Default case

        mock_subprocess_popen.side_effect = side_effect

        checkpointname = "checkpointname"
        print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
        # Invocation of the command with the CliRunner
        result = self.runner.invoke(config.config.commands["checkpoint"],
                                    [checkpointname],
                                    catch_exceptions=True)

        print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
        # Assertions and verifications
        self.assertEqual(result.exit_code, 0, "Command should succeed")
        self.assertIn("Checkpoint created successfully.", result.output)

    @patch('generic_config_updater.generic_updater.Util.check_checkpoint_exists', mock.Mock(return_value=True))
    @patch('generic_config_updater.generic_updater.ConfigReplacer.replace', MagicMock())
    @patch('generic_config_updater.generic_updater.Util.get_checkpoint_content')
    def test_rollback_multiasic(self, mock_get_checkpoint_content):
        mock_get_checkpoint_content.return_value = copy.deepcopy(self.all_config)
        checkpointname = "checkpointname"
        print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
        # Invocation of the command with the CliRunner
        result = self.runner.invoke(config.config.commands["rollback"],
                                    [checkpointname],
                                    catch_exceptions=True)

        print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
        # Assertions and verifications
        self.assertEqual(result.exit_code, 0, "Command should succeed")
        self.assertIn("Config rolled back successfully.", result.output)

    @patch('generic_config_updater.generic_updater.Util.checkpoints_dir_exist', mock.Mock(return_value=True))
    @patch('generic_config_updater.generic_updater.Util.get_checkpoint_names',
           mock.Mock(return_value=["checkpointname"]))
    def test_list_checkpoint_multiasic(self):
        print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
        # Invocation of the command with the CliRunner
        result = self.runner.invoke(config.config.commands["list-checkpoints"],
                                    catch_exceptions=True)

        print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
        # Assertions and verifications
        self.assertEqual(result.exit_code, 0, "Command should succeed")
        self.assertIn("checkpointname", result.output)

    @patch('generic_config_updater.generic_updater.Util.delete_checkpoint', MagicMock())
    @patch('generic_config_updater.generic_updater.Util.check_checkpoint_exists', mock.Mock(return_value=True))
    def test_delete_checkpoint_multiasic(self):
        checkpointname = "checkpointname"
        # Mock GenericUpdater to avoid actual patch application
        with patch('config.main.GenericUpdater') as mock_generic_updater:
            mock_generic_updater.return_value.delete_checkpoint = MagicMock()

            print("Multi ASIC: {}".format(multi_asic.is_multi_asic()))
            # Invocation of the command with the CliRunner
            result = self.runner.invoke(config.config.commands["delete-checkpoint"],
                                        [checkpointname],
                                        catch_exceptions=True)

            print("Exit Code: {}, output: {}".format(result.exit_code, result.output))
            # Assertions and verifications
            self.assertEqual(result.exit_code, 0, "Command should succeed")
            self.assertIn("Checkpoint deleted successfully.", result.output)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_database_config()
