import sys
import os
from unittest import mock
from unittest.mock import MagicMock, patch

from .mock_tables import dbconnector

import pytest
from click.testing import CliRunner
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

sys.modules['sonic_platform'] = mock.MagicMock()
import sfputil.main as sfputil


class TestSfputil(object):
    def test_format_dict_value_to_string(self):
        sorted_key_table = [
            'rx1power',
            'rx2power',
            'rx3power',
            'rx4power',
            'tx1bias',
            'tx1power',
            'tx2bias',
            'tx2power',
            'tx3bias',
            'tx3power',
            'tx4bias',
            'tx4power'
        ]

        dom_info_dict = {
            'temperature': '41.7539C',
            'voltage': '3.2577Volts',
            'rx1power': '-1.6622dBm',
            'rx2power': '-1.7901dBm',
            'rx3power': '-1.6973dBm',
            'rx4power': '-2.0915dBm',
            'tx1bias': '35.8400mA',
            'tx2bias': '37.5780mA',
            'tx3bias': '35.8400mA',
            'tx4bias': '35.8400mA',
            'tx1power': 'N/A',
            'tx2power': 'N/A',
            'tx3power': 'N/A',
            'tx4power': 'N/A'
        }

        expected_output = '''\
                RX1Power: -1.6622dBm
                RX2Power: -1.7901dBm
                RX3Power: -1.6973dBm
                RX4Power: -2.0915dBm
                TX1Bias: 35.8400mA
                TX2Bias: 37.5780mA
                TX3Bias: 35.8400mA
                TX4Bias: 35.8400mA
'''

        output = sfputil.format_dict_value_to_string(sorted_key_table,
                                                     dom_info_dict,
                                                     sfputil.QSFP_DOM_CHANNEL_MONITOR_MAP,
                                                     sfputil.DOM_VALUE_UNIT_MAP)
        assert output == expected_output

        # Change temperature and voltage to floats and ensure units get appended
        dom_info_dict['temperature'] = 41.7539
        dom_info_dict['voltage'] = 3.2577

        output = sfputil.format_dict_value_to_string(sorted_key_table,
                                                     dom_info_dict,
                                                     sfputil.QSFP_DOM_CHANNEL_MONITOR_MAP,
                                                     sfputil.DOM_VALUE_UNIT_MAP)
        assert output == expected_output
    @pytest.mark.parametrize("sfp_info_dict, expected_output",[
        # Non-CMIS module
        (
            # sfp_info_dict
            {
                'type': 'QSFP28 or later',
                'type_abbrv_name': 'QSFP28',
                'manufacturer': 'Mellanox',
                'model': 'MCP1600-C003',
                'vendor_rev': 'A2',
                'serial': 'MT1636VS10561',
                'vendor_oui': '00-02-c9',
                'vendor_date': '2016-07-18',
                'connector': 'No separable connector',
                'encoding': '64B66B',
                'ext_identifier': 'Power Class 1(1.5W max)',
                'ext_rateselect_compliance': 'QSFP+ Rate Select Version 1',
                'cable_type': 'Length Cable Assembly(m)',
                'cable_length': '3',
                'application_advertisement': 'N/A',
                'specification_compliance': "{'10/40G Ethernet Compliance Code': '40GBASE-CR4'}",
                'dom_capability': "{'Tx_power_support': 'no', 'Rx_power_support': 'no', 'Voltage_support': 'no', 'Temp_support': 'no'}",
                'nominal_bit_rate': '255'
            },
            # expected_output
            "        Application Advertisement: N/A\n"
            "        Connector: No separable connector\n"
            "        Encoding: 64B66B\n"
            "        Extended Identifier: Power Class 1(1.5W max)\n"
            "        Extended RateSelect Compliance: QSFP+ Rate Select Version 1\n"
            "        Identifier: QSFP28 or later\n"
            "        Length Cable Assembly(m): 3\n"
            "        Nominal Bit Rate(100Mbs): 255\n"
            "        Specification compliance:\n"
            "                10/40G Ethernet Compliance Code: 40GBASE-CR4\n"
            "        Vendor Date Code(YYYY-MM-DD Lot): 2016-07-18\n"
            "        Vendor Name: Mellanox\n"
            "        Vendor OUI: 00-02-c9\n"
            "        Vendor PN: MCP1600-C003\n"
            "        Vendor Rev: A2\n"
            "        Vendor SN: MT1636VS10561\n"
        ),
        # CMIS compliant module
        (
            # sfp_info_dict
            {
                'type': 'QSFP-DD Double Density 8X Pluggable Transceiver',
                'type_abbrv_name': 'QSFP-DD',
                'manufacturer': 'abc',
                'model': 'def',
                'vendor_rev': 'ghi',
                'serial': 'jkl',
                'vendor_oui': '00-00-00',
                'vendor_date': '2000-01-01',
                'connector': 'LC',
                'encoding': 'N/A',
                'ext_identifier': 'Power Class 8 (18.0W Max)',
                'ext_rateselect_compliance': 'N/A',
                'cable_type': 'Length Cable Assembly(m)',
                'cable_length': '0',
                'application_advertisement': 'N/A',
                'specification_compliance': "sm_media_interface",
                'dom_capability': "{'Tx_power_support': 'no', 'Rx_power_support': 'no', 'Voltage_support': 'no', 'Temp_support': 'no'}",
                'nominal_bit_rate': '0',
                'active_firmware': '0.1',
                'inactive_firmware': '0.0',
                'hardware_rev': '0.0',
                'media_interface_code': '400ZR, DWDM, amplified',
                'host_electrical_interface': '400GAUI-8 C2M (Annex 120E)',
                'host_lane_count': 8,
                'media_lane_count': 1,
                'host_lane_assignment_option': 1,
                'media_lane_assignment_option': 1,
                'active_apsel_hostlane1': 1,
                'active_apsel_hostlane2': 1,
                'active_apsel_hostlane3': 1,
                'active_apsel_hostlane4': 1,
                'active_apsel_hostlane5': 1,
                'active_apsel_hostlane6': 1,
                'active_apsel_hostlane7': 1,
                'active_apsel_hostlane8': 1,
                'media_interface_technology': 'C-band tunable laser',
                'cmis_rev': '5.0',
                'supported_max_tx_power': 0,
                'supported_min_tx_power': -20,
                'supported_max_laser_freq': 196100,
                'supported_min_laser_freq': 191300
            },
            # expected_output
            "        Active App Selection Host Lane 1: 1\n"
            "        Active App Selection Host Lane 2: 1\n"
            "        Active App Selection Host Lane 3: 1\n"
            "        Active App Selection Host Lane 4: 1\n"
            "        Active App Selection Host Lane 5: 1\n"
            "        Active App Selection Host Lane 6: 1\n"
            "        Active App Selection Host Lane 7: 1\n"
            "        Active App Selection Host Lane 8: 1\n"
            "        Active Firmware Version: 0.1\n"
            "        CMIS Revision: 5.0\n"
            "        Connector: LC\n"
            "        Encoding: N/A\n"
            "        Extended Identifier: Power Class 8 (18.0W Max)\n"
            "        Extended RateSelect Compliance: N/A\n"
            "        Hardware Revision: 0.0\n"
            "        Host Electrical Interface: 400GAUI-8 C2M (Annex 120E)\n"
            "        Host Lane Assignment Options: 1\n"
            "        Host Lane Count: 8\n"
            "        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver\n"
            "        Inactive Firmware Version: 0.0\n"
            "        Length Cable Assembly(m): 0\n"
            "        Media Interface Code: 400ZR, DWDM, amplified\n"
            "        Media Interface Technology: C-band tunable laser\n"
            "        Media Lane Assignment Options: 1\n"
            "        Media Lane Count: 1\n"
            "        Nominal Bit Rate(100Mbs): 0\n"
            "        Specification compliance: sm_media_interface\n"
            "        Supported Max Laser Frequency: 196100GHz\n"
            "        Supported Max TX Power: 0dBm\n"
            "        Supported Min Laser Frequency: 191300GHz\n"
            "        Supported Min TX Power: -20dBm\n"
            "        Vendor Date Code(YYYY-MM-DD Lot): 2000-01-01\n"
            "        Vendor Name: abc\n"
            "        Vendor OUI: 00-00-00\n"
            "        Vendor PN: def\n"
            "        Vendor Rev: ghi\n"
            "        Vendor SN: jkl\n"
        ),
    ])
    def test_convert_sfp_info_to_output_string(self, sfp_info_dict, expected_output):
        output = sfputil.convert_sfp_info_to_output_string(sfp_info_dict)
        assert output == expected_output

    def test_convert_dom_to_output_string(self):
        sfp_type = 'QSFP28 or later'

        dom_info_dict = {
            'temperature': '41.7539C',
            'voltage': '3.2577Volts',
            'rx1power': '-1.6622dBm',
            'rx2power': '-1.7901dBm',
            'rx3power': '-1.6973dBm',
            'rx4power': '-2.0915dBm',
            'tx1bias': '35.8400mA',
            'tx2bias': '37.5780mA',
            'tx3bias': '35.8400mA',
            'tx4bias': '35.8400mA',
            'tx1power': 'N/A',
            'tx2power': 'N/A',
            'tx3power': 'N/A',
            'tx4power': 'N/A'
        }

        expected_output = '''\
        ChannelMonitorValues:
                RX1Power: -1.6622dBm
                RX2Power: -1.7901dBm
                RX3Power: -1.6973dBm
                RX4Power: -2.0915dBm
                TX1Bias: 35.8400mA
                TX2Bias: 37.5780mA
                TX3Bias: 35.8400mA
                TX4Bias: 35.8400mA
        ChannelThresholdValues:
        ModuleMonitorValues:
                Temperature: 41.7539C
                Vcc: 3.2577Volts
        ModuleThresholdValues:
'''

        output = sfputil.convert_dom_to_output_string(sfp_type, dom_info_dict)
        assert output == expected_output

        # TODO: Add tests for other SFP types

    def test_get_physical_port_name(self):
        output = sfputil.get_physical_port_name(0, 0, False)
        assert output == '0'

        output = sfputil.get_physical_port_name('Ethernet0', 0, False)
        assert output == 'Ethernet0'

        output = sfputil.get_physical_port_name('Ethernet0', 0, True)
        assert output == 'Ethernet0:0 (ganged)'

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['version'], [])
        assert result.output.rstrip() == 'sfputil version {}'.format(sfputil.VERSION)

    def test_error_status_from_db(self):
        db = Db()
        expected_output = [['Ethernet0', 'Blocking Error|High temperature'],
                           ['Ethernet4', 'OK'],
                           ['Ethernet8', 'Unplugged'],
                           ['Ethernet12', 'Unknown state: 255']]
        output = sfputil.fetch_error_status_from_state_db(None, db.db)
        assert output == expected_output

        expected_output_ethernet0 = expected_output[:1]
        output = sfputil.fetch_error_status_from_state_db('Ethernet0', db.db)
        assert output == expected_output_ethernet0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_show_firmware_version(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.get_module_fw_info.return_value = {'info' : ""}
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['fwversion'], ["Ethernet0"])
        assert result.exit_code == 0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_unlock_firmware(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.cdb_enter_host_password.return_value = 0
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['unlock'], ["Ethernet0"])
        assert result.exit_code == 0


    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_run_firmwre(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.cdb_run_firmware.return_value = 1
        status = sfputil.run_firmware("Ethernet0", 1)
        assert status == 1

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_commit_firmwre(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.cdb_commit_firmware.return_value = 1
        status = sfputil.commit_firmware("Ethernet0")
        assert status == 1
