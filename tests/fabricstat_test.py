import os
import shutil

from click.testing import CliRunner

import clear.main as clear
import show.main as show
from .utils import get_result_and_return_code

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

multi_asic_fabric_counters = """\
  ASIC    PORT    STATE    IN_CELL    IN_OCTET    OUT_CELL    OUT_OCTET    CRC    FEC_CORRECTABLE    FEC_UNCORRECTABLE    SYMBOL_ERR
------  ------  -------  ---------  ----------  ----------  -----------  -----  -----------------  -------------------  ------------
     0       0       up          6        1113           0            0      0                  5           1759692040             5
     0       1     down          0           0           0            0      0                  0          58977677898             0
     0       2       up          2         371           0            0      0                  0           1769448760             0
     0       3     down          0           0           0            0      0                  0          58976477608             0
     0       4       up         10        1855           0            0      0                 73           1763293100            73
     0       5     down          0           0           0            0      0              44196          58975150569             0
     0       6       up          4         742           0            0      0                 10           1763174090             0
     0       7       up         10        1855           0            0      0                187           1768439529          1331

  ASIC    PORT    STATE    IN_CELL    IN_OCTET    OUT_CELL    OUT_OCTET    CRC    FEC_CORRECTABLE    FEC_UNCORRECTABLE    SYMBOL_ERR
------  ------  -------  ---------  ----------  ----------  -----------  -----  -----------------  -------------------  ------------
     1       0       up         16        2968           0            0      0                  0           1763890500             0
     1       1     down          0           0           0            0      0                  0         105269481425             0
     1       2     down          0           0           0            0      0                  0         105268895944             0
     1       3     down          0           0           0            0      0                  0         105268290607             0
     1       4       up         14        2597           0            0      0                  0           1762188940             0
     1       5     down          0           0           0            0      0                968         105267020477             0
     1       6     down          0           0           0            0      0        53192703023              1422986   41913682074
     1       7     down          0           0           0            0      0                  0         105264567398             0

"""
multi_asic_fabric_counters_asic0 = """\
  ASIC    PORT    STATE    IN_CELL    IN_OCTET    OUT_CELL    OUT_OCTET    CRC    FEC_CORRECTABLE    FEC_UNCORRECTABLE    SYMBOL_ERR
------  ------  -------  ---------  ----------  ----------  -----------  -----  -----------------  -------------------  ------------
     0       0       up          6        1113           0            0      0                  5           1759692040             5
     0       1     down          0           0           0            0      0                  0          58977677898             0
     0       2       up          2         371           0            0      0                  0           1769448760             0
     0       3     down          0           0           0            0      0                  0          58976477608             0
     0       4       up         10        1855           0            0      0                 73           1763293100            73
     0       5     down          0           0           0            0      0              44196          58975150569             0
     0       6       up          4         742           0            0      0                 10           1763174090             0
     0       7       up         10        1855           0            0      0                187           1768439529          1331

"""

fabric_invalid_asic_error = """ValueError: Unknown Namespace asic99"""

multi_asic_fabric_counters_queue = """\
  ASIC    PORT    STATE    QUEUE_ID    CURRENT_BYTE    CURRENT_LEVEL    WATERMARK_LEVEL
------  ------  -------  ----------  --------------  ---------------  -----------------
     0       0       up           0             763               12                 20
     0       1     down           0               0                0                  0
     0       2       up           0             104                8                  8
     0       3     down           0               0                0                  0
     0       4       up           0            1147               14                 22
     0       5     down           0               0                0                  0
     0       6       up           0             527                8                 10
     0       7       up           0            1147               14                 17

  ASIC    PORT    STATE    QUEUE_ID    CURRENT_BYTE    CURRENT_LEVEL    WATERMARK_LEVEL
------  ------  -------  ----------  --------------  ---------------  -----------------
     1       0       up           0            1942               18                 24
     1       1     down           0               0                0                  0
     1       2     down           0               0                0                  0
     1       3     down           0               0                0                  0
     1       4       up           0            1362               15                 24
     1       5     down           0               0                0                  0
     1       6     down           0               0                0                  0
     1       7     down           0               0                0                  0

"""

multi_asic_fabric_counters_queue_asic0 = """\
  ASIC    PORT    STATE    QUEUE_ID    CURRENT_BYTE    CURRENT_LEVEL    WATERMARK_LEVEL
------  ------  -------  ----------  --------------  ---------------  -----------------
     0       0       up           0             763               12                 20
     0       1     down           0               0                0                  0
     0       2       up           0             104                8                  8
     0       3     down           0               0                0                  0
     0       4       up           0            1147               14                 22
     0       5     down           0               0                0                  0
     0       6       up           0             527                8                 10
     0       7       up           0            1147               14                 17

"""

multi_asic_fabric_reachability = """\

asic0
  Local Link    Remote Module    Remote Link    Status
------------  ---------------  -------------  --------
           0                0             79        up
           2                0             94        up
           4                0             85        up
           6                0             84        up
           7                0             93        up

asic1
  Local Link    Remote Module    Remote Link    Status
------------  ---------------  -------------  --------
           0                0             69        up
           4                0             75        up
"""

multi_asic_fabric_reachability_asic0 = """\

asic0
  Local Link    Remote Module    Remote Link    Status
------------  ---------------  -------------  --------
           0                0             79        up
           2                0             94        up
           4                0             85        up
           6                0             84        up
           7                0             93        up
"""

class TestFabricStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_single_show_fabric_counters(self):
        from .mock_tables import mock_single_asic
        import importlib
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config
        dbconnector.load_namespace_config()

        return_code, result = get_result_and_return_code('fabricstat')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_asic0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""


class TestMultiAsicFabricStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def test_multi_show_fabric_counters(self):
        return_code, result = get_result_and_return_code('fabricstat')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters

    def test_multi_show_fabric_counters_asic(self):
        return_code, result = get_result_and_return_code('fabricstat -n asic0')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_asic0

    def test_multi_asic_invalid_asic(self):
        return_code, result = get_result_and_return_code('fabricstat -n asic99')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == fabric_invalid_asic_error

    def test_multi_show_fabric_counters_queue(self):
        return_code, result = get_result_and_return_code('fabricstat -q')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_queue

    def test_multi_show_fabric_counters_queue_asic(self):
        return_code, result = get_result_and_return_code('fabricstat -q -n asic0')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_queue_asic0

    def test_multi_show_fabric_reachability(self):
        return_code, result = get_result_and_return_code('fabricstat -r')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_reachability

    def test_multi_show_fabric_reachability_asic(self):
        return_code, result = get_result_and_return_code('fabricstat -r -n asic0')
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_reachability_asic0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
