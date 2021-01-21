import sys
import os
from click.testing import CliRunner

from .mock_tables import dbconnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

import show.main as show

test_sfp_eeprom_with_dom_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
        ChannelMonitorValues:
                RX1Power: 0.3802dBm
                RX2Power: -0.4871dBm
                RX3Power: -0.0860dBm
                RX4Power: 0.3830dBm
                TX1Bias: 6.7500mA
                TX2Bias: 6.7500mA
                TX3Bias: 6.7500mA
                TX4Bias: 6.7500mA
        ChannelThresholdValues:
                RxPowerHighAlarm  : 3.4001dBm
                RxPowerHighWarning: 2.4000dBm
                RxPowerLowAlarm   : -13.5067dBm
                RxPowerLowWarning : -9.5001dBm
                TxBiasHighAlarm   : 10.0000mA
                TxBiasHighWarning : 9.5000mA
                TxBiasLowAlarm    : 0.5000mA
                TxBiasLowWarning  : 1.0000mA
        ModuleMonitorValues:
                Temperature: 30.9258C
                Vcc: 3.2824Volts
        ModuleThresholdValues:
                TempHighAlarm  : 75.0000C
                TempHighWarning: 70.0000C
                TempLowAlarm   : -5.0000C
                TempLowWarning : 0.0000C
                VccHighAlarm   : 3.6300Volts
                VccHighWarning : 3.4650Volts
                VccLowAlarm    : 2.9700Volts
                VccLowWarning  : 3.1349Volts
"""

test_qsfp_dd_eeprom_with_dom_output = """\
Ethernet8: SFP EEPROM detected
        Application Advertisement: 400GAUI-8 C2M (Annex 120E) - Active Cable assembly with BER < 2.6x10^-4
				   IB EDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 5x10^-5
				   IB QDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 10^-12
				   
        Connector: No separable connector
        Encoding: Not supported for CMIS cables
        Extended Identifier: Power Class 1(10.0W Max)
        Extended RateSelect Compliance: Not supported for CMIS cables
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Length Cable Assembly(m): 10
        Nominal Bit Rate(100Mbs): Not supported for CMIS cables
        Specification compliance: Not supported for CMIS cables
        Vendor Date Code(YYYY-MM-DD Lot): 2020-05-22 
        Vendor Name: INNOLIGHT
        Vendor OUI: 44-7c-7f
        Vendor PN: C-DQ8FNM010-N00
        Vendor Rev: 2A
        Vendor SN: INKAO2900002A
        ChannelMonitorValues: 
                RX1Power: -3.8595dBm
                RX2Power: 8.1478dBm
                RX3Power: -22.9243dBm
                RX4Power: 1.175dBm
                RX5Power: 1.2421dBm
                RX6Power: 8.1489dBm
                RX7Power: -3.5962dBm
                RX8Power: -3.6131dBm
                TX1Bias: 17.4760mA
                TX1Power: 1.175dBm
                TX2Bias: 17.4760mA
                TX2Power: 1.175dBm
                TX3Bias: 0.0000mA
                TX3Power: 1.175dBm
                TX4Bias: 0.0000mA
                TX4Power: 1.175dBm
                TX5Bias: 0.0000mAmA
                TX5Power: 1.175dBm
                TX6Bias: 8.2240mAmA
                TX6Power: 1.175dBm
                TX7Bias: 8.2240mAmA
                TX7Power: 1.175dBm
                TX8Bias: 8.2240mAmA
                TX8Power: 1.175dBm
        ChannelThresholdValues: 
                RxPowerHighAlarm  : 6.9999dBm
                RxPowerHighWarning: 4.9999dBm
                RxPowerLowAlarm   : -11.9044dBm
                RxPowerLowWarning : -8.9008dBm
                TxBiasHighAlarm   : 14.9960mA
                TxBiasHighWarning : 12.9980mA
                TxBiasLowAlarm    : 4.4960mA
                TxBiasLowWarning  : 5.0000mA
                TxPowerHighAlarm  : 6.9999dBm
                TxPowerHighWarning: 4.9999dBm
                TxPowerLowAlarm   : -10.5012dBm
                TxPowerLowWarning : -7.5007dBm
        ModuleMonitorValues: 
                Temperature: 44.9883C
                Vcc: 3.2999Volts
        ModuleThresholdValues: 
                TempHighAlarm  : 80.0000C
                TempHighWarning: 75.0000C
                TempLowAlarm   : -10.0000C
                TempLowWarning : -5.0000C
                VccHighAlarm   : 3.6352Volts
                VccHighWarning : 3.4672Volts
                VccLowAlarm    : 2.9696Volts
                VccLowWarning  : 3.1304Volts
"""

test_sfp_eeprom_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
"""

test_qsfp_dd_eeprom_output = """\
Ethernet8: SFP EEPROM detected
        Application Advertisement: 400GAUI-8 C2M (Annex 120E) - Active Cable assembly with BER < 2.6x10^-4
				   IB EDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 5x10^-5
				   IB QDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 10^-12
				   
        Connector: No separable connector
        Encoding: Not supported for CMIS cables
        Extended Identifier: Power Class 1(10.0W Max)
        Extended RateSelect Compliance: Not supported for CMIS cables
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Length Cable Assembly(m): 10
        Nominal Bit Rate(100Mbs): Not supported for CMIS cables
        Specification compliance: Not supported for CMIS cables
        Vendor Date Code(YYYY-MM-DD Lot): 2020-05-22 
        Vendor Name: INNOLIGHT
        Vendor OUI: 44-7c-7f
        Vendor PN: C-DQ8FNM010-N00
        Vendor Rev: 2A
        Vendor SN: INKAO2900002A
"""

