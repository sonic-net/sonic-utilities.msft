from importlib import reload

from click.testing import CliRunner

from utilities_common.db import Db

show_feature_status_output="""\
Feature     State           AutoRestart
----------  --------------  --------------
bgp         enabled         enabled
database    always_enabled  always_enabled
dhcp_relay  enabled         enabled
lldp        enabled         enabled
nat         enabled         enabled
pmon        enabled         enabled
radv        enabled         enabled
restapi     disabled        enabled
sflow       disabled        enabled
snmp        enabled         enabled
swss        enabled         enabled
syncd       enabled         enabled
teamd       enabled         enabled
telemetry   enabled         enabled
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
----------  --------------
bgp         enabled
database    always_enabled
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

show_feature_database_always_enabled_state_output="""\
Feature    State           AutoRestart
---------  --------------  --------------
database   always_enabled  always_enabled
"""

show_feature_database_always_enabled_autorestart_output="""\
Feature    AutoRestart
---------  --------------
database   always_enabled
"""
config_feature_bgp_inconsistent_state_output="""\
Feature 'bgp' state is not consistent across namespaces
"""
config_feature_bgp_inconsistent_autorestart_output="""\
Feature 'bgp' auto-restart is not consistent across namespaces
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

    def test_show_feature_status_abbrev_cmd(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["feature"], ["st"])
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
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["bgp", "disabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["bgp"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_disabled_status_output

    def test_config_bgp_autorestart(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["bgp", "disabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["bgp"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_disabled_autorestart_output

    def test_config_database_feature_state(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["database", "disabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["database"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_database_always_enabled_state_output
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["database", "enabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["database"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_database_always_enabled_state_output

    def test_config_database_feature_autorestart(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["database", "disabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["database"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_database_always_enabled_autorestart_output
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["database", "enabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["database"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_database_always_enabled_autorestart_output

    def test_config_unknown_feature(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands['state'], ["foo", "enabled"])
        print(result.output)
        assert result.exit_code == 1

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

class TestFeatureMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_config_bgp_feature_inconsistent_state(self, get_cmd_module):
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic_3_asics
        reload(mock_multi_asic_3_asics)
        dbconnector.load_namespace_config()
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["bgp", "disabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == config_feature_bgp_inconsistent_state_output
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["bgp", "enabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == config_feature_bgp_inconsistent_state_output

    def test_config_bgp_feature_inconsistent_autorestart(self, get_cmd_module):
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic_3_asics
        reload(mock_multi_asic_3_asics)
        dbconnector.load_namespace_config()
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["bgp", "disabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == config_feature_bgp_inconsistent_autorestart_output
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["bgp", "enabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == config_feature_bgp_inconsistent_autorestart_output

    def test_config_bgp_feature_consistent_state(self, get_cmd_module):
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        dbconnector.load_namespace_config()
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["bgp", "disabled"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["bgp"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_disabled_status_output
        result = runner.invoke(config.config.commands["feature"].commands["state"], ["bgp", "enabled"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["feature"].commands["status"], ["bgp"], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_status_output

    def test_config_bgp_feature_consistent_autorestart(self, get_cmd_module):
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        dbconnector.load_namespace_config()
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["bgp", "disabled"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["bgp"], obj=db)
        print(result.output)
        print(result.exit_code)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_disabled_autorestart_output
        result = runner.invoke(config.config.commands["feature"].commands["autorestart"], ["bgp", "enabled"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["feature"].commands["autorestart"], ["bgp"], obj=db)
        print(result.output)
        print(result.exit_code)
        assert result.exit_code == 0
        assert result.output == show_feature_bgp_autorestart_output
 
 
    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        from .mock_tables import mock_single_asic
        reload(mock_single_asic)
