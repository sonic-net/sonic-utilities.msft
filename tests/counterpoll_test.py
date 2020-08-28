import sys
import os
import time
import pytest
import click
import swsssdk
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import mock_tables.dbconnector
import counterpoll.main as counterpoll

expected_counterpoll_show = """Type                    Interval (in ms)  Status
--------------------  ------------------  --------
QUEUE_STAT                         10000  enable
PORT_STAT                           1000  enable
PORT_BUFFER_DROP                   60000  enable
QUEUE_WATERMARK_STAT               10000  enable
PG_WATERMARK_STAT                  10000  enable
"""

class TestCounterpoll(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show(self):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["show"], [])
        print(result.output)
        assert result.output == expected_counterpoll_show

    def test_port_buffer_drop_interval(self):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["port-buffer-drop"].commands["interval"], ["30000"])
        print(result.output)
        assert result.exit_code == 0

    def test_port_buffer_drop_interval_too_short(self):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["port-buffer-drop"].commands["interval"], ["1000"])
        print(result.output)
        expected = "Invalid value for 'POLL_INTERVAL': 1000 is not in the valid range of 30000 to 300000."
        assert result.exit_code == 2
        assert expected in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
