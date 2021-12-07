import os
import traceback

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

ERROR_STR = '''
Error: argument is not in pattern prefix [vrf <vrf_name>] <A.B.C.D/M> nexthop <[vrf <vrf_name>] <A.B.C.D>>|<dev <dev_name>>!
''' 
ERROR_STR_MISS_PREFIX = '''
Error: argument is incomplete, prefix not found!
'''
ERROR_STR_MISS_NEXTHOP = '''
Error: argument is incomplete, nexthop not found!
'''
ERROR_DEL_NONEXIST_KEY_STR = '''
Error: Route {} doesnt exist
'''
ERROR_DEL_NONEXIST_ENTRY_STR = '''
Error: Not found {} in {}
'''
ERROR_INVALID_IP = '''
Error: ip address is not valid.
'''
ERROR_INVALID_PORTCHANNEL = '''
Error: portchannel does not exist.
'''


class TestStaticRoutes(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_simple_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "1.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('1.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '1.2.3.4/32') == {'nexthop': '30.0.0.5', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix 1.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "1.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert not '1.2.3.4/32' in db.cfgdb.get_table('STATIC_ROUTE')

    def test_invalid_portchannel_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop PortChannel0101
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "1.2.3.4/32", "nexthop", "PortChannel0101"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_INVALID_PORTCHANNEL in result.output

    def test_static_route_invalid_prefix_ip(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 1.2.3/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "1.2.3/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_INVALID_IP in result.output
        
    def test_static_route_invalid_nexthop_ip(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop 30.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "1.2.3.4/32", "nexthop", "30.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_INVALID_IP in result.output

    def test_vrf_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix vrf Vrf-BLUE 2.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "vrf", "Vrf-BLUE", "2.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('Vrf-BLUE', '2.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'Vrf-BLUE|2.2.3.4/32') == {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix vrf Vrf-BLUE 2.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "vrf", "Vrf-BLUE", "2.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('Vrf-BLUE', '2.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_dest_vrf_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 3.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "3.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('3.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '3.2.3.4/32') == {'nexthop': '30.0.0.6', 'nexthop-vrf': 'Vrf-RED', 'blackhole': 'false', 'distance': '0', 'ifname': ''}

        # config route del prefix 3.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "3.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('3.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_multiple_nexthops_with_vrf_static_route(self):
            db = Db()
            runner = CliRunner()
            obj = {'config_db':db.cfgdb}

            ''' Add '''
            # config route add prefix 6.2.3.4/32 nexthop vrf Vrf-RED "30.0.0.6,30.0.0.7"
            result = runner.invoke(config.config.commands["route"].commands["add"], \
            ["prefix", "6.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6,30.0.0.7"], obj=obj)
            print(result.exit_code, result.output)
            assert ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
            assert db.cfgdb.get_entry('STATIC_ROUTE', '6.2.3.4/32') == {'nexthop': '30.0.0.6,30.0.0.7', 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ',', 'nexthop-vrf': 'Vrf-RED,Vrf-RED'}

            ''' Del '''
            # config route del prefix 6.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.7
            result = runner.invoke(config.config.commands["route"].commands["del"], \
            ["prefix", "6.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.7"], obj=obj)
            print(result.exit_code, result.output)
            assert ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
            assert db.cfgdb.get_entry('STATIC_ROUTE', '6.2.3.4/32') == {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': 'Vrf-RED'}

            # config route del prefix 6.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.6
            result = runner.invoke(config.config.commands["route"].commands["del"], \
            ["prefix", "6.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6"], obj=obj)
            print(result.exit_code, result.output)
            assert not ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_multiple_nexthops_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        ''' Add '''
        # config route add prefix 6.2.3.4/32 nexthop "30.0.0.6,30.0.0.7"
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.6,30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '6.2.3.4/32') == {'nexthop': '30.0.0.6,30.0.0.7', 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ',', 'nexthop-vrf': ','}

        # config route add prefix 6.2.3.4/32 nexthop 30.0.0.8
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.8"], obj=obj)
        print(result.exit_code, result.output)
        assert ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '6.2.3.4/32') == {'nexthop': '30.0.0.6,30.0.0.7,30.0.0.8', 'blackhole': 'false,false,false', 'distance': '0,0,0', 'ifname': ',,', 'nexthop-vrf': ',,'}

        ''' Del '''
        # config route del prefix 6.2.3.4/32 nexthop 30.0.0.8
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.8"], obj=obj)
        print(result.exit_code, result.output)
        assert ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '6.2.3.4/32') == {"nexthop": '30.0.0.6,30.0.0.7', 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ',', 'nexthop-vrf': ','}
        
        # config route del prefix 6.2.3.4/32 nexthop 30.0.0.7
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '6.2.3.4/32') == {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix 6.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_static_route_miss_prefix(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], ["nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_MISS_PREFIX in result.output

    def test_static_route_miss_nexthop(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 7.2.3.4/32
        result = runner.invoke(config.config.commands["route"].commands["add"], ["prefix", "7.2.3.4/32"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_MISS_NEXTHOP in result.output
        
    def test_static_route_ECMP_nexthop(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        ''' Add '''
        # config route add prefix 10.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '10.2.3.4/32') == {'nexthop': '30.0.0.5', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}
        
        # config route add prefix 10.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '10.2.3.4/32') == {'nexthop': '30.0.0.5,30.0.0.6', 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ',', 'nexthop-vrf': ','}

        ''' Del '''
        # config route del prefix 10.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '10.2.3.4/32') == {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}
        
        # config route del prefix 1.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_static_route_ECMP_nexthop_with_vrf(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        ''' Add '''
        # config route add prefix 11.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '11.2.3.4/32') == {'nexthop': '30.0.0.5', 'nexthop-vrf': 'Vrf-RED', 'blackhole': 'false', 'distance': '0', 'ifname': ''}
        
        # config route add prefix 11.2.3.4/32 nexthop vrf Vrf-BLUE 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-BLUE", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '11.2.3.4/32') == {"nexthop": "30.0.0.5,30.0.0.6", "nexthop-vrf": "Vrf-RED,Vrf-BLUE", 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ','}

        ''' Del '''
        # config route del prefix 11.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '11.2.3.4/32') == {"nexthop": "30.0.0.6", "nexthop-vrf": "Vrf-BLUE", 'blackhole': 'false', 'distance': '0', 'ifname': ''}
        
        # config route del prefix 11.2.3.4/32 nexthop vrf Vrf-BLUE 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-BLUE", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
   
    def test_static_route_ECMP_mixed_nextfop(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        ''' Add '''    
        # config route add prefix 12.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "12.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '12.2.3.4/32') == {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route add prefix 12.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.7
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "12.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '12.2.3.4/32') == {'nexthop': '30.0.0.6,30.0.0.7', 'nexthop-vrf': ',Vrf-RED', 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ','}

        ''' Del '''
        # config route del prefix 12.2.3.4/32 nexthop vrf Vrf-Red 30.0.0.7
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "12.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '12.2.3.4/32') == {'nexthop': '30.0.0.6', 'nexthop-vrf': '', 'ifname': '', 'blackhole': 'false', 'distance': '0'}
        
        # config route del prefix 12.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "12.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
      
    def test_del_nonexist_key_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route del prefix 10.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "17.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_DEL_NONEXIST_KEY_STR.format("17.2.3.4/32") in result.output
        
    def test_del_nonexist_entry_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 13.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "13.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('13.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '13.2.3.4/32') == {'nexthop': '30.0.0.5', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix 13.2.3.4/32 nexthop 30.0.0.6 <- nh ip that doesnt exist
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "13.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_DEL_NONEXIST_ENTRY_STR.format(('30.0.0.6', '', ''), "13.2.3.4/32") in result.output

        # config route del prefix 13.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "13.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert not '13.2.3.4/32' in db.cfgdb.get_table('STATIC_ROUTE')

    def test_del_entire_ECMP_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # config route add prefix 14.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "14.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('14.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '14.2.3.4/32') == {'nexthop': '30.0.0.5', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route add prefix 14.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], \
        ["prefix", "14.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('14.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', '14.2.3.4/32') == {'nexthop': '30.0.0.5,30.0.0.6', 'nexthop-vrf': ',', 'ifname': ',', 'blackhole': 'false,false', 'distance': '0,0'}

        # config route del prefix 14.2.3.4/32
        result = runner.invoke(config.config.commands["route"].commands["del"], ["prefix", "14.2.3.4/32"], obj=obj)
        print(result.exit_code, result.output)
        assert not '14.2.3.4/32' in db.cfgdb.get_table('STATIC_ROUTE')

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN") 