test_sfp_eeprom_dom_all_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
        ChannelMonitorValues:
                RX1Power: 0.3802dBm
                RX2Power: -0.4871dBm
                RX3Power: -0.0860dBm
                RX4Power: 0.3830dBm
                TX1Bias: 6.7500mA
                TX2Bias: 6.7500mA
                TX3Bias: 6.7500mA
                TX4Bias: 6.7500mA
        ChannelThresholdValues:
                RxPowerHighAlarm  : 3.4001dBm
                RxPowerHighWarning: 2.4000dBm
                RxPowerLowAlarm   : -13.5067dBm
                RxPowerLowWarning : -9.5001dBm
                TxBiasHighAlarm   : 10.0000mA
                TxBiasHighWarning : 9.5000mA
                TxBiasLowAlarm    : 0.5000mA
                TxBiasLowWarning  : 1.0000mA
        ModuleMonitorValues:
                Temperature: 30.9258C
                Vcc: 3.2824Volts
        ModuleThresholdValues:
                TempHighAlarm  : 75.0000C
                TempHighWarning: 70.0000C
                TempLowAlarm   : -5.0000C
                TempLowWarning : 0.0000C
                VccHighAlarm   : 3.6300Volts
                VccHighWarning : 3.4650Volts
                VccLowAlarm    : 2.9700Volts
                VccLowWarning  : 3.1349Volts

Ethernet4: SFP EEPROM Not detected

Ethernet64: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
        ChannelMonitorValues:
                RX1Power: 0.3802dBm
                RX2Power: -0.4871dBm
                RX3Power: -0.0860dBm
                RX4Power: 0.3830dBm
                TX1Bias: 6.7500mA
                TX2Bias: 6.7500mA
                TX3Bias: 6.7500mA
                TX4Bias: 6.7500mA
        ChannelThresholdValues:
                RxPowerHighAlarm  : 3.4001dBm
                RxPowerHighWarning: 2.4000dBm
                RxPowerLowAlarm   : -13.5067dBm
                RxPowerLowWarning : -9.5001dBm
                TxBiasHighAlarm   : 10.0000mA
                TxBiasHighWarning : 9.5000mA
                TxBiasLowAlarm    : 0.5000mA
                TxBiasLowWarning  : 1.0000mA
        ModuleMonitorValues:
                Temperature: 30.9258C
                Vcc: 3.2824Volts
        ModuleThresholdValues:
                TempHighAlarm  : 75.0000C
                TempHighWarning: 70.0000C
                TempLowAlarm   : -5.0000C
                TempLowWarning : 0.0000C
                VccHighAlarm   : 3.6300Volts
                VccHighWarning : 3.4650Volts
                VccLowAlarm    : 2.9700Volts
                VccLowWarning  : 3.1349Volts
"""

test_sfp_eeprom_all_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064

Ethernet4: SFP EEPROM Not detected

Ethernet64: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
"""

test_sfp_presence_all_output = """\
Port        Presence
----------  -----------
Ethernet0   Present
Ethernet4   Not present
Ethernet64  Present
"""

class TestSFP(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    def test_sfp_presence(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet0"])
        expected = """Port       Presence
---------  ----------
Ethernet0  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet200"])
        expected = """Port         Presence
-----------  -----------
Ethernet200  Not present
"""
        assert result.exit_code == 0
        assert result.output == expected

    def test_sfp_eeprom_with_dom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet0 -d"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_with_dom_output

    def test_qsfp_dd_eeprom_with_dom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet8 -d"])
        assert result.exit_code == 0
        assert "result.output == test_qsfp_dd_eeprom_with_dom_output"

    def test_sfp_eeprom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet0"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet200"])
        result_lines = result.output.strip('\n')
        expected = "Ethernet200: SFP EEPROM Not detected"
        assert result_lines == expected

    def test_qsfp_dd_eeprom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet8"])
        assert result.exit_code == 0
        assert "result.output == test_qsfp_dd_eeprom_output"

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

class Test_multiAsic_SFP(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def test_sfp_presence_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet0 -n asic0"])
        expected = """Port       Presence
---------  ----------
Ethernet0  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet200 -n asic0"])
        expected = """Port         Presence
-----------  -----------
Ethernet200  Not present
"""
        assert result.exit_code == 0
        assert result.output == expected

    def test_sfp_presence_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_presence_all_output

    def test_sfp_eeprom_with_dom_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet0 -d -n asic0"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_with_dom_output

    def test_sfp_eeprom_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet0 -n asic0"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet200 -n asic0"])
        result_lines = result.output.strip('\n')
        expected = "Ethernet200: SFP EEPROM Not detected"
        assert result_lines == expected

    def test_sfp_eeprom_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet0 -n asic0"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet200 -n asic0"])
        result_lines = result.output.strip('\n')
        expected = "Ethernet200: SFP EEPROM Not detected"
        assert result_lines == expected

    def test_sfp_eeprom_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_all_output

    def test_sfp_eeprom_dom_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["-d"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_dom_all_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
