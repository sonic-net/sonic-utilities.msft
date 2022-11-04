import os
from click.testing import CliRunner
from utilities_common.db import Db
import show.main as show

class TestShowVnetRoutesAll(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_vnet_routes_all_basic(self):
        runner = CliRunner()
        db = Db()
        
        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['all'], [], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name    prefix    nexthop    interface
-----------  --------  ---------  -----------

vnet name        prefix                    endpoint                                     mac address    vni    status
---------------  ------------------------  -------------------------------------------  -------------  -----  --------
Vnet_v6_in_v6-0  fddd:a156:a251::a6:1/128  fddd:a100:a251::a10:1,fddd:a101:a251::a10:1                        active
test_v4_in_v4-0  160.162.191.1/32          100.251.7.1                                                        active
test_v4_in_v4-0  160.163.191.1/32          100.251.7.1                                                        active
test_v4_in_v4-0  160.164.191.1/32          100.251.7.1
"""
        assert result.output == expected_output

class TestShowVnetAdvertisedRoutesIPX(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_vnet_adv_routes_ip_basic(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['advertised-routes'], [], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Prefix                    Profile              Community Id
------------------------  -------------------  --------------
160.62.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.63.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.64.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
fccc:a250:a251::a6:1/128
fddd:a150:a251::a6:1/128  FROM_SDN_SLB_ROUTES  1234:1235
"""
        assert result.output == expected_output

    def test_show_vnet_adv_routes_ip_string(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['advertised-routes'], ['1234:1235'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Prefix                    Profile              Community Id
------------------------  -------------------  --------------
160.62.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.63.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.64.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
fddd:a150:a251::a6:1/128  FROM_SDN_SLB_ROUTES  1234:1235
"""
        assert result.output == expected_output

    def test_show_vnet_adv_routes_ipv6_Error(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['advertised-routes'], ['1230:1235'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Prefix    Profile    Community Id
--------  ---------  --------------
"""
        assert result.output == expected_output
