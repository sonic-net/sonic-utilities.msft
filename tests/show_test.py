import os
import sys
import pytest
import importlib
import show.main as show
import utilities_common.bgp_util as bgp_util
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
        cls._old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=cls.mock_run_bgp_command())

    def mock_run_bgp_command():
        return ""

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
        assert result.exit_code == 0
        assert mock_get_cmd_output.call_count == 1
        assert mock_get_cmd_output.call_args_list == [
            call(['sonic-cfggen', '-d', '--print-data'])]

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        bgp_util.run_bgp_command = cls._old_run_bgp_command
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"


class TestShowRunAllCommandsMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        cls._old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=cls.mock_run_bgp_command())
        # change to multi asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def mock_run_bgp_command():
        return ""

    def test_show_runningconfiguration_all_masic(self):
        def get_cmd_output_side_effect(*args, **kwargs):
            return "{}", 0
        with mock.patch('show.main.get_cmd_output',
                mock.MagicMock(side_effect=get_cmd_output_side_effect)) as mock_get_cmd_output:
            result = CliRunner().invoke(show.cli.commands['runningconfiguration'].commands['all'], [])
        assert result.exit_code == 0
        assert mock_get_cmd_output.call_count == 3
        assert mock_get_cmd_output.call_args_list == [
            call(['sonic-cfggen', '-d', '--print-data']),
            call(['sonic-cfggen', '-d', '--print-data', '-n', 'asic0']),
            call(['sonic-cfggen', '-d', '--print-data', '-n', 'asic1'])]

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        bgp_util.run_bgp_command = cls._old_run_bgp_command
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


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

def side_effect_subprocess_popen(*args, **kwargs):
    mock = MagicMock()
    if args[0] == "uptime":
        mock.stdout.read.return_value = "05:58:07 up 25 days"
    elif args[0].startswith("sudo docker images"):
        mock.stdout.read.return_value = "REPOSITORY   TAG"
    return mock

@patch('sonic_py_common.device_info.get_sonic_version_info', MagicMock(return_value={
        "build_version": "release-1.1-7d94c0c28",
        "sonic_os_version": "11",
        "debian_version": "11.6",
        "kernel_version": "5.10",
        "commit_id": "7d94c0c28",
        "build_date": "Wed Feb 15 06:17:08 UTC 2023",
        "built_by": "AzDevOps"}))
@patch('sonic_py_common.device_info.get_platform_info', MagicMock(return_value={
        "platform": "x86_64-kvm_x86_64-r0",
        "hwsku": "Force10-S6000",
        "asic_type": "vs",
        "asic_count": 1}))
@patch('sonic_py_common.device_info.get_chassis_info', MagicMock(return_value={
        "serial": "N/A",
        "model": "N/A",
        "revision": "N/A"}))
@patch('subprocess.Popen', MagicMock(side_effect=side_effect_subprocess_popen))
def test_show_version():
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["version"])
    assert "SONiC OS Version: 11" in result.output
