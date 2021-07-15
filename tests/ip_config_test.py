import os
import traceback
from unittest import mock

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

ERROR_MSG = '''
Error: ip address or mask is not valid.
'''

class TestConfigIP(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        
    ''' Tests for IPv4  '''
      
    def test_add_del_interface_valid_ipv4(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')
        
        # config int ip remove Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"], ["Ethernet64", "10.10.10.1/24"], obj=obj)        
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')
    
    def test_add_interface_invalid_ipv4(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet64 10000.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet64", "10000.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ERROR_MSG in result.output
        
    def test_add_interface_ipv4_invalid_mask(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet64 10.10.10.1/37
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet64", "10.10.10.1/37"], obj=obj)        
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ERROR_MSG in result.output

    def test_add_interface_ipv4_with_leading_zeros(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet68 10.10.10.002/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet68", "10.10.10.002/24"], obj=obj)        
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ERROR_MSG in result.output

    '''  Tests for IPv6 '''
    
    def test_add_del_interface_valid_ipv6(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet72 2001:1db8:11a3:19d7:1f34:8a2e:17a0:765d/34
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet72", "2001:1db8:11a3:19d7:1f34:8a2e:17a0:765d/34"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet72', '2001:1db8:11a3:19d7:1f34:8a2e:17a0:765d/34') in db.cfgdb.get_table('INTERFACE')
        
        # config int ip remove Ethernet72 2001:1db8:11a3:19d7:1f34:8a2e:17a0:765d/34
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"], ["Ethernet72", "2001:1db8:11a3:19d7:1f34:8a2e:17a0:765d/34"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ('Ethernet72', '2001:1db8:11a3:19d7:1f34:8a2e:17a0:765d/34') not in db.cfgdb.get_table('INTERFACE')
    
    def test_add_interface_invalid_ipv6(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet72 20001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/34
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet72", "20001:0db8:11a3:19d7:1f34:8a2e:17a0:765d/34"], obj=obj)        
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ERROR_MSG in result.output
        
    def test_add_interface_ipv6_invalid_mask(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet72 2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/200
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet72", "2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/200"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ERROR_MSG in result.output

    def test_add_del_interface_ipv6_with_leading_zeros(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet68 2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/34
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet68", "2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/34"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet68', '2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/34') in db.cfgdb.get_table('INTERFACE')
        
        # config int ip remove Ethernet68 2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/34
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"], ["Ethernet68", "2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/34"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ('Ethernet68', '2001:0db8:11a3:09d7:1f34:8a2e:07a0:765d/34') not in db.cfgdb.get_table('INTERFACE')
        
    def test_add_del_interface_shortened_ipv6_with_leading_zeros(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # config int ip add Ethernet68 3000::001/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Ethernet68", "3000::001/64"], obj=obj)        
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet68', '3000::001/64') in db.cfgdb.get_table('INTERFACE')
        
        # config int ip remove Ethernet68 3000::001/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"], ["Ethernet68", "3000::001/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ('Ethernet68', '3000::001/64') not in db.cfgdb.get_table('INTERFACE')
    
    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
