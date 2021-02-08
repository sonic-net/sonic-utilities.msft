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

    def test_config_buffer_profile_headroom(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'testprofile')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '18432', 'xoff': '32768', 'size': '18432'}

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

    def test_config_buffer_profile_add_no_xon(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test_profile_no_xon", "--xoff", "32768"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Xon is mandatory for non-dynamic profile" in result.output

    def test_config_buffer_profile_add_no_param(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"], ["no_parameter"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Either size information (xon, xoff, size) or dynamic_th needs to be provided" in result.output

    def test_config_buffer_profile_multiple_or_none_default_buffer_param_in_database(self):
        runner = CliRunner()
        db = Db()
        default_lossless_buffer_parameter = db.cfgdb.get_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE')

        # Remove all entries from DEFAULT_LOSSLESS_BUFFER_PARAMETER
        db.cfgdb.set_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE', None)
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Dynamic buffer calculation is enabled while no entry found in DEFAULT_LOSSLESS_BUFFER_PARAMETER table" in result.output

        # Insert AZURE and another entry into DEFAULT_LOSSLESS_BUFFER_PARAMETER
        db.cfgdb.set_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE', default_lossless_buffer_parameter)
        db.cfgdb.set_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'TEST', default_lossless_buffer_parameter)
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Multiple entries are found in DEFAULT_LOSSLESS_BUFFER_PARAMETER while no dynamic_th specified" in result.output

    def test_config_shp_size_negative(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["size"],
                               ["20000000"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Shared headroom pool must be less than mmu size" in result.output

    def test_config_shp_ratio(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["over-subscribe-ratio"],
                               ["4"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert db.cfgdb.get_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE') == {'default_dynamic_th': '0', 'over_subscribe_ratio': '4'}

    def test_config_shp_ratio_negative(self):
        runner = CliRunner()
        db = Db()
        port_number = len(db.cfgdb.get_table('PORT').keys())
        bad_oversubscribe_ratio = str(port_number + 1)
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["over-subscribe-ratio"],
                               [bad_oversubscribe_ratio], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid over-subscribe-ratio value {}. It should be in range [0, {}]".format(bad_oversubscribe_ratio, port_number) in result.output

    def test_config_buffer_profile_headroom_toggle_shp(self):
        runner = CliRunner()
        db = Db()

        # Disable SHP by setting over-subscribe-ratio to 0
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["over-subscribe-ratio"],
                               ["0"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE') == {'default_dynamic_th': '0', 'over_subscribe_ratio': '0'}

        # Size should equal xon + xoff
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test1", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test1')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '18432', 'xoff': '32768', 'size': '51200'}

        # Xoff should equal size - xon
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test2", "--dynamic_th", "3", "--xon", "18432", "--size", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '18432', 'xoff': '14336', 'size': '32768'}

        # Neither xon nor size is provided
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test_profile_neither_xoff_nor_size", "--xon", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Neither xoff nor size is provided" in result.output

        # Negative xoff
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["test_profile_negative_xoff", "--xon", "32768", "--size", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "The xoff must be greater than 0 while we got -14336 (calculated by: size 18432 - xon 32768)" in result.output

        # Set size
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["test2", "--dynamic_th", "3", "--size", "65536"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '18432', 'xoff': '14336', 'size': '65536'}

        # Set xon
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["test2", "--xon", "19456"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '19456', 'xoff': '14336', 'size': '65536'}

        # Set xoff
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["set"],
                               ["test2", "--xoff", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'test2')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '19456', 'xoff': '18432', 'size': '65536'}

        # Enable SHP by setting size
        result = runner.invoke(config.config.commands["buffer"].commands["shared-headroom-pool"].commands["size"],
                               ["200000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert db.cfgdb.get_entry('BUFFER_POOL', 'ingress_lossless_pool') == {'mode': 'dynamic', 'type': 'ingress', 'xoff': '200000'}

        # Size should equal xon
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile3", "--dynamic_th", "3", "--xon", "18432", "--xoff", "32768"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        profile = db.cfgdb.get_entry('BUFFER_PROFILE', 'testprofile3')
        assert profile == {'dynamic_th': '3', 'pool': '[BUFFER_POOL|ingress_lossless_pool]', 'xon': '18432', 'xoff': '32768', 'size': '18432'}

        # Negative test: xoff not provided
        result = runner.invoke(config.config.commands["buffer"].commands["profile"].commands["add"],
                               ["testprofile4", "--dynamic_th", "3", "--xon", "18432"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Shared headroom pool is enabled, xoff is mandatory for non-dynamic profile" in result.output

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
