import importlib
import os
import sys

from click.testing import CliRunner
from unittest import mock

import show.main as show
import clear.main as clear

from .utils import get_result_and_return_code
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, scripts_path)

flow_counters_stat_path = os.path.join(scripts_path, 'flow_counters_stat')
flow_counters_stat = load_module_from_source('flow_counters_stat', flow_counters_stat_path)

expect_show_output = """\
  Trap Name    Packets    Bytes      PPS
-----------  ---------  -------  -------
       dhcp        100    2,000  50.25/s
"""

expect_show_output_json = """\
{
    "dhcp": {
        "Bytes": "2,000",
        "PPS": "50.25/s",
        "Packets": "100"
    }
}
"""

expect_show_output_after_clear = """\
  Trap Name    Packets    Bytes      PPS
-----------  ---------  -------  -------
       dhcp          0        0  50.25/s
"""

expect_show_output_multi_asic = """\
  ASIC ID    Trap Name    Packets    Bytes      PPS
---------  -----------  ---------  -------  -------
    asic0         dhcp        100    2,000  50.25/s
    asic1         dhcp        200    3,000  45.25/s
"""

expect_show_output_json_multi_asic = """\
{
    "asic0": {
        "Bytes": "2,000",
        "PPS": "50.25/s",
        "Packets": "100",
        "Trap Name": "dhcp"
    },
    "asic1": {
        "Bytes": "3,000",
        "PPS": "45.25/s",
        "Packets": "200",
        "Trap Name": "dhcp"
    }
}
"""

expect_show_output_multi_asic_after_clear = """\
  ASIC ID    Trap Name    Packets    Bytes      PPS
---------  -----------  ---------  -------  -------
    asic0         dhcp          0        0  50.25/s
    asic1         dhcp          0        0  45.25/s
"""


def delete_cache():
    cmd = 'flow_counters_stat -t trap -d'
    get_result_and_return_code(cmd)


class TestTrapStat:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        delete_cache()

    def test_show(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output

    def test_show_json(self):
        cmd = 'flow_counters_stat -t trap -j'
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_output_json

    def test_clear(self):
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["flowcnt-trap"],
            []
        )
        print(result.output)

        assert result.exit_code == 0

        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output_after_clear

    def test_diff(self):
        args = mock.MagicMock()
        args.type = 'trap'
        args.delete = False
        args.namespace = None
        args.json = False
        stats = flow_counters_stat.FlowCounterStats(args)
        stats._collect = mock.MagicMock()
        old_data = {
            '': {
                'bgp': [100, 200, 50.0, 1],
                'bgpv6': [100, 200, 50.0, 2],
                'lldp': [100, 200, 50.0, 3],
            }
        }
        stats._save(old_data)
        stats.data = {
            '': {
                'bgp': [100, 200, 50.0, 4],
                'bgpv6': [100, 100, 50.0, 2],
                'lldp': [200, 300, 50.0, 3],
            }
        }

        stats._collect_and_diff()
        cached_data = stats._load()
        assert cached_data['']['bgp'] == [0, 0, 50.0, 4]
        assert cached_data['']['bgpv6'] == [0, 0, 50.0, 2]
        assert cached_data['']['lldp'] == [100, 200, 50.0, 3]


class TestTrapStatsMultiAsic:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        delete_cache()

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        delete_cache()
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

    def test_show(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output_multi_asic

    def test_show_json(self):
        cmd = 'flow_counters_stat -t trap -j'
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_output_json_multi_asic

    def test_clear(self):
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["flowcnt-trap"],
            []
        )
        print(result.output)

        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output_multi_asic_after_clear
