import filecmp
import importlib
import os
import traceback
import json
import jsonpatch
import sys
import unittest
from unittest import mock

import click
from click.testing import CliRunner

from sonic_py_common import device_info
from utilities_common.db import Db
from utilities_common.general import load_module_from_source

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


load_minigraph_command_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer
Running command: pfcwd start_default
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""


RELOAD_CONFIG_DB_OUTPUT = """\
Running command: rm -rf /tmp/dropstat-*
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_YANG_CFG_OUTPUT = """\
Running command: rm -rf /tmp/dropstat-*
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen  -Y /tmp/config.json  --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

RELOAD_MASIC_CONFIG_DB_OUTPUT = """\
Running command: rm -rf /tmp/dropstat-*
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  --write-to-db
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  -n asic0  --write-to-db
Running command: /usr/local/bin/sonic-cfggen  -j /tmp/config.json  -n asic1  --write-to-db
Restarting SONiC target ...
Reloading Monit configuration ...
"""

reload_config_with_sys_info_command_output="""\
Running command: rm -rf /tmp/dropstat-*
Running command: /usr/local/bin/sonic-cfggen -H -k Seastone-DX010-25-50 --write-to-db"""

def mock_run_command_side_effect(*args, **kwargs):
    command = args[0]

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer'
        elif command == "systemctl list-dependencies --plain sonic.target | sed '1d'":
            return 'swss'
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled'
        else:
            return ''


# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')


class TestConfigReload(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

        import config.main
        importlib.reload(config.main)

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

            assert "\n".join([l.rstrip() for l in result.output.split('\n')][:2]) == reload_config_with_sys_info_command_output

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

    def test_load_minigraph_with_port_config_inconsistent_port(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            db = Db()
            db.cfgdb.set_entry("PORT", "Ethernet1", {"admin_status": "up"})
            port_config = [{"PORT": {"Eth1": {"admin_status": "up"}}}]
            self.check_port_config(db, config, port_config, "Failed to load port_config.json, Error: Port Eth1 is not defined in current device")

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

    def test_load_minigraph_with_golden_config(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            db = Db()
            golden_config = {}
            self.check_golden_config(db, config, golden_config,
                                     "config override-config-table /etc/sonic/golden_config_db.json")

    def check_golden_config(self, db, config, golden_config, expected_output):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False
        with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert expected_output in result.output

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
        open(cls.dummy_cfg_file, 'w').close()

    def test_reload_config(self, get_cmd_module, setup_single_broadcom_asic):
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

    def test_reload_config_masic(self, get_cmd_module, setup_multi_broadcom_masic):
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
                                    [self.dummy_cfg_file, '-y','-f' ,'-t', 'config_yang'])

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

    def test_apply_patch__no_params__get_required_params_error_msg(self):
        # Arrange
        unexpected_exit_code = 0
        expected_output = "Error: Missing argument \"PATCH_FILE_PATH\""

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"])

        # Assert
        self.assertNotEqual(unexpected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

    def test_apply_patch__help__gets_help_msg(self):
        # Arrange
        expected_exit_code = 0
        expected_output = "Options:" # this indicates the options are listed

        # Act
        result = self.runner.invoke(config.config.commands["apply-patch"], ['--help'])

        # Assert
        self.assertEqual(expected_exit_code, result.exit_code)
        self.assertTrue(expected_output in result.output)

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
