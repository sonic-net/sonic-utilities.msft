import sys
import os
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

import show.main as show

class TestPsu(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_no_param(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["platform"].commands["psustatus"], [])
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        psus = ["PSU 1", "PSU 2"]
        for i, psu in enumerate(psus):
            assert psu in result_lines[i+2]
        header_lines = 2
        assert len(result_lines) == header_lines + len(psus)

    def test_verbose(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["platform"].commands["psustatus"], ["--verbose"])
        print(result.output)
        assert result.output.split('\n')[0] == "Running command: psushow -s"

    def test_single_psu(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["platform"].commands["psustatus"], ["--index=1"])
        expected = """\
PSU    Status    LED
-----  --------  -----
PSU 1  OK        green
"""
        assert result.output == expected

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

