import os
import sys
import traceback

import mock_tables.dbconnector
from click.testing import CliRunner
from unittest import mock
from utilities_common.db import Db

sys.modules['sonic_platform_base'] = mock.Mock()
sys.modules['sonic_platform_base.sonic_sfp'] = mock.Mock()
sys.modules['sonic_platform_base.sonic_sfp.sfputilhelper'] = mock.Mock()
sys.modules['sonic_y_cable'] = mock.Mock()
sys.modules['y_cable'] = mock.Mock()
sys.modules['sonic_y_cable.y_cable'] = mock.Mock()
sys.modules['platform_sfputil'] = mock.Mock()
sys.modules['platform_sfputil_helper'] = mock.Mock()
sys.modules['utilities_common.platform_sfputil_helper'] = mock.Mock()
sys.modules['show.muxcable.platform_sfputil'] = mock.Mock()
#sys.modules['os'] = mock.Mock()
#sys.modules['os.geteuid'] = mock.Mock()
#sys.modules['platform_sfputil'] = mock.Mock()
import config.main as config
import show.main as show


tabular_data_status_output_expected = """\
PORT        STATUS    HEALTH
----------  --------  ---------
Ethernet0   active    healthy
Ethernet4   standby   healthy
Ethernet8   standby   unhealthy
Ethernet12  unknown   unhealthy
Ethernet32  active    healthy
"""

json_data_status_output_expected = """\
{
    "MUX_CABLE": {
        "Ethernet0": {
            "STATUS": "active",
            "HEALTH": "healthy"
        },
        "Ethernet4": {
            "STATUS": "standby",
            "HEALTH": "healthy"
        },
        "Ethernet8": {
            "STATUS": "standby",
            "HEALTH": "unhealthy"
        },
        "Ethernet12": {
            "STATUS": "unknown",
            "HEALTH": "unhealthy"
        },
        "Ethernet32": {
            "STATUS": "active",
            "HEALTH": "healthy"
        }
    }
}
"""


tabular_data_config_output_expected = """\
SWITCH_NAME    PEER_TOR
-------------  ----------
sonic-switch   10.2.2.2
port        state    ipv4      ipv6
----------  -------  --------  --------
Ethernet0   active   10.2.1.1  e800::46
Ethernet4   auto     10.3.1.1  e801::46
Ethernet8   active   10.4.1.1  e802::46
Ethernet12  active   10.4.1.1  e802::46
Ethernet32  auto     10.1.1.1  fc00::75
"""

json_data_status_config_output_expected = """\
{
    "MUX_CABLE": {
        "PEER_TOR": "10.2.2.2",
        "PORTS": {
            "Ethernet0": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.2.1.1",
                    "IPv6": "e800::46"
                }
            },
            "Ethernet4": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.3.1.1",
                    "IPv6": "e801::46"
                }
            },
            "Ethernet8": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.4.1.1",
                    "IPv6": "e802::46"
                }
            },
            "Ethernet12": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.4.1.1",
                    "IPv6": "e802::46"
                }
            },
            "Ethernet32": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75"
                }
            }
        }
    }
}
"""

json_port_data_status_config_output_expected = """\
{
    "MUX_CABLE": {
        "PEER_TOR": "10.2.2.2",
        "PORTS": {
            "Ethernet32": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75"
                }
            }
        }
    }
}
"""

json_data_config_output_auto_expected = """\
{
    "Ethernet32": "OK",
    "Ethernet0": "OK",
    "Ethernet4": "OK",
    "Ethernet8": "OK",
    "Ethernet12": "OK"
}
"""

json_data_config_output_active_expected = """\
{
    "Ethernet32": "OK",
    "Ethernet0": "OK",
    "Ethernet4": "INPROGRESS",
    "Ethernet8": "OK",
    "Ethernet12": "OK"
}
"""

expected_muxcable_cableinfo_output = """\
Vendor    Model
--------  ---------------
Credo     CACL1X321P2PA1M
"""

show_muxcable_hwmode_muxdirection_active_expected_output = """\
Port        Direction
----------  -----------
Ethernet12  active
"""

show_muxcable_hwmode_muxdirection_standby_expected_output = """\
Port        Direction
----------  -----------
Ethernet12  standby
"""

show_muxcable_firmware_version_expected_output = """\
{
    "version_self_active": "0.6MS",
    "version_self_inactive": "0.6MS",
    "version_self_next": "0.6MS",
    "version_peer_active": "0.6MS",
    "version_peer_inactive": "0.6MS",
    "version_peer_next": "0.6MS",
    "version_nic_active": "0.6MS",
    "version_nic_inactive": "0.6MS",
    "version_nic_next": "0.6MS"
}
"""

show_muxcable_firmware_version_active_expected_output = """\
{
    "version_self_active": "0.6MS",
    "version_peer_active": "0.6MS",
    "version_nic_active": "0.6MS"
}
"""

show_muxcable_metrics_expected_output = """\
PORT       EVENT                         TIME
---------  ----------------------------  ---------------------------
Ethernet0  linkmgrd_switch_active_start  2021-May-13 10:00:21.420898
Ethernet0  linkmgrd_switch_standby_end   2021-May-13 10:01:15.696728
Ethernet0  xcvrd_switch_standby_end      2021-May-13 10:01:15.696051
Ethernet0  xcvrd_switch_standby_start    2021-May-13 10:01:15.690835
"""

