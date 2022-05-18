import os
import traceback

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

class TestStormControl(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_add_broadcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "broadcast", "10000"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_add_uucast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "unknown-unicast", "10000"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_add_umcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["add"], ["Ethernet0", "unknown-multicast", "10000"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_del_broadcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["del"], ["Ethernet0", "broadcast"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_del_uucast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["del"], ["Ethernet0", "unknown-unicast"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_del_umcast_storm(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["storm-control"].commands["del"], ["Ethernet0", "unknown-multicast"], obj = obj)
        print (result.exit_code)
        print (result.output)
        assert result.exit_code == 0

    def test_show_storm(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["storm-control"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
