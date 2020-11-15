import sys
import os
import traceback

from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

from .mock_tables import dbconnector

import show.main as show
import clear.main as clear

show_interfaces_counters_rif_output="""\
          IFACE    RX_OK    RX_BPS    RX_PPS    RX_ERR    TX_OK    TX_BPS    TX_PPS    TX_ERR
---------------  -------  --------  --------  --------  -------  --------  --------  --------
     Ethernet20        4       N/A       N/A         2        8       N/A       N/A         6
PortChannel0001      883       N/A       N/A         0        0       N/A       N/A         0
PortChannel0002      883       N/A       N/A         0        0       N/A       N/A         0
PortChannel0003        0       N/A       N/A         0        0       N/A       N/A         0
PortChannel0004      883       N/A       N/A         0        0       N/A       N/A         0
       Vlan1000        0       N/A       N/A         0        0       N/A       N/A         0
"""

class TestIntfstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    def test_no_param(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], [])
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_counters_rif_output

    def test_verbose(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], ["--verbose"])
        print(result.output)
        assert result.output.split('\n')[0] == "Running command: intfstat"

    def test_period(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], ["-p3"])
        print(result.output)
        assert result.output.split('\n')[0] == "The rates are calculated within 3 seconds period"

    def test_period_single_interface(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], ["Ethernet20", "-p3"])
        print(result.output)
        assert result.output.split('\n')[0] == "The rates are calculated within 3 seconds period"

    def test_single_intfs(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], ["Ethernet20"])
        expected = """Ethernet20
----------

        RX:
                 4 packets
                 3 bytes
                 2 error packets
              1128 error bytes
        TX:
                 8 packets
               754 bytes
                 6 error packets
                 5 error bytes
"""
        assert result.output == expected

    def test_clear_single_intfs(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["rifcounters"], ["Ethernet20"])
        print(result.stdout)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], ["Ethernet20"])
        expected = """Ethernet20
----------

        RX:
                 0 packets
                 0 bytes
                 0 error packets
                 0 error bytes
        TX:
                 0 packets
                 0 bytes
                 0 error packets
                 0 error bytes
"""
        # remove the counters snapshot
        show.run_command("intfstat -D")
        assert expected in result.output

    def test_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["rifcounters"], [])
        print(result.stdout)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], [])
        print(result.stdout)
        expected = ["Ethernet20        0  0.00 B/s    0.00/s         0        0  0.00 B/s    0.00/s         0",
                    "PortChannel0001        0  0.00 B/s    0.00/s         0        0  0.00 B/s    0.00/s         0",
                    "PortChannel0002        0  0.00 B/s    0.00/s         0        0  0.00 B/s    0.00/s         0",
                    "PortChannel0003        0  0.00 B/s    0.00/s         0        0  0.00 B/s    0.00/s         0",
                    "PortChannel0004        0  0.00 B/s    0.00/s         0        0  0.00 B/s    0.00/s         0",
                    "Vlan1000        0  0.00 B/s    0.00/s         0        0  0.00 B/s    0.00/s         0"]

        # remove the counters snapshot
        show.run_command("intfstat -D")
        for line in expected:
            assert line in result.output

    def test_alias_mode(self):
        os.environ["SONIC_CLI_IFACE_MODE"] = "alias"
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["counters"].commands["rif"], [])
        # no aliases for Portchannels and Vlans for now
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        interfaces = ["etp6", "PortChannel0001", "PortChannel0002", "PortChannel0003", "PortChannel0004", "Vlan1000"]
        result_lines = result.output.split('\n')
        #assert all interfaces are present in the output and in the correct order
        for i, interface in enumerate(interfaces):
            assert interface in result_lines[i+2]
        os.environ["SONIC_CLI_IFACE_MODE"] = "default"

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
