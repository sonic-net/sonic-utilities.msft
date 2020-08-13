import os
import traceback

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

show_vlan_brief_output="""\
+-----------+-----------------+------------+----------------+-----------------------+
|   VLAN ID | IP Address      | Ports      | Port Tagging   | DHCP Helper Address   |
+===========+=================+============+================+=======================+
|      1000 | 192.168.0.1/21  | Ethernet4  | untagged       | 192.0.0.1             |
|           | fc02:1000::1/64 | Ethernet8  | untagged       | 192.0.0.2             |
|           |                 | Ethernet12 | untagged       | 192.0.0.3             |
|           |                 | Ethernet16 | untagged       | 192.0.0.4             |
+-----------+-----------------+------------+----------------+-----------------------+
"""

show_vlan_brief_in_alias_mode_output="""\
+-----------+-----------------+---------+----------------+-----------------------+
|   VLAN ID | IP Address      | Ports   | Port Tagging   | DHCP Helper Address   |
+===========+=================+=========+================+=======================+
|      1000 | 192.168.0.1/21  | etp2    | untagged       | 192.0.0.1             |
|           | fc02:1000::1/64 | etp3    | untagged       | 192.0.0.2             |
|           |                 | etp4    | untagged       | 192.0.0.3             |
|           |                 | etp5    | untagged       | 192.0.0.4             |
+-----------+-----------------+---------+----------------+-----------------------+
"""

show_vlan_brief_empty_output="""\
+-----------+--------------+---------+----------------+-----------------------+
| VLAN ID   | IP Address   | Ports   | Port Tagging   | DHCP Helper Address   |
+===========+==============+=========+================+=======================+
+-----------+--------------+---------+----------------+-----------------------+
"""

show_vlan_brief_with_portchannel_output="""\
+-----------+-----------------+-----------------+----------------+-----------------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | DHCP Helper Address   |
+===========+=================+=================+================+=======================+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | 192.0.0.1             |
|           | fc02:1000::1/64 | Ethernet8       | untagged       | 192.0.0.2             |
|           |                 | Ethernet12      | untagged       | 192.0.0.3             |
|           |                 | Ethernet16      | untagged       | 192.0.0.4             |
|           |                 | PortChannel1001 | untagged       |                       |
+-----------+-----------------+-----------------+----------------+-----------------------+
"""

show_vlan_config_output="""\
Name        VID  Member      Mode
--------  -----  ----------  --------
Vlan1000   1000  Ethernet8   untagged
Vlan1000   1000  Ethernet12  untagged
Vlan1000   1000  Ethernet4   untagged
Vlan1000   1000  Ethernet16  untagged
"""

show_vlan_config_in_alias_mode_output="""\
Name        VID  Member    Mode
--------  -----  --------  --------
Vlan1000   1000  etp3      untagged
Vlan1000   1000  etp4      untagged
Vlan1000   1000  etp2      untagged
Vlan1000   1000  etp5      untagged
"""

config_vlan_add_dhcp_relay_output="""\
Added DHCP relay destination address 192.0.0.100 to Vlan1000
Restarting DHCP relay service...
"""

config_vlan_del_dhcp_relay_output="""\
Removed DHCP relay destination address 192.0.0.100 from Vlan1000
Restarting DHCP relay service...
"""

show_vlan_brief_output_with_new_dhcp_relay_address="""\
+-----------+-----------------+------------+----------------+-----------------------+
|   VLAN ID | IP Address      | Ports      | Port Tagging   | DHCP Helper Address   |
+===========+=================+============+================+=======================+
|      1000 | 192.168.0.1/21  | Ethernet4  | untagged       | 192.0.0.1             |
|           | fc02:1000::1/64 | Ethernet8  | untagged       | 192.0.0.2             |
|           |                 | Ethernet12 | untagged       | 192.0.0.3             |
|           |                 | Ethernet16 | untagged       | 192.0.0.4             |
|           |                 |            |                | 192.0.0.100           |
+-----------+-----------------+------------+----------------+-----------------------+
"""

config_add_del_vlan_and_vlan_member_output="""\
+-----------+-----------------+------------+----------------+-----------------------+
|   VLAN ID | IP Address      | Ports      | Port Tagging   | DHCP Helper Address   |
+===========+=================+============+================+=======================+
|      1000 | 192.168.0.1/21  | Ethernet4  | untagged       | 192.0.0.1             |
|           | fc02:1000::1/64 | Ethernet8  | untagged       | 192.0.0.2             |
|           |                 | Ethernet12 | untagged       | 192.0.0.3             |
|           |                 | Ethernet16 | untagged       | 192.0.0.4             |
+-----------+-----------------+------------+----------------+-----------------------+
|      1001 |                 | Ethernet20 | untagged       |                       |
+-----------+-----------------+------------+----------------+-----------------------+
"""

