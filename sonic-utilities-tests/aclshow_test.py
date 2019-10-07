import sys
import os
from StringIO import StringIO
import mock

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

from imp import load_source
load_source('aclshow', scripts_path+'/aclshow')
from aclshow import *

import mock_tables.dbconnector

# Expected output for aclshow
default_output = ''+ \
"""RULE NAME     TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
------------  ------------  ------  ---------------  -------------
RULE_1        DATAACL         9999              101            100
RULE_2        DATAACL         9998              201            200
RULE_3        DATAACL         9997              301            300
RULE_4        DATAACL         9996              401            400
RULE_7        DATAACL         9993              701            700
RULE_9        DATAACL         9991              901            900
DEFAULT_RULE  DATAACL            1                2              1
RULE_6        EVERFLOW        9994              601            600
"""

# Expected output for aclshow -a
all_output = '' + \
"""RULE NAME     TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
------------  ------------  ------  ---------------  -------------
RULE_1        DATAACL         9999              101            100
RULE_2        DATAACL         9998              201            200
RULE_3        DATAACL         9997              301            300
RULE_4        DATAACL         9996              401            400
RULE_05       DATAACL         9995                0              0
RULE_7        DATAACL         9993              701            700
RULE_9        DATAACL         9991              901            900
DEFAULT_RULE  DATAACL            1                2              1
RULE_6        EVERFLOW        9994              601            600
RULE_08       EVERFLOW        9992                0              0
"""

# Expected output for aclshow -r RULE_1 -t DATAACL
rule1_dataacl_output = '' + \
"""RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_1       DATAACL         9999              101            100
"""

# Expected output for aclshow -a -r RULE_05
rule05_all_output = ''+ \
"""RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_05      DATAACL         9995                0              0
"""

# Expected output for aclshow -r RULE_0
rule0_output = '' + \
"""RULE NAME    TABLE NAME    PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
"""

# Expected output for aclshow -r RULE_4,RULE_6 -vv
rule4_rule6_verbose_output = '' + \
"""Reading ACL info...
Total number of ACL Tables: 5
Total number of ACL Rules: 10

RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_4       DATAACL         9996              401            400
RULE_6       EVERFLOW        9994              601            600
"""

# Expected output for aclshow -t EVERFLOW
everflow_output = '' + \
"""RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_6       EVERFLOW        9994              601            600
"""

# Expected output for aclshow -t DATAACL
dataacl_output = '' + \
"""RULE NAME     TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
------------  ------------  ------  ---------------  -------------
RULE_1        DATAACL         9999              101            100
RULE_2        DATAACL         9998              201            200
RULE_3        DATAACL         9997              301            300
RULE_4        DATAACL         9996              401            400
RULE_7        DATAACL         9993              701            700
RULE_9        DATAACL         9991              901            900
DEFAULT_RULE  DATAACL            1                2              1
"""

# Expected output for aclshow -c
clear_output = ''

# Expected output for
# aclshow -a -c ; aclshow -a
all_after_clear_output = '' + \
"""RULE NAME     TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
------------  ------------  ------  ---------------  -------------
RULE_1        DATAACL         9999                0              0
RULE_2        DATAACL         9998                0              0
RULE_3        DATAACL         9997                0              0
RULE_4        DATAACL         9996                0              0
RULE_05       DATAACL         9995                0              0
RULE_7        DATAACL         9993                0              0
RULE_9        DATAACL         9991                0              0
DEFAULT_RULE  DATAACL            1                0              0
RULE_6        EVERFLOW        9994                0              0
RULE_08       EVERFLOW        9992                0              0
"""

class Aclshow():
    def __init__(self, *args, **kwargs):
        """
        nullify_on_start, nullify_on_exit will call nullify_counters()
        before and/or after the test. By default - clear on start and exit.
        """
        self.nullify_on_start, self.nullify_on_exit = args if args else (True, True)
        self.kwargs = kwargs
        self.setUp()
        self.runTest()
        self.tearDown()

    def nullify_counters(self):
        """
        This method is used to empty dumped counters
        if exist in /tmp/.counters_acl.p (by default).
        """
        if os.path.isfile(COUNTER_POSITION):
            with open(COUNTER_POSITION, 'wb') as fp:
                json.dump([], fp)

    def runTest(self):
        """
        This method invokes main() from aclshow utility (parametrized by argparse)
        parametrized by mock argparse.
        """
        @mock.patch('argparse.ArgumentParser.parse_args', return_value = argparse.Namespace(**self.kwargs))
        def run(mock_args):
            main()
        run()

    def setUp(self):
        if self.nullify_on_start:
            self.nullify_counters()
        self.old_stdout = sys.stdout
        self.result = StringIO()
        sys.stdout = self.result

    def tearDown(self):
        if self.nullify_on_exit:
            self.nullify_counters()
        sys.stdout = self.old_stdout

# aclshow
def test_default():
    test = Aclshow(all = None, clear = None, rules = None, tables = None, verbose = None)
    assert test.result.getvalue() == default_output

# aclshow -a
def test_all():
    test = Aclshow(all = True, clear = None, rules = None, tables = None, verbose = None)
    assert test.result.getvalue() == all_output

# aclshow -r RULE_1 -t DATAACL
def test_rule1_dataacl():
    test = Aclshow(all = None, clear = None, rules = 'RULE_1', tables = 'DATAACL', verbose = None)
    assert test.result.getvalue() == rule1_dataacl_output

# aclshow -a -r RULE_05
def test_rule05_all():
    test = Aclshow(all = True, clear = None, rules = 'RULE_05', tables = None, verbose = None)
    assert test.result.getvalue() == rule05_all_output

# aclshow -r RULE_0
def test_rule0():
    test = Aclshow(all = None, clear = None, rules = 'RULE_0', tables = None, verbose = None)
    assert test.result.getvalue() == rule0_output

# aclshow -r RULE_4,RULE_6 -vv
def test_rule4_rule6_verbose():
    test = Aclshow(all = None, clear = None, rules = 'RULE_4,RULE_6', tables = None, verbose = True)
    assert test.result.getvalue() == rule4_rule6_verbose_output

# aclshow -t EVERFLOW
def test_everflow():
    test = Aclshow(all=None, clear=None, rules=None, tables='EVERFLOW', verbose=None)
    assert test.result.getvalue() == everflow_output

# aclshow -t DATAACL
def test_dataacl():
    test = Aclshow(all=None, clear=None, rules=None, tables='DATAACL', verbose=None)
    assert test.result.getvalue() == dataacl_output

# aclshow -c
def test_clear():
    test = Aclshow(all=None, clear=True, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == clear_output

# aclshow -a -c ; aclshow -a
def test_all_after_clear():
    nullify_on_start, nullify_on_exit = True, False
    test = Aclshow(nullify_on_start, nullify_on_exit, all=True, clear=True, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == clear_output
    nullify_on_start, nullify_on_exit = False, True
    test = Aclshow(nullify_on_start, nullify_on_exit, all=True, clear=False, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == all_after_clear_output
