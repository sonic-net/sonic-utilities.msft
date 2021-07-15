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

from generic_config_updater.generic_updater import ConfigFormat

import config.main as config

load_minigraph_command_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: pfcwd start_default
Running command: config qos reload --no-dynamic-buffer
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""

def mock_run_command_side_effect(*args, **kwargs):
    command = args[0]

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        return ''

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
            assert mock_run_command.call_count == 7

    def test_load_minigraph_with_port_config_bad_format(self, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:

            # Not in an array
            port_config = {"PORT": {"Ethernet0": {"admin_status": "up"}}}
            self.check_port_config(None, port_config, "Failed to load port_config.json, Error: Bad format: port_config is not an array")

            # No PORT table
            port_config = [{}]
            self.check_port_config(None, port_config, "Failed to load port_config.json, Error: Bad format: PORT table not exists")

    def test_load_minigraph_with_port_config_inconsistent_port(self, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            db = Db()
            db.cfgdb.set_entry("PORT", "Ethernet1", {"admin_status": "up"})
            port_config = [{"PORT": {"Eth1": {"admin_status": "up"}}}]
            self.check_port_config(db, port_config, "Failed to load port_config.json, Error: Port Eth1 is not defined in current device")

    def test_load_minigraph_with_port_config(self, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            db = Db()

            # From up to down
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "up"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "down"}}}]
            self.check_port_config(db, port_config, "config interface shutdown Ethernet0")

            # From down to up
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "down"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "up"}}}]
            self.check_port_config(db, port_config, "config interface startup Ethernet0")

    def check_port_config(self, db, port_config, expected_output):
        def read_json_file_side_effect(filename):
            return port_config
        with mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=read_json_file_side_effect)):
            def is_file_side_effect(filename):
                return True
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
        self.any_patch_as_json = [{"op":"remove", "path":"/PORT"}]
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
        expected_call_with_default_values = mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, False)
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
        expected_call_with_non_default_values = mock.call(self.any_patch, ConfigFormat.SONICYANG, True, True)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_patch_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["apply-patch"],
                                            [self.any_path,
                                             "--format", ConfigFormat.SONICYANG.name,
                                             "--dry-run",
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
            mock.call(self.any_patch, ConfigFormat.SONICYANG, False, False))
        self.validate_apply_patch_optional_parameter(
            ["--verbose"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, True, False))
        self.validate_apply_patch_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_patch, ConfigFormat.CONFIGDB, False, True))

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
        expected_call_with_default_values = mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, False)
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
        expected_call_with_non_default_values = mock.call(self.any_target_config, ConfigFormat.SONICYANG, True, True)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):
            with mock.patch('builtins.open', mock.mock_open(read_data=self.any_target_config_as_text)):

                # Act
                result = self.runner.invoke(config.config.commands["replace"],
                                            [self.any_path,
                                             "--format", ConfigFormat.SONICYANG.name,
                                             "--dry-run",
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
            mock.call(self.any_target_config, ConfigFormat.SONICYANG, False, False))
        self.validate_replace_optional_parameter(
            ["--verbose"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, True, False))
        self.validate_replace_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_target_config, ConfigFormat.CONFIGDB, False, True))

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
        expected_call_with_default_values = mock.call(self.any_checkpoint_name, False, False)
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
        expected_call_with_non_default_values = mock.call(self.any_checkpoint_name, True, True)
        mock_generic_updater = mock.Mock()
        with mock.patch('config.main.GenericUpdater', return_value=mock_generic_updater):

            # Act
            result = self.runner.invoke(config.config.commands["rollback"],
                                        [self.any_checkpoint_name,
                                            "--dry-run",
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
            mock.call(self.any_checkpoint_name, True, False))
        self.validate_rollback_optional_parameter(
            ["--dry-run"],
            mock.call(self.any_checkpoint_name, False, True))

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
