import filecmp
import imp
import os
import traceback
import json
from unittest import mock

import click
from click.testing import CliRunner

from sonic_py_common import device_info
from utilities_common.db import Db

load_minigraph_command_output="""\
Executing stop of service telemetry...
Executing stop of service swss...
Executing stop of service lldp...
Executing stop of service pmon...
Executing stop of service bgp...
Executing stop of service hostcfgd...
Executing stop of service nat...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: pfcwd start_default
Running command: config qos reload --no-dynamic-buffer
Executing reset-failed of service bgp...
Executing reset-failed of service dhcp_relay...
Executing reset-failed of service hostcfgd...
Executing reset-failed of service hostname-config...
Executing reset-failed of service interfaces-config...
Executing reset-failed of service lldp...
Executing reset-failed of service nat...
Executing reset-failed of service ntp-config...
Executing reset-failed of service pmon...
Executing reset-failed of service radv...
Executing reset-failed of service rsyslog-config...
Executing reset-failed of service snmp...
Executing reset-failed of service swss...
Executing reset-failed of service syncd...
Executing reset-failed of service teamd...
Executing reset-failed of service telemetry...
Executing restart of service hostname-config...
Executing restart of service interfaces-config...
Executing restart of service ntp-config...
Executing restart of service rsyslog-config...
Executing restart of service swss...
Executing restart of service bgp...
Executing restart of service pmon...
Executing restart of service lldp...
Executing restart of service hostcfgd...
Executing restart of service nat...
Executing restart of service telemetry...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""

def mock_run_command_side_effect(*args, **kwargs):
    command = args[0]

    if 'display_cmd' in kwargs and kwargs['display_cmd'] == True:
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))


class TestLoadMinigraph(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        imp.reload(config.main)

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
            assert mock_run_command.call_count == 38

    def test_load_minigraph_with_disabled_telemetry(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            db = Db()
            runner = CliRunner()
            result = runner.invoke(config.config.commands["feature"].commands["state"], ["telemetry", "disabled"], obj=db)
            assert result.exit_code == 0
            result = runner.invoke(show.cli.commands["feature"].commands["status"], ["telemetry"], obj=db)
            print(result.output)
            assert result.exit_code == 0
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert "telemetry" not in result.output
            assert mock_run_command.call_count == 35

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
        imp.reload(config.main)

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
        imp.reload(config.main)

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
        imp.reload(mock_single_asic)
        dbconnector.load_namespace_config()
