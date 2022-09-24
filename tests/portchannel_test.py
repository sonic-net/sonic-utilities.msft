import os
import pytest
import traceback
import mock

from click.testing import CliRunner
from jsonpatch import JsonPatchConflict

import config.main as config
import config.validated_config_db_connector as validated_config_db_connector
import show.main as show
from utilities_common.db import Db
from mock import patch

class TestPortChannel(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    @patch("config.main.is_portchannel_present_in_db", mock.Mock(return_value=False))
    @patch("config.validated_config_db_connector.validated_set_entry", mock.Mock(side_effect=ValueError))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_add_portchannel_with_invalid_name_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output
    
    def test_add_portchannel_with_invalid_name_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    @patch("config.validated_config_db_connector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_delete_nonexistent_portchannel_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "PortChan005 is not present" in result.output

    def test_delete_portchannel_with_invalid_name_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_add_existing_portchannel_again(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel which is already created
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 already exists!" in result.output

    def test_delete_non_existing_portchannel_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel which is not present
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChannel0005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    @pytest.mark.parametrize("fast_rate", ["False", "True", "false", "true"])
    def test_add_portchannel_with_fast_rate_adhoc_validation(self, fast_rate):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with fats rate
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0005", "--fast-rate", fast_rate], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @pytest.mark.parametrize("fast_rate", ["Fls", "tru"])
    def test_add_portchannel_with_invalid_fast_rate(self, fast_rate):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        
        # add a portchannel with invalid fats rate
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0005", "--fast-rate", fast_rate], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Invalid value for "--fast-rate"'  in result.output

    def test_add_portchannel_member_with_invalid_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChan005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_delete_portchannel_member_with_invalid_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChan005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_add_non_existing_portchannel_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with portchannel is not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_delete_non_existing_portchannel_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with portchannel is not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChannel0005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_add_portchannel_member_which_has_ipaddress(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which has ip-address
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error:  Ethernet0 has ip address configured" in result.output

    def test_add_portchannel_member_which_has_subintf(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which has ip-address
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet36"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        print(result.output)
        assert "Error:  Ethernet36 has subinterfaces configured" in result.output

    def test_add_portchannel_member_which_is_member_of_vlan(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which is member of Vlan
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet24"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet24 Interface configured as VLAN_MEMBER under vlan : Vlan2000" in result.output

    def test_add_portchannel_member_which_is_member_of_another_po(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which is member of another PO
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet116"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet116 Interface is already member of PortChannel0002 " in result.output

    def test_delete_portchannel_member_which_is_member_of_another_po(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with port which is member of another PO
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChannel1001", "Ethernet116"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet116 is not a member of portchannel PortChannel1001" in result.output

    def test_add_portchannel_member_with_acl_bindngs(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb, 'db_wrap':db, 'namespace':''}

        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0002", "Ethernet100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Port Ethernet100 is already bound to following ACL_TABLES:" in result.output

    def test_add_portchannel_member_with_pbh_bindngs(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb, 'db_wrap':db, 'namespace':''}

        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0002", "Ethernet60"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Port Ethernet60 is already bound to following PBH_TABLES:" in result.output

    def test_delete_portchannel_which_is_member_of_a_vlan(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # try to delete the portchannel when its member of a vlan
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChannel1001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "PortChannel1001 has vlan Vlan4000 configured, remove vlan membership to proceed" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
