import os
import sys
import textwrap
from unittest import mock

import pytest
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)
import show.main as show


@pytest.fixture(scope='class')
def config_env():
    os.environ["UTILITIES_UNIT_TESTING"] = "1"

    yield

    os.environ["UTILITIES_UNIT_TESTING"] = "0"


@pytest.mark.usefixtures('config_env')
class TestShowPlatform(object):
    TEST_PLATFORM = "x86_64-mlnx_msn2700-r0"
    TEST_HWSKU = "Mellanox-SN2700"
    TEST_ASIC_TYPE = "mellanox"

    # Test 'show platform summary'
    def test_summary(self):
        expected_output = """\
            Platform: {}
            HwSKU: {}
            ASIC: {}
            """.format(self.TEST_PLATFORM, self.TEST_HWSKU, self.TEST_ASIC_TYPE)

        with mock.patch("show.platform.get_hw_info_dict",
                        return_value={"platform": self.TEST_PLATFORM, "hwsku": self.TEST_HWSKU, "asic_type": self.TEST_ASIC_TYPE}):
            result = CliRunner().invoke(show.cli.commands["platform"].commands["summary"], [])
            assert result.output == textwrap.dedent(expected_output)


class TestShowPlatformPsu(object):
    """
        Note: `show platform psustatus` simply calls the `psushow` utility and
        passes a variety of options. Here we test that the utility is called
        with the appropriate option(s). The functionality of the underlying
        `psushow` utility is expected to be tested by a separate suite of unit tests
    """
    def test_all_psus(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], [])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with('psushow -s', display_cmd=False)

    def test_all_psus_json(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--json'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with('psushow -s -j', display_cmd=False)

    def test_single_psu(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--index=1'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with('psushow -s -i 1', display_cmd=False)

    def test_single_psu_json(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--index=1', '--json'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with('psushow -s -i 1 -j', display_cmd=False)

    def test_verbose(self):
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            CliRunner().invoke(show.cli.commands['platform'].commands['psustatus'], ['--verbose'])
        assert mock_run_command.call_count == 1
        mock_run_command.assert_called_with('psushow -s', display_cmd=True)
