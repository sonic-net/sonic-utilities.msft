import os
import sys
import pytest
import show.main as show
from click.testing import CliRunner
from unittest import mock
from unittest.mock import call, MagicMock, patch

EXPECTED_BASE_COMMAND = 'sudo '

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestShowRunAllCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_runningconfiguration_all_json_loads_failure(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "", 0
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert result.exit_code != 0

    def test_show_runningconfiguration_all_get_cmd_ouput_failure(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "{}", 2
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert result.exit_code != 0

    def test_show_runningconfiguration_all(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "{}", 0
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert mock_get_cmd_output.call_count == 2
        assert mock_get_cmd_output.call_args_list == [
            call(['sonic-cfggen', '-d', '--print-data']),
            call(['rvtysh', '-c', 'show running-config'])]

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

@patch('show.main.run_command')
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log/syslog'),
            (['xcvrd'], "cat /var/log/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log/syslog | tail -10'),
            (['-f'], 'tail -F /var/log/syslog'),
        ]
)
def test_show_logging_default(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.isfile', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log/syslog.1 /var/log/syslog'),
            (['xcvrd'], "cat /var/log/syslog.1 /var/log/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log/syslog.1 /var/log/syslog | tail -10'),
            (['-f'], 'tail -F /var/log/syslog'),
        ]
)
def test_show_logging_syslog_1(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.exists', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log.tmpfs/syslog'),
            (['xcvrd'], "cat /var/log.tmpfs/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log.tmpfs/syslog | tail -10'),
            (['-f'], 'tail -F /var/log.tmpfs/syslog'),
        ]
)
def test_show_logging_tmpfs(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.isfile', MagicMock(return_value=True))
@patch('os.path.exists', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog'),
            (['xcvrd'], "cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog | tail -10'),
            (['-f'], 'tail -F /var/log.tmpfs/syslog'),
        ]
)
def test_show_logging_tmpfs_syslog_1(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)
