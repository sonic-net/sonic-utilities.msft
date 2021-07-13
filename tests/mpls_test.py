import os
import sys
import traceback
from unittest import mock

from click.testing import CliRunner

from .mock_tables import dbconnector

import config.main as config
import show.main as show
from utilities_common.db import Db

show_interfaces_mpls_output="""\
Interface     MPLS State
------------  ------------
Ethernet2     enable
Ethernet4     disable
Ethernet8     disable
Ethernet16    disable
Loopback0     disable
PortChannel2  disable
Vlan2         enable
"""

show_interfaces_mpls_specific_output="""\
Interface    MPLS State
-----------  ------------
Ethernet2    enable
"""

modules_path = os.path.join(os.path.dirname(__file__), "..")
test_path = os.path.join(modules_path, "tests")
sys.path.insert(0, modules_path)
sys.path.insert(0, test_path)
mock_db_path = os.path.join(test_path, "mpls_input")


class TestMpls(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    def test_config_mpls_add(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["mpls"].commands["add"], ["Ethernet4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("INTERFACE", "Ethernet4") == {"mpls": "enable"}

    def test_config_mpls_remove(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].commands["mpls"].commands["remove"], ["Ethernet4"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("INTERFACE", "Ethernet4") == {"mpls": "disable"}

    def test_show_interfaces_mpls(self):
        jsonfile = os.path.join(mock_db_path, 'appl_db')
        dbconnector.dedicated_dbs['APPL_DB'] = jsonfile

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["mpls"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_output

    def test_show_interfaces_mpls_specific(self):
        jsonfile = os.path.join(mock_db_path, 'appl_db')
        dbconnector.dedicated_dbs['APPL_DB'] = jsonfile

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["mpls"], ["Ethernet2"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_mpls_specific_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dbconnector.dedicated_dbs['APPL_DB'] = None
