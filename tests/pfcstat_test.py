import imp
import os
import shutil
import sys

from click.testing import CliRunner

import show.main as show

from .utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

show_pfc_counters_output = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0     200     201     202     203     204     205     206     207
Ethernet4     400     401     402     403     404     405     406     407
Ethernet8     800     801     802     803     804     805     806     807

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0     210     211     212     213     214     215     216     217
Ethernet4     410     411     412     413     414     415     416     417
Ethernet8     810     811     812     813     814     815     816     817
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
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0     200     201     202     203     204     205     206     207
     Ethernet4     400     401     402     403     404     405     406     407
  Ethernet-BP0     600     601     602     603     604     605     606     607
  Ethernet-BP4     800     801     802     803     804     805     806     807
Ethernet-BP256     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A
Ethernet-BP260     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A

       Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0     210     211     212     213     214     215     216     217
     Ethernet4     410     411     412     413     414     415     416     417
  Ethernet-BP0     610     611     612     613     614     615     616     617
  Ethernet-BP4     810     811     812     813     814     815     816     817
Ethernet-BP256     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A
Ethernet-BP260     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A
"""

show_pfc_counters_all_asic = """\
     Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0     200     201     202     203     204     205     206     207
   Ethernet4     400     401     402     403     404     405     406     407
Ethernet-BP0     600     601     602     603     604     605     606     607
Ethernet-BP4     800     801     802     803     804     805     806     807

     Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0     210     211     212     213     214     215     216     217
   Ethernet4     410     411     412     413     414     415     416     417
Ethernet-BP0     610     611     612     613     614     615     616     617
Ethernet-BP4     810     811     812     813     814     815     816     817
"""
show_pfc_counters_all = """\
       Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0     200     201     202     203     204     205     206     207
     Ethernet4     400     401     402     403     404     405     406     407
  Ethernet-BP0     600     601     602     603     604     605     606     607
  Ethernet-BP4     800     801     802     803     804     805     806     807
Ethernet-BP256     900     901     902     903     904     905     906     907
Ethernet-BP260     100     101     102     103     104     105     106     107

       Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0     210     211     212     213     214     215     216     217
     Ethernet4     410     411     412     413     414     415     416     417
  Ethernet-BP0     610     611     612     613     614     615     616     617
  Ethernet-BP4     810     811     812     813     814     815     816     817
Ethernet-BP256     910     911     912     913     914     915     916     917
Ethernet-BP260     110     111     112     113     114     115     116     117
"""

show_pfc_counters_asic0_frontend = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0     200     201     202     203     204     205     206     207
Ethernet4     400     401     402     403     404     405     406     407

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0     210     211     212     213     214     215     216     217
Ethernet4     410     411     412     413     414     415     416     417
"""

show_pfc_counters_msaic_output_diff = """\
       Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0       0       0       0       0       0       0       0       0
     Ethernet4       0       0       0       0       0       0       0       0
  Ethernet-BP0       0       0       0       0       0       0       0       0
  Ethernet-BP4       0       0       0       0       0       0       0       0
Ethernet-BP256       0       0       0       0       0       0       0       0
Ethernet-BP260       0       0       0       0       0       0       0       0

       Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0       0       0       0       0       0       0       0       0
     Ethernet4       0       0       0       0       0       0       0       0
  Ethernet-BP0       0       0       0       0       0       0       0       0
  Ethernet-BP4       0       0       0       0       0       0       0       0
Ethernet-BP256       0       0       0       0       0       0       0       0
Ethernet-BP260       0       0       0       0       0       0       0       0
"""


def del_cached_stats():
    uid = str(os.getuid())
    cnstat_dir = os.path.join(os.sep, "tmp", "pfcstat-{}".format(uid))
    shutil.rmtree(cnstat_dir, ignore_errors=True, onerror=None)


def pfc_clear(expected_output):
    counters_file_list = ['0tx', '0rx']
    del_cached_stats()

    return_code, result = get_result_and_return_code(
        'pfcstat -c'
    )

    # verify that files are created with stats
    uid = str(os.getuid())
    cnstat_dir = os.path.join(os.sep, "tmp", "pfcstat-{}".format(uid))
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
    del_cached_stats()


class TestPfcstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        del_cached_stats()

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
        del_cached_stats()



class TestMultiAsicPfcstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        del_cached_stats()

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
        assert result == show_pfc_counters_all_asic

    def test_masic_pfc_clear(self):
        pfc_clear(show_pfc_counters_msaic_output_diff)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        del_cached_stats()
