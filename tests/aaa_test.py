import imp
import os
import sys

from click.testing import CliRunner
from utilities_common.db import Db

import config.main as config
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import mock_tables.dbconnector

show_aaa_default_output="""\
AAA authentication login local (default)
AAA authentication failthrough False (default)

"""

show_aaa_radius_output="""\
AAA authentication login radius
AAA authentication failthrough False (default)

"""

show_aaa_radius_local_output="""\
AAA authentication login radius,local
AAA authentication failthrough False (default)

"""

config_aaa_empty_output="""\
"""

config_aaa_not_a_valid_command_output="""\
Not a valid command
"""

class TestAaa(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        imp.reload(config.main)
        import show.main
        imp.reload(show.main)

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

    def test_show_aaa_default(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["aaa"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_radius(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()
        db.cfgdb.delete_table("AAA")

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "radius"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        db.cfgdb.mod_entry("AAA", "authentication", {'login' : 'radius'})

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_radius_output

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        db.cfgdb.delete_table("AAA")

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_radius_local(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()
        db.cfgdb.delete_table("AAA")

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "radius", "local"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        db.cfgdb.mod_entry("AAA", "authentication", {'login' : 'radius,local'})

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_radius_local_output

        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "default"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_empty_output

        db.cfgdb.delete_table("AAA")

        result = runner.invoke(show.cli.commands["aaa"], [], obj=db)
        assert result.exit_code == 0
        assert result.output == show_aaa_default_output

    def test_config_aaa_radius_invalid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["aaa"],\
                               ["authentication", "login", "radius", "tacacs+"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_aaa_not_a_valid_command_output

