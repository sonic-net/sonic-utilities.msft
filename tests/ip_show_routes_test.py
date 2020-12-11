import os
import pytest

from . import show_ip_route_common
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")


class TestShowIpRouteCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        #in case someone did not clean up properly so undo the multi-asic mock here
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        import mock_tables.dbconnector
    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_expected_output + "\n"

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_specific_route'], indirect=['setup_single_bgp_instance'])
    def test_show_specific_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["192.168.0.1"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_specific_ip_route_expected_output + "\n"

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_special_route'], indirect=['setup_single_bgp_instance'])
    def test_show_special_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_special_ip_route_expected_output + "\n"

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_specific_route'], indirect=['setup_single_bgp_instance'])
    def test_show_specific_ipv6_route_json(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["20c0:a8c7:0:81::", "json"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_single_json_expected_output + "\n"

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ipv6_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_expected_output + "\n"

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route_err'], indirect=['setup_single_bgp_instance'])
    def test_show_ipv6_route_err(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["garbage"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_err_expected_output + "\n"
