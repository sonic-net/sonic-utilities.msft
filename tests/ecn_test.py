import json
import os
import sys

from click.testing import CliRunner

import config.main as config
from .ecn_input.ecn_test_vectors import *
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestEcnConfig(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def test_ecn_show_config(self):
        self.executor(testData['ecn_show_config'])

    def test_ecn_config_gmin(self):
        self.executor(testData['ecn_cfg_gmin'])

    def test_ecn_config_gmax(self):
        self.executor(testData['ecn_cfg_gmax'])

    def test_ecn_config_ymin(self):
        self.executor(testData['ecn_cfg_ymin'])

    def test_ecn_config_ymax(self):
        self.executor(testData['ecn_cfg_ymax'])

    def test_ecn_config_rmin(self):
        self.executor(testData['ecn_cfg_gmin'])

    def test_ecn_config_rmax(self):
        self.executor(testData['ecn_cfg_gmax'])

    def test_ecn_config_gdrop(self):
        self.executor(testData['ecn_cfg_gdrop'])

    def test_ecn_config_ydrop(self):
        self.executor(testData['ecn_cfg_ydrop'])

    def test_ecn_config_rdrop(self):
        self.executor(testData['ecn_cfg_rdrop'])

    def test_ecn_config_multi_set(self):
        self.executor(testData['ecn_cfg_multi_set'])

    def test_ecn_config_gmin_gmax_invalid(self):
        self.executor(testData['ecn_cfg_gmin_gmax_invalid'])

    def test_ecn_config_ymin_ymax_invalid(self):
        self.executor(testData['ecn_cfg_ymin_ymax_invalid'])

    def test_ecn_config_rmin_rmax_invalid(self):
        self.executor(testData['ecn_cfg_rmin_rmax_invalid'])

    def test_ecn_config_rmax_invalid(self):
        self.executor(testData['ecn_cfg_rmax_invalid'])

    def test_ecn_config_rdrop_invalid(self):
        self.executor(testData['ecn_cfg_rdrop_invalid'])

    def executor(self, input):
        runner = CliRunner()

        if 'show' in input['cmd']:
            exec_cmd = show.cli.commands["ecn"]
        else:
            exec_cmd = config.config.commands["ecn"]

        result = runner.invoke(exec_cmd, input['args'])

        print(result.exit_code)
        print(result.output)

        if input['rc'] == 0:
            assert result.exit_code == 0
        else:
            assert result.exit_code != 0

        if 'cmp_args' in input:
            fd = open('/tmp/ecnconfig', 'r')
            prof_data = json.load(fd)
            for args in input['cmp_args']:
                profile, name, value = args.split(',')
                assert(prof_data[profile][name] == value)
            fd.close()

        if 'rc_msg' in input:
            assert input['rc_msg'] in result.output

        if 'rc_output' in input:
            assert result.output == input['rc_output']

    @classmethod
    def teardown_class(cls):
        os.environ['PATH'] = os.pathsep.join(os.environ['PATH'].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        if os.path.isfile('/tmp/ecnconfig'):
            os.remove('/tmp/ecnconfig')
        print("TEARDOWN")
