import os
import sys
import textwrap

import mock
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

import show.main as show


TEST_PLATFORM = "x86_64-mlnx_msn2700-r0"
TEST_HWSKU = "Mellanox-SN2700"
TEST_ASIC_TYPE = "mellanox"


"""
    Note: The following 'show platform' commands simply call other SONiC
    CLI utilities, so the unit tests for the other utilities are expected
    to cover testing their functionality:

        show platform fan
        show platform firmware
        show platform mlnx
        show platform psustatus
        show platform ssdhealth
        show platform syseeprom
        show platform temperature
"""

class TestShowPlatform(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    # Test 'show platform summary'
    def test_summary(self):
        expected_output = """\
            Platform: {}
            HwSKU: {}
            ASIC: {}
            """.format(TEST_PLATFORM, TEST_HWSKU, TEST_ASIC_TYPE)

        with mock.patch("show.main.get_hw_info_dict",
                        return_value={"platform": TEST_PLATFORM, "hwsku": TEST_HWSKU, "asic_type": TEST_ASIC_TYPE}):
            runner = CliRunner()
            result = runner.invoke(show.cli.commands["platform"].commands["summary"], [])
            assert result.output == textwrap.dedent(expected_output)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
