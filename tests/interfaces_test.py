import os

from click.testing import CliRunner

import show.main as show

show_interfaces_alias_output="""\
Name         Alias
-----------  -------
Ethernet0    etp1
Ethernet4    etp2
Ethernet8    etp3
Ethernet12   etp4
Ethernet16   etp5
Ethernet20   etp6
Ethernet24   etp7
Ethernet28   etp8
Ethernet32   etp9
Ethernet36   etp10
Ethernet40   etp11
Ethernet44   etp12
Ethernet48   etp13
Ethernet52   etp14
Ethernet56   etp15
Ethernet60   etp16
Ethernet64   etp17
Ethernet68   etp18
Ethernet72   etp19
Ethernet76   etp20
Ethernet80   etp21
Ethernet84   etp22
Ethernet88   etp23
Ethernet92   etp24
Ethernet96   etp25
Ethernet100  etp26
Ethernet104  etp27
Ethernet108  etp28
Ethernet112  etp29
Ethernet116  etp30
Ethernet120  etp31
Ethernet124  etp32
"""

show_interfaces_alias_Ethernet0_output="""\
Name       Alias
---------  -------
Ethernet0  etp1
"""

show_interfaces_neighbor_expected_output="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
Ethernet112  ARISTA01T1  Ethernet1       None                10.250.0.51     LeafRouter
Ethernet116  ARISTA02T1  Ethernet1       None                10.250.0.52     LeafRouter
Ethernet120  ARISTA03T1  Ethernet1       None                10.250.0.53     LeafRouter
Ethernet124  ARISTA04T1  Ethernet1       None                10.250.0.54     LeafRouter
"""

show_interfaces_neighbor_expected_output_Ethernet112="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
Ethernet112  ARISTA01T1  Ethernet1       None                10.250.0.51     LeafRouter
"""

show_interfaces_neighbor_expected_output_etp29="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
etp29        ARISTA01T1  Ethernet1       None                10.250.0.51     LeafRouter
"""

class TestInterfaces(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_show_interfaces(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_show_interfaces_alias(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_alias_output

    def test_show_interfaces_alias_Ethernet0(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_alias_Ethernet0_output

    def test_show_interfaces_alias_etp1(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["etp1"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_alias_Ethernet0_output

    def test_show_interfaces_alias_invalid_name(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["Ethernet3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid interface name Ethernet3" in result.output

    def test_show_interfaces_naming_mode_default(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["naming_mode"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.rstrip() == "default"

    def test_show_interfaces_naming_mode_alias(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["naming_mode"], [])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.rstrip() == "alias"

    def test_show_interfaces_neighbor_expected(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], [])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output

    def test_show_interfaces_neighbor_expected_Ethernet112(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["Ethernet112"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output_Ethernet112

    def test_show_interfaces_neighbor_expected_etp29(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["etp29"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output_etp29

    def test_show_interfaces_neighbor_expected_Ethernet0(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output.rstrip() == "No neighbor information available for interface Ethernet0"

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
