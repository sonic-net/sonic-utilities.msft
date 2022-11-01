import os
import sys
from click.testing import CliRunner
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.db import Db

import config.main as config
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "vrf_input")

class TestShowVrf(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_vrf_show(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()
        expected_output = """\
VRF     Interfaces
------  ---------------
Vrf1
Vrf101  Ethernet0.10
Vrf102  Eth36.10
        PortChannel0002
        Vlan40
Vrf103  Ethernet4
        Loopback0
        Po0002.101
"""
       
        result = runner.invoke(show.cli.commands['vrf'], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

    def test_vrf_bind_unbind(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()
        expected_output = """\
VRF     Interfaces
------  ---------------
Vrf1
Vrf101  Ethernet0.10
Vrf102  Eth36.10
        PortChannel0002
        Vlan40
Vrf103  Ethernet4
        Loopback0
        Po0002.101
"""
       
        result = runner.invoke(show.cli.commands['vrf'], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

        obj = {'config_db':db.cfgdb}

        expected_output_unbind = "Interface Ethernet4 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Ethernet4"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Ethernet4' not in db.cfgdb.get_table('INTERFACE')
        assert result.output == expected_output_unbind
        
        expected_output_unbind = "Interface Loopback0 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Loopback0"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Loopback0' not in db.cfgdb.get_table('LOOPBACK_INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Vlan40 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Vlan40"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Vlan40' not in db.cfgdb.get_table('VLAN_INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface PortChannel0002 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["PortChannel0002"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'PortChannel002' not in db.cfgdb.get_table('PORTCHANNEL_INTERFACE')
        assert result.output == expected_output_unbind
        
        expected_output_unbind = "Interface Eth36.10 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Eth36.10"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vrf_name', 'Vrf102') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth36.10']
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Ethernet0.10 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Ethernet0.10"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vrf_name', 'Vrf101') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.10']
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Po0002.101 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Po0002.101"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vrf_name', 'Vrf103') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0002.101']
        assert result.output == expected_output_unbind

        vrf_obj = {'config_db':db.cfgdb, 'namespace':db.db.namespace}
        
        expected_output_bind = "Interface Ethernet0 IP disabled and address(es) removed due to binding VRF Vrf1.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Ethernet0", "Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf1') in db.cfgdb.get_table('INTERFACE')['Ethernet0']['vrf_name']

        expected_output_bind = "Interface Loopback0 IP disabled and address(es) removed due to binding VRF Vrf101.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Loopback0", "Vrf101"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf101') in db.cfgdb.get_table('LOOPBACK_INTERFACE')['Loopback0']['vrf_name']

        expected_output_bind = "Interface Vlan40 IP disabled and address(es) removed due to binding VRF Vrf101.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Vlan40", "Vrf101"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf101') in db.cfgdb.get_table('VLAN_INTERFACE')['Vlan40']['vrf_name']

        expected_output_bind = "Interface PortChannel0002 IP disabled and address(es) removed due to binding VRF Vrf101.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["PortChannel0002", "Vrf101"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf101') in db.cfgdb.get_table('PORTCHANNEL_INTERFACE')['PortChannel0002']['vrf_name']

        expected_output_bind = "Interface Eth36.10 IP disabled and address(es) removed due to binding VRF Vrf102.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Eth36.10", "Vrf102"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth36.10']['vrf_name']

        expected_output_bind = "Interface Ethernet0.10 IP disabled and address(es) removed due to binding VRF Vrf103.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Ethernet0.10", "Vrf103"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf103') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.10']['vrf_name']

        expected_output_bind = "Interface Po0002.101 IP disabled and address(es) removed due to binding VRF Vrf1.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Po0002.101", "Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf1') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0002.101']['vrf_name']

        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        expected_output = """\
VRF     Interfaces
------  ---------------
Vrf1
Vrf101  Ethernet0.10
Vrf102  Eth36.10
        PortChannel0002
        Vlan40
Vrf103  Ethernet4
        Loopback0
        Po0002.101
"""
       
        result = runner.invoke(show.cli.commands['vrf'], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

    def test_vrf_del(self):
        runner = CliRunner()
        db = Db()
        vrf_obj = {'config_db':db.cfgdb, 'namespace':db.db.namespace}
        
        expected_output_del = "VRF Vrf1 deleted and all associated IP addresses removed.\n"
        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_del
        assert ('Vrf1') not in db.cfgdb.get_table('VRF')

        expected_output_del = "VRF Vrf101 deleted and all associated IP addresses removed.\n"
        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["Vrf101"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_del
        assert ('Vrf101') not in db.cfgdb.get_table('VRF')

        expected_output_del = "VRF Vrf102 deleted and all associated IP addresses removed.\n"
        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["Vrf102"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_del
        assert ('Vrf102') not in db.cfgdb.get_table('VRF')

        expected_output_del = "VRF Vrf103 deleted and all associated IP addresses removed.\n"
        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["Vrf103"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_del
        assert ('Vrf103') not in db.cfgdb.get_table('VRF')
