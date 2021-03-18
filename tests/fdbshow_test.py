import os
from click.testing import CliRunner
import pytest

import show.main as show
from .utils import get_result_and_return_code
import subprocess

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

show_mac_output_with_def_vlan = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       2  11:22:33:44:55:66  Ethernet0  Dynamic
    2       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 2
"""

show_mac_output = """\
  No.    Vlan  MacAddress         Port           Type
-----  ------  -----------------  -------------  -------
    1       2  11:22:33:44:55:66  Ethernet0      Dynamic
    2       3  11:22:33:66:55:44  Ethernet4      Static
    3       4  66:55:44:33:22:11  Ethernet0      Dynamic
    4       4  77:66:44:33:22:11  1000000000fff  Dynamic
    5       5  77:66:55:44:22:11  Ethernet4      Dynamic
Total number of entries 5
"""

show_mac__port_vlan_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       2  11:22:33:44:55:66  Ethernet0  Dynamic
Total number of entries 1
"""

show_mac_no_results_output = """\
No.    Vlan    MacAddress    Port    Type
-----  ------  ------------  ------  ------
Total number of entries 0
"""

show_mac_no_port_output = """\
'Ethernet20' is not in list
"""

show_mac_no_vlan_output = """\
123 is not in list
"""


class TestFdbshow():
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        yield
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    @pytest.fixture(scope="function", autouse=True)
    def setUp(self):
        self.runner = CliRunner()
        yield
        del os.environ["FDBSHOW_MOCK"]

    def set_mock_variant(self, variant: str):
        os.environ["FDBSHOW_MOCK"] = variant

    def test_show_mac_def_vlan(self):
        self.set_mock_variant("2")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_output_with_def_vlan

        return_code, result = get_result_and_return_code('fdbshow')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_output_with_def_vlan

    def test_show_mac(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_output

        return_code, result = get_result_and_return_code('fdbshow')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_output

    def test_show_mac_port_vlan(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-p Ethernet0 -v 2")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__port_vlan_output

        return_code, result = get_result_and_return_code('fdbshow -p Ethernet0 -v 2')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__port_vlan_output

    def test_show_mac_no_port(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-p Ethernet20")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_mac_no_port_output

        return_code, result = get_result_and_return_code('fdbshow -p Ethernet20')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == show_mac_no_port_output.strip("\n")

    def test_show_mac_no_vlan(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-v 123")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_mac_no_vlan_output

        return_code, result = get_result_and_return_code('fdbshow -v 123')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == show_mac_no_vlan_output.strip("\n")

    def test_show_mac_no_fdb(self):
        self.set_mock_variant("3")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code('fdbshow')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_mac_no_bridge(self):
        self.set_mock_variant("4")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code('fdbshow')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_fetch_except(self):
        self.set_mock_variant("5")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert "Failed to get Vlan id for bvid oid:0x260000000007c7" in result.output

        try:
            output = subprocess.check_output(
                'fdbshow', stderr=subprocess.STDOUT, shell=True, text=True)
        except subprocess.CalledProcessError as e:
            return_code = e.returncode
            output = e.output

        print("return_code: {}".format(return_code))
        print("result = {}".format(output))
        assert return_code == 1
        assert "Failed to get Vlan id for bvid oid:0x260000000007c7" in output
