import imp
import os
import shutil
import sys

from click.testing import CliRunner

import show.main as show

from utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

show_pfc_counters_output = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4     400     401     402     403     404     405     406     407
Ethernet8     800     801     802     803     804     805     806     807

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4     400     401     402     403     404     405     406     407
Ethernet8     800     801     802     803     804     805     806     807
"""

show_pfc_counters_output_diff = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4       0       0       0       0       0       0       0       0
Ethernet8       0       0       0       0       0       0       0       0

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4       0       0       0       0       0       0       0       0
Ethernet8       0       0       0       0       0       0       0       0
"""

show_pfc_counters_all = """\
     Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0     400     201     202     203     204     205     206     207
   Ethernet4     400     401     402     403     404     405     406     407
Ethernet-BP0     600     601     602     603     604     605     606     607
Ethernet-BP4     800     801     802     803     804     805     806     807

     Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0     400     201     202     203     204     205     206     207
   Ethernet4     400     401     402     403     404     405     406     407
Ethernet-BP0     600     601     602     603     604     605     606     607
Ethernet-BP4     800     801     802     803     804     805     806     807
"""

show_pfc_counters_asic0_frontend = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0     400     201     202     203     204     205     206     207
Ethernet4     400     401     402     403     404     405     406     407

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0     400     201     202     203     204     205     206     207
Ethernet4     400     401     402     403     404     405     406     407
"""

show_pfc_counters_msaic_output_diff = """\
     Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0       0       0       0       0       0       0       0       0
   Ethernet4       0       0       0       0       0       0       0       0
Ethernet-BP0       0       0       0       0       0       0       0       0
Ethernet-BP4       0       0       0       0       0       0       0       0

     Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0       0       0       0       0       0       0       0       0
   Ethernet4       0       0       0       0       0       0       0       0
Ethernet-BP0       0       0       0       0       0       0       0       0
Ethernet-BP4       0       0       0       0       0       0       0       0
"""


def pfc_clear(expected_output):
    counters_file_list = ['0tx', '0rx']
    uid = str(os.getuid())
    cnstat_dir = os.path.join(os.sep, "tmp", "pfcstat-{}".format(uid))
    shutil.rmtree(cnstat_dir, ignore_errors=True, onerror=None)

    return_code, result = get_result_and_return_code(
        'pfcstat -c'
    )

    # verify that files are created with stats
    cnstat_fqn_file_rx = "{}rx".format(uid)
    cnstat_fqn_file_tx = "{}tx".format(uid)
    file_list = [cnstat_fqn_file_tx, cnstat_fqn_file_rx]
    file_list.sort()
    files = os.listdir(cnstat_dir)
    files.sort()
    assert files == file_list

    return_code, result = get_result_and_return_code(
        'pfcstat -s all'
    )
    result_stat = [s for s in result.split("\n") if "Last cached" not in s]
    expected = expected_output.split("\n")
    # this will also verify the saved counters are correct since the
    # expected counters are all '0s'
    assert result_stat == expected
    shutil.rmtree(cnstat_dir, ignore_errors=True, onerror=None)


class TestPfcstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    def test_pfc_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            []
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfc_counters_output

    def test_pfc_clear(self):
        pfc_clear(show_pfc_counters_output_diff)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"


class TestMultiAsicPfcstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        imp.reload(show)

    def test_pfc_counters_all(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfc_counters_all

    def test_pfc_counters_frontend(self):
        return_code, result = get_result_and_return_code(
            'pfcstat -s frontend'
        )
        assert return_code == 0
        assert result == show_pfc_counters_asic0_frontend

    def test_pfc_counters_asic(self):
        return_code, result = get_result_and_return_code(
            'pfcstat -n asic0'
        )
        assert return_code == 0
        assert result == show_pfc_counters_asic0_frontend

    def test_pfc_counters_asic_all(self):
        return_code, result = get_result_and_return_code(
            'pfcstat -n asic0 -s all'
        )
        assert return_code == 0
        assert result == show_pfc_counters_all

    def test_pfc_clear(self):
        pfc_clear(show_pfc_counters_msaic_output_diff)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
