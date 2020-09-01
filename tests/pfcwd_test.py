import os
import sys

from click.testing import CliRunner
from utilities_common.db import Db

from pfcwd_input.pfcwd_test_vectors import testData

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "pfcwd")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import pfcwd.main as pfcwd

class TestPfcwd(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def test_pfcwd_show_config(self):
        self.executor(testData['pfcwd_show_config'])

    def test_pfcwd_show_config_single_port(self):
        self.executor(testData['pfcwd_show_config_single_port'])

    def test_pfcwd_show_config_multi_port(self):
        self.executor(testData['pfcwd_show_config_multi_port'])

    def test_pfcwd_show_config_invalid_port(self):
        self.executor(testData['pfcwd_show_config_invalid_port'])

    def test_pfcwd_show_stats(self):
        self.executor(testData['pfcwd_show_stats'])

    def test_pfcwd_show_stats_single_queue(self):
        self.executor(testData['pfcwd_show_stats_single_queue'])

    def test_pfcwd_show_stats_multi_queue(self):
        self.executor(testData['pfcwd_show_stats_multi_queue'])

    def test_pfcwd_show_stats_invalid_queue(self):
        self.executor(testData['pfcwd_show_stats_invalid_queue'])

    def executor(self, testcase):
        runner = CliRunner()
        db = Db()

        for input in testcase:
            exec_cmd = ""
            if len(input['cmd']) == 1:
                exec_cmd = pfcwd.cli.commands[input['cmd'][0]]
            else:
                exec_cmd = pfcwd.cli.commands[input['cmd'][0]].commands[input['cmd'][1]]

            if 'db' in input and input['db']:
                result = runner.invoke(exec_cmd, input['args'], obj=db)
            else:
                result = runner.invoke(exec_cmd, input['args'])

            print(result.exit_code)
            print(result.output)

            if input['rc'] == 0:
                assert result.exit_code == 0
            else:
                assert result.exit_code != 0

            if 'rc_msg' in input:
                assert input['rc_msg'] in result.output

            if 'rc_output' in input:
                assert result.output == input['rc_output']

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
