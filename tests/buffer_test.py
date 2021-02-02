import imp
import os
import sys
from click.testing import CliRunner
from unittest import TestCase
from swsscommon.swsscommon import ConfigDBConnector

from .mock_tables import dbconnector

import show.main as show
import config.main as config
from utilities_common.db import Db

from .buffer_input.buffer_test_vectors import *

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

class TestBuffer(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def setUp(self):
        self.runner = CliRunner()
        self.config_db = ConfigDBConnector()
        self.config_db.connect()
        self.obj = {'db': self.config_db}

    def test_config_buffer_profile_headroom(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'testprofile')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '18432', 'xoff': '32768', 'size': '51200'}

    def test_config_buffer_profile_dynamic_th(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--dynamic_th", "3"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'testprofile')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'headroom_type': 'dynamic'}

    def test_config_buffer_profile_add_existing(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["headroom_profile", "--dynamic_th", "3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Profile headroom_profile already exist" in result.output

    def test_config_buffer_profile_set_non_existing(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["non_existing_profile", "--dynamic_th", "3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Profile non_existing_profile doesn't exist" in result.output

    def test_config_buffer_profile_add_headroom_to_dynamic_profile(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["alpha_profile", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Can't change profile alpha_profile from dynamically calculating headroom to non-dynamically one" in result.output

    def test_show_buffer_configuration(self):
        self.executor(testData['show_buffer_configuration'])

    def test_show_buffer_information(self):
        self.executor(testData['show_buffer_information'])

    def executor(self, testcase):
        runner = CliRunner()

        for input in testcase:
            exec_cmd = show.cli.commands[input['cmd'][0]].commands[input['cmd'][1]]

            result = runner.invoke(exec_cmd, [], catch_exceptions=True)

            print(result.exit_code)
            print(result.output)
            if result.exception:
                print(result.exception)

            assert result.exit_code == 0
            assert result.output == input['rc_output']

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
