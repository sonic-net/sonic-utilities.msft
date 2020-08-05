from click.testing import CliRunner

show_feature_status_output="""\
Feature     State     AutoRestart
----------  --------  -------------
bgp         enabled   enabled
database    enabled   disabled
dhcp_relay  enabled   enabled
lldp        enabled   enabled
nat         enabled   enabled
pmon        enabled   enabled
radv        enabled   enabled
restapi     disabled  enabled
sflow       disabled  enabled
snmp        enabled   enabled
swss        enabled   enabled
syncd       enabled   enabled
teamd       enabled   enabled
telemetry   enabled   enabled
"""

show_feature_bgp_status_output="""\
Feature    State    AutoRestart
---------  -------  -------------
bgp        enabled  enabled
"""

show_feature_bgp_disabled_status_output="""\
Feature    State     AutoRestart
---------  --------  -------------
bgp        disabled  enabled
"""

show_feature_autorestart_output="""\
Feature     AutoRestart
----------  -------------
bgp         enabled
database    disabled
dhcp_relay  enabled
lldp        enabled
nat         enabled
pmon        enabled
radv        enabled
restapi     enabled
sflow       enabled
snmp        enabled
swss        enabled
syncd       enabled
teamd       enabled
telemetry   enabled
"""

show_feature_bgp_autorestart_output="""\
Feature    AutoRestart
---------  -------------
bgp        enabled
"""


show_feature_bgp_disabled_autorestart_output="""\
Feature    AutoRestart
---------  -------------
bgp        disabled
"""

class TestFeature(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_show_feature_status(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["feature"].commands["status"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_status_output

    def test_show_bgp_feature_status(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["bgp"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_status_output

    def test_show_unknown_feature_status(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["foo"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1

    def test_show_feature_autorestart(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_autorestart_output

    def test_show_bgp_autorestart_status(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["bgp"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_autorestart_output

    def test_show_unknown_autorestart_status(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["foo"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1

    def test_config_bgp_feature_state(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["bgp", "disabled"])
        print(result.exit_code)
        print(result.output)
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["bgp"])
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_disabled_status_output

    def test_config_bgp_autorestart(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["bgp", "disabled"])
        print(result.exit_code)
        print(result.output)
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["bgp"])
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_disabled_autorestart_output

    def test_config_unknown_feature(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands['state'], ["foo", "enabled"])
        print(result.output)
        assert result.exit_code == 1

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
