import os
import sys
import pytest

import config.main as config
import tests.mock_tables.dbconnector

from click.testing import CliRunner
from utilities_common.db import Db

class TestConfigConsoleCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
    
    def test_console_add_exists(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, { "baud_rate" : "9600" })

        # add a console setting which the port exists
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1", '--baud', "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to add console port setting, which is already exists." in result.output
    
    def test_console_add_no_baud(self):
        runner = CliRunner()
        db = Db()

        # add a console setting without baud
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Missing option \"--baud\"" in result.output

    def test_console_add_name_conflict(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, { "remote_device" : "switch1" })

        # add a console setting which the device name has been used by other port
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1", '--baud', "9600", "--devicename", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Please enter a valid device name or remove the existing one" in result.output

    def test_console_add_success(self):
        runner = CliRunner()
        db = Db()

        # add a console setting without flow control option
        result = runner.invoke(config.config.commands["console"].commands["add"], ["0", '--baud', "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        # add a console setting with flow control option
        result = runner.invoke(config.config.commands["console"].commands["add"], ["1", '--baud', "9600", "--flowcontrol"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        # add a console setting with device name option
        result = runner.invoke(config.config.commands["console"].commands["add"], ["2", '--baud', "9600", "--devicename", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_console_del_non_exists(self):
        runner = CliRunner()
        db = Db()

        # remote a console port setting which is not exists
        result = runner.invoke(config.config.commands["console"].commands["del"], ["0"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to delete console port setting, which is not present." in result.output

    def test_console_del_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", { "baud_rate" : "9600" })

        # add a console setting which the port exists
        result = runner.invoke(config.config.commands["console"].commands["del"], ["1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_remote_device_name_non_exists(self):
        runner = CliRunner()
        db = Db()

        # trying to update a console line remote device configuration which is not exists
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["1", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to update console port setting, which is not present." in result.output

    def test_update_console_remote_device_name_conflict(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 1, { "baud": "9600" })
        db.cfgdb.set_entry("CONSOLE_PORT", 2, { "baud": "9600", "remote_device" : "switch1" })

        # trying to update a console line remote device configuration which is not exists
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["1", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Please enter a valid device name or remove the existing one" in result.output
    
    def test_update_console_remote_device_name_existing_and_same(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, { "remote_device" : "switch1" })

        # trying to update a console line remote device configuration which is existing and same with user provided value
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["2", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_remote_device_name_reset(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", 2, { "remote_device" : "switch1" })

        # trying to reset a console line remote device configuration which is not exists
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["2"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_remote_device_name_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", { "baud_rate" : "9600" })

        # trying to set a console line remote device configuration
        result = runner.invoke(config.config.commands["console"].commands["remote_device"], ["1", "switch1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_baud_no_change(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", { "baud_rate" : "9600" })

        # trying to set a console line baud which is same with existing one
        result = runner.invoke(config.config.commands["console"].commands["baud"], ["1", "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
    
    def test_update_console_baud_non_exists(self):
        runner = CliRunner()
        db = Db()

        # trying to set a console line baud which is not exists
        result = runner.invoke(config.config.commands["console"].commands["baud"], ["1", "9600"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to update console port setting, which is not present." in result.output
    
    def test_update_console_baud_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", { "baud_rate" : "9600" })

        # trying to set a console line baud
        result = runner.invoke(config.config.commands["console"].commands["baud"], ["1", "115200"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_flow_control_no_change(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", { "baud_rate" : "9600", "flow_control" : "0" })

        # trying to set a console line flow control option which is same with existing one
        result = runner.invoke(config.config.commands["console"].commands["flow_control"], ["disable", "1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

    def test_update_console_flow_control_non_exists(self):
        runner = CliRunner()
        db = Db()

        # trying to set a console line flow control option which is not exists
        result = runner.invoke(config.config.commands["console"].commands["flow_control"], ["enable", "1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code != 0
        assert "Trying to update console port setting, which is not present." in result.output

    def test_update_console_flow_control_success(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("CONSOLE_PORT", "1", { "baud_rate" : "9600", "flow_control" : "0" })

        # trying to set a console line flow control option
        result = runner.invoke(config.config.commands["console"].commands["flow_control"], ["enable", "1"], obj=db)
        print(result.exit_code)
        print(sys.stderr, result.output)
        assert result.exit_code == 0