config_add_del_vlan_and_vlan_member_in_alias_mode_output="""\
+-----------+-----------------+---------+----------------+-----------------------+
|   VLAN ID | IP Address      | Ports   | Port Tagging   | DHCP Helper Address   |
+===========+=================+=========+================+=======================+
|      1000 | 192.168.0.1/21  | etp2    | untagged       | 192.0.0.1             |
|           | fc02:1000::1/64 | etp3    | untagged       | 192.0.0.2             |
|           |                 | etp4    | untagged       | 192.0.0.3             |
|           |                 | etp5    | untagged       | 192.0.0.4             |
+-----------+-----------------+---------+----------------+-----------------------+
|      1001 |                 | etp6    | untagged       |                       |
+-----------+-----------------+---------+----------------+-----------------------+
"""
class TestVlan(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_show_vlan(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_show_vlan_brief(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_show_vlan_brief_verbose(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], ["--verbose"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_show_vlan_brief_in_alias_mode(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_in_alias_mode_output

    def test_show_vlan_config(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["config"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_config_output

    def test_show_vlan_config_in_alias_mode(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["vlan"].commands["config"], [])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_config_in_alias_mode_output

    def test_config_vlan_add_vlan_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["4096"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (1-4094)" in result.output

    def test_config_vlan_add_vlan_with_exist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1000"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1000 already exists" in result.output

    def test_config_vlan_del_vlan_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["4096"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (1-4094)" in result.output

    def test_config_vlan_del_vlan_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1001 does not exist" in result.output

    def test_config_vlan_add_member_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["4096", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (1-4094)" in result.output

    def test_config_vlan_add_member_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1001", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1001 does not exist" in result.output

    def test_config_vlan_add_exist_port_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1000", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet4 is already a member of Vlan1000" in result.output

    def test_config_vlan_add_nonexist_port_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1000", "Ethernet3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet3 does not exist" in result.output

    def test_config_vlan_add_nonexist_portchannel_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], \
				["1000", "PortChannel1011"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel1011 does not exist" in result.output

    def test_config_vlan_add_portchannel_member(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], \
				["1000", "PortChannel1001", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_with_portchannel_output

    def test_config_vlan_add_rif_portchannel_member(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], \
				["1000", "PortChannel0001", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 is a router interface!" in result.output

    def test_config_vlan_del_vlan(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_empty_output

    def test_config_vlan_del_nonexist_vlan_member(self):
        runner = CliRunner()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"], \
				["1000", "Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet0 is not a member of Vlan1000" in result.output

    def test_config_add_del_vlan_and_vlan_member(self):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "Ethernet20", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == config_add_del_vlan_and_vlan_member_output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_config_add_del_vlan_and_vlan_member_in_alias_mode(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add etp6 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "etp6", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == config_add_del_vlan_and_vlan_member_in_alias_mode_output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001", "etp6"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_in_alias_mode_output

        os.environ['SONIC_CLI_IFACE_MODE'] = ""

    def test_config_vlan_add_dhcp_relay_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["add"],
                ["1001", "192.0.0.100"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Error: Vlan1001 doesn't exist" in result.output

    def test_config_vlan_add_dhcp_relay_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["add"],
                ["4096", "192.0.0.100"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Error: Vlan4096 doesn't exist" in result.output

    def test_config_vlan_add_dhcp_relay_with_invalid_ip(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["add"],
                ["1000", "192.0.0.1000"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Error: 192.0.0.1000 is invalid IP address" in result.output

    def test_config_vlan_add_dhcp_relay_with_exist_ip(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["add"],
                ["1000", "192.0.0.1"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert "192.0.0.1 is already a DHCP relay destination for Vlan1000" in result.output

    def test_config_vlan_add_del_dhcp_relay_dest(self):
        runner = CliRunner()
        db = Db()

        # add new relay dest
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["add"],
                ["1000", "192.0.0.100"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_vlan_add_dhcp_relay_output

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == show_vlan_brief_output_with_new_dhcp_relay_address

        # del relay dest
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["del"],
                ["1000", "192.0.0.100"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == config_vlan_del_dhcp_relay_output

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == show_vlan_brief_output

    def test_config_vlan_remove_nonexist_dhcp_relay_dest(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["del"],
                ["1000", "192.0.0.100"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Error: 192.0.0.100 is not a DHCP relay destination for Vlan1000" in result.output

    def test_config_vlan_remove_dhcp_relay_dest_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["dhcp_relay"].commands["del"],
                ["1001", "192.0.0.1"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Error: Vlan1001 doesn't exist" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
