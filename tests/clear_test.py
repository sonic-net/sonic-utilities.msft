import pytest
import clear.main as clear
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

class TestClear(object):
    def setup(self):
        print('SETUP')

    @patch('clear.main.run_command')
    def test_clear_pg_wm_hdrm(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['priority-group'].commands['watermark'].commands['headroom'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-t', 'pg_headroom'])

    @patch('clear.main.run_command')
    def test_clear_pg_wm_shr(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['priority-group'].commands['watermark'].commands['shared'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-t', 'pg_shared'])

    @patch('clear.main.run_command')
    def test_clear_pg_pst_wm_hdrm(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['priority-group'].commands['persistent-watermark'].commands['headroom'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-p', '-t', 'pg_headroom'])

    @patch('clear.main.run_command')
    def test_clear_pg_pst_wm_shr(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['priority-group'].commands['persistent-watermark'].commands['shared'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-p', '-t', 'pg_shared'])

    @patch('clear.main.run_command')
    def test_clear_q_wm_all(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['queue'].commands['watermark'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-t', 'q_shared_all'])

    @patch('clear.main.run_command')
    def test_clear_q_wm_multi(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['queue'].commands['watermark'].commands['multicast'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-t', 'q_shared_multi'])

    @patch('clear.main.run_command')
    def test_clear_q_wm_uni(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['queue'].commands['watermark'].commands['unicast'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-t', 'q_shared_uni'])

    @patch('clear.main.run_command')
    def test_clear_q_pst_wm_all(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['queue'].commands['persistent-watermark'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-p', '-t', 'q_shared_all'])

    @patch('clear.main.run_command')
    def test_clear_q_pst_wm_multi(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['queue'].commands['persistent-watermark'].commands['multicast'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-p', '-t', 'q_shared_multi'])

    @patch('clear.main.run_command')
    def test_clear_q_pst_wm_uni(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['queue'].commands['persistent-watermark'].commands['unicast'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-p', '-t', 'q_shared_uni'])

    @patch('clear.main.run_command')
    @patch('clear.main.os.geteuid', MagicMock(return_value=0))
    def test_clear_hdrm_wm(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['headroom-pool'].commands['watermark'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-t', 'headroom_pool'])

    @patch('clear.main.run_command')
    @patch('clear.main.os.geteuid', MagicMock(return_value=0))
    def test_clear_hdrm_pst_wm(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['headroom-pool'].commands['persistent-watermark'])
        assert result.exit_code == 0
        run_command.assert_called_with(['watermarkstat', '-c', '-p', '-t', 'headroom_pool'])

    @patch('clear.main.run_command')
    def test_clear_fdb(self, run_command):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['fdb'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['fdbclear'])

    def teardown(self):
        print('TEAR DOWN')


class TestClearQuaggav4(object):
    def setup(self):
        print('SETUP')

    @patch('clear.main.run_command')
    @patch('clear.main.get_routing_stack', MagicMock(return_value='quagga'))
    def test_clear_ipv4_quagga(self, run_command):
        from clear.bgp_quagga_v4 import bgp
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp *"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['all'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp 10.0.0.1"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['in'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp * in"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['in'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp 10.0.0.1 in"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['out'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp * out"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['out'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp 10.0.0.1 out"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['soft'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp * soft"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['soft'].commands['all'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp 10.0.0.1 soft"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['soft'].commands['in'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp * soft in"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['soft'].commands['in'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp 10.0.0.1 soft in"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['soft'].commands['out'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp * soft out"])

        result = runner.invoke(clear.cli.commands['ip'].commands['bgp'].commands['neighbor'].commands['soft'].commands['out'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ip bgp 10.0.0.1 soft out"])

    def teardown(self):
        print('TEAR DOWN')


class TestClearQuaggav6(object):
    def setup(self):
        print('SETUP')

    @patch('clear.main.run_command')
    @patch('clear.main.get_routing_stack', MagicMock(return_value='quagga'))
    def test_clear_ipv6_quagga(self, run_command):
        from clear.bgp_quagga_v6 import bgp
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp *"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['all'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp 10.0.0.1"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['in'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp * in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['in'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp 10.0.0.1 in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['out'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp * out"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['out'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp 10.0.0.1 out"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp * soft"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['all'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp 10.0.0.1 soft"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['in'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp * soft in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['in'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp 10.0.0.1 soft in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['out'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp * soft out"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['out'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear ipv6 bgp 10.0.0.1 soft out"])

    def teardown(self):
        print('TEAR DOWN')


class TestClearFrr(object):
    def setup(self):
        print('SETUP')

    @patch('clear.main.run_command')
    @patch('clear.main.get_routing_stack', MagicMock(return_value='frr'))
    def test_clear_ipv6_frr(self, run_command):
        from clear.bgp_frr_v6 import bgp
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 *"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['all'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 10.0.0.1"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['in'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 * in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['in'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 10.0.0.1 in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['out'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 * out"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['out'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 10.0.0.1 out"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['all'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 * soft"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['all'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 10.0.0.1 soft"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['in'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 * soft in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['in'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 10.0.0.1 soft in"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['out'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 * soft out"])

        result = runner.invoke(clear.cli.commands['ipv6'].commands['bgp'].commands['neighbor'].commands['soft'].commands['out'], ['10.0.0.1'])
        assert result.exit_code == 0
        run_command.assert_called_with(['sudo', 'vtysh', '-c', "clear bgp ipv6 10.0.0.1 soft out"])

    def teardown(self):
        print('TEAR DOWN')