show_muxcable_metrics_expected_output_json = """\
{
    "linkmgrd_switch_active_start": "2021-May-13 10:00:21.420898",
    "linkmgrd_switch_standby_end": "2021-May-13 10:01:15.696728",
    "xcvrd_switch_standby_end": "2021-May-13 10:01:15.696051",
    "xcvrd_switch_standby_start": "2021-May-13 10:01:15.690835"
}
"""

class TestMuxcable(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        #show.muxcable.platform_sfputil.logical = mock.Mock(return_value=["Ethernet0", "Ethernet4"])
        print("SETUP")

    def test_muxcable_status(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["muxcable"].commands["status"], obj=db)

        assert result.exit_code == 0
        assert result.output == tabular_data_status_output_expected

    def test_muxcable_status_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == json_data_status_output_expected

    def test_muxcable_status_config(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], obj=db)

        assert result.exit_code == 0
        assert result.output == tabular_data_config_output_expected

    def test_muxcable_status_config_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == json_data_status_config_output_expected

    def test_muxcable_config_json_with_incorrect_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet33", "--json"], obj=db)

        assert result.exit_code == 1

    def test_muxcable_status_json_with_correct_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_muxcable_status_json_port_incorrect_index(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 1
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 1

    def test_muxcable_status_with_patch(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"], obj=db)

    def test_muxcable_status_json_with_incorrect_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet33", "--json"], obj=db)

        assert result.exit_code == 1

    def test_muxcable_config_with_correct_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet0"], obj=db)

        assert result.exit_code == 0

    def test_muxcable_config_json_with_correct_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_muxcable_config_json_port_with_incorrect_index(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 1
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_muxcable_config_json_with_incorrect_port_patch(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet33", "--json"], obj=db)

        assert result.exit_code == 1

    def test_muxcable_status_json_port_eth0(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet0"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet8_active(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet8"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet8_auto(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "Ethernet8"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_mode_auto_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "all", "--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == json_data_config_output_auto_expected

    def test_config_muxcable_mode_active_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "all", "--json"], obj=db)
        f = open("newfile1", "w")
        f.write(result.output)

        assert result.exit_code == 0
        assert result.output == json_data_config_output_active_expected

    def test_config_muxcable_json_port_auto_Ethernet0(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "auto", "Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_json_port_active_Ethernet0(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "active", "Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_mode_auto_tabular(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "all"], obj=db)
        assert result.exit_code == 0

    def test_config_muxcable_mode_active_tabular(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "all"], obj=db)
        f = open("newfile", "w")
        f.write(result.output)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet0"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet4_active(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet4"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet4_auto(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "Ethernet4"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_with_incorrect_index(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 2
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet0"], obj=db)

        assert result.exit_code == 1

    def test_config_muxcable_tabular_port_with_incorrect_port_index(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 7
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "active", "Ethernet33"], obj=db)

        assert result.exit_code == 1

    def test_config_muxcable_tabular_port_with_incorrect_port(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "active", "Ethernet33"], obj=db)

        assert result.exit_code == 1

    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('sonic_y_cable.y_cable.get_eye_info', mock.MagicMock(return_value=[0, 0]))
    def test_show_muxcable_eye_info(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["eyeinfo"],
                               ["0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('sonic_y_cable.y_cable.get_ber_info', mock.MagicMock(return_value=[0, 0]))
    def test_show_muxcable_ber_info(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["berinfo"],
                               ["0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('sonic_y_cable.y_cable.enable_prbs_mode', mock.MagicMock(return_value=1))
    def test_config_muxcable_enable_prbs(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["prbs"].commands["enable"],
                               ["0", "0", "0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('sonic_y_cable.y_cable.enable_loopback_mode', mock.MagicMock(return_value=1))
    def test_config_muxcable_enable_loopback(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["loopback"].commands["enable"],
                               ["0", "0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('sonic_y_cable.y_cable.disable_prbs_mode', mock.MagicMock(return_value=1))
    def test_config_muxcable_disble_prbs(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["prbs"].commands["disable"],
                               ["0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('sonic_y_cable.y_cable.disable_loopback_mode', mock.MagicMock(return_value=1))
    def test_config_muxcable_disable_loopback(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["loopback"].commands["disable"],
                               ["0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=("CACL1X321P2PA1M")))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=("Credo          ")))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_cableinfo(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)

        assert result.exit_code == 0
        assert result.output == expected_muxcable_cableinfo_output

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_cableinfo_incorrect_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=0))
    def test_show_muxcable_cableinfo_incorrect_port_return_value(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0, 1]))
    def test_show_muxcable_cableinfo_incorrect_logical_port_return_value(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["Ethernet12"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_active_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["Ethernet12"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_standby_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_port_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["active", "Ethernet12"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["active", "all"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_port_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["standby", "Ethernet12"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["standby", "all"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.get_firmware_version', mock.MagicMock(return_value={"version_active": "0.6MS",
                                                                                           "version_inactive": "0.6MS",
                                                                                           "version_next": "0.6MS"}))
    def test_show_muxcable_firmware_version(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_firmware_version_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.download_fimware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_DOWNLOAD_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_download_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["download"], [
                               "fwfile", "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.activate_firmware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_ACTIVATE_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_activate_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["activate"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.rollback_firmware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_ROLLBACK_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_rollback_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["rollback"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["Ethernet0", "--json"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output_json

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.get_firmware_version', mock.MagicMock(return_value={"version_active": "0.6MS",
                                                                                           "version_inactive": "0.6MS",
                                                                                           "version_next": "0.6MS"}))
    def test_show_muxcable_firmware_active_version(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "Ethernet0", "--active"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_firmware_version_active_expected_output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
