import copy
import json
import os
import sys
import syslog
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.append("scripts")
import route_check

DESCR = "Description"
ARGS = "args"
RET = "return"
APPL_DB = 0
ASIC_DB = 1
PRE = "pre-value"
UPD = "update"
RESULT = "res"

OP_SET = "SET"
OP_DEL = "DEL"

ROUTE_TABLE = 'ROUTE_TABLE'
INTF_TABLE = 'INTF_TABLE'
RT_ENTRY_TABLE = 'ASIC_STATE'
SEPARATOR = ":"

RT_ENTRY_KEY_PREFIX = 'SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest":\"'
RT_ENTRY_KEY_SUFFIX = '\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000023\"}'

current_test_name = None
current_test_no = None
current_test_data = None

tables_returned = {}

selector_returned = None
subscribers_returned = {}

test_data = {
    "0": {
        DESCR: "basic good one",
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            APPL_DB: {
                ROUTE_TABLE: {
                    "0.0.0.0/0" : { "ifname": "portchannel0" },
                    "10.10.196.12/31" : { "ifname": "portchannel0" },
                    "10.10.196.20/31" : { "ifname": "portchannel0" },
                    "10.10.196.30/31" : { "ifname": "lo" }
                },
                INTF_TABLE: {
                    "PortChannel1013:10.10.196.24/31": {},
                    "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                    "PortChannel1024": {}
                }
            },
            ASIC_DB: {
                RT_ENTRY_TABLE: {
                    RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                }
            }
        }
    },
    "1": {
        DESCR: "With updates",
        ARGS: "route_check -m DEBUG -i 1",
        PRE: {
            APPL_DB: {
                ROUTE_TABLE: {
                    "0.0.0.0/0" : { "ifname": "portchannel0" },
                    "10.10.196.12/31" : { "ifname": "portchannel0" },
                    "10.10.196.20/31" : { "ifname": "portchannel0" },
                    "10.10.196.30/31" : { "ifname": "lo" }
                },
                INTF_TABLE: {
                    "PortChannel1013:10.10.196.24/31": {},
                    "PortChannel1023:2603:10b0:503:df4::5d/126": {}
                }
            },
            ASIC_DB: {
                RT_ENTRY_TABLE: {
                    RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "10.10.10.10/32" + RT_ENTRY_KEY_SUFFIX: {}
                }
            }
        },
        UPD: {
            ASIC_DB: {
                RT_ENTRY_TABLE: {
                    OP_SET: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                    },
                    OP_DEL: {
                        RT_ENTRY_KEY_PREFIX + "10.10.10.10/32" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "2": {
        DESCR: "basic failure one",
        ARGS: "route_check -i 15",
        RET: -1,
        PRE: {
            APPL_DB: {
                ROUTE_TABLE: {
                    "0.0.0.0/0" : { "ifname": "portchannel0" },
                    "10.10.196.12/31" : { "ifname": "portchannel0" },
                    "10.10.196.20/31" : { "ifname": "portchannel0" },
                    "10.10.196.30/31" : { "ifname": "lo" }
                },
                INTF_TABLE: {
                    "PortChannel1013:90.10.196.24/31": {},
                    "PortChannel1023:9603:10b0:503:df4::5d/126": {},
                    "PortChannel1024": {}
                }
            },
            ASIC_DB: {
                RT_ENTRY_TABLE: {
                    RT_ENTRY_KEY_PREFIX + "20.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "20.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "20.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "3603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                }
            }
        },
        RESULT: {
            "missed_ROUTE_TABLE_routes": [
                "10.10.196.12/31",
                "10.10.196.20/31"
            ],
            "missed_INTF_TABLE_entries": [
                "90.10.196.24/32",
                "9603:10b0:503:df4::5d/128"
            ],
            "Unaccounted_ROUTE_ENTRY_TABLE_entries": [
                "20.10.196.12/31",
                "20.10.196.20/31",
                "20.10.196.24/32",
                "3603:10b0:503:df4::5d/128"
            ]
        }
    },
    "3": {
        DESCR: "basic good one with no args",
        ARGS: "route_check",
        PRE: {
            APPL_DB: {
                ROUTE_TABLE: {
                    "0.0.0.0/0" : { "ifname": "portchannel0" },
                    "10.10.196.12/31" : { "ifname": "portchannel0" },
                    "10.10.196.20/31" : { "ifname": "portchannel0" },
                    "10.10.196.30/31" : { "ifname": "lo" }
                },
                INTF_TABLE: {
                    "PortChannel1013:10.10.196.24/31": {},
                    "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                    "PortChannel1024": {}
                }
            },
            ASIC_DB: {
                RT_ENTRY_TABLE: {
                    RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                }
            }
        }
    }
}

def do_start_test(tname, tno, ctdata):
    global current_test_name, current_test_no, current_test_data
    global tables_returned, selector_returned, subscribers_returned

    current_test_name = tname
    current_test_no = tno
    current_test_data = ctdata
    tables_returned = {}

    selector_returned = None
    subscribers_returned = {}

    print("Starting test case {} number={}".format(tname, tno))


def check_subset(d_sub, d_all):
    if type(d_sub) != type(d_all):
        return -1
    if not type(d_sub) is dict:
        ret = 0 if d_sub == d_all else -2
        return ret

    for (k, v) in d_sub.items():
        if not k in d_all:
            return -3
        ret = check_subset(v, d_all[k])
        if ret != 0:
            return ret
    return 0


def recursive_update(d, t):
    assert (type(t) is dict)
    for k in t.keys():
        if type(t[k]) is not dict:
            d.update(t)
            return

        if k not in d:
            d[k] = {}
        recursive_update(d[k], t[k])


class Table:

    def __init__(self, db, tbl):
        self.db = db
        self.tbl = tbl
        self.data = copy.deepcopy(self.get_val(current_test_data[PRE], [db, tbl]))
        # print("Table:init: db={} tbl={} data={}".format(db, tbl, json.dumps(self.data, indent=4)))


    def update(self):
        t = copy.deepcopy(self.get_val(current_test_data.get(UPD, {}),
            [self.db, self.tbl, OP_SET]))
        drop = copy.deepcopy(self.get_val(current_test_data.get(UPD, {}),
                        [self.db, self.tbl, OP_DEL]))
        if t:
            recursive_update(self.data, t)

        for k in drop:
            self.data.pop(k, None)
        return (list(t.keys()), list(drop.keys()))


    def get_val(self, d, keys):
        for k in keys:
            d = d[k] if k in d else {}
        return d


    def getKeys(self):
        return list(self.data.keys())


    def get(self, key):
        ret = copy.deepcopy(self.data.get(key, {}))
        return (True, ret)


db_conns = {"APPL_DB": APPL_DB, "ASIC_DB": ASIC_DB}
def conn_side_effect(arg, _):
    return db_conns[arg]


def table_side_effect(db, tbl):
    if not db in tables_returned:
        tables_returned[db] = {}
    if not tbl in tables_returned[db]:
        tables_returned[db][tbl] = Table(db, tbl)
    return tables_returned[db][tbl]


class mock_selector:
    TIMEOUT = 1
    EMULATE_HANG = False

    def __init__(self):
        self.select_state = 0
        self.select_cnt = 0
        self.subs = None
        # print("Mock Selector constructed")


    def addSelectable(self, subs):
        self.subs = subs
        return 0


    def select(self, timeout):
        # Toggle between good & timeout
        #
        state = self.select_state
        self.subs.update()

        if mock_selector.EMULATE_HANG:
            time.sleep(60)

        if self.select_state == 0:
            self.select_state = self.TIMEOUT
        else:
            time.sleep(timeout)

        return (state, None)


class mock_db_conn:
    def __init__(self, db):
        self.db_name = None
        for (k, v) in db_conns.items():
            if v == db:
                self.db_name = k
        assert self.db_name != None

    def getDbName(self):
        return self.db_name


class mock_subscriber:
    def __init__(self, db, tbl):
        self.state = PRE
        self.db = db
        self.tbl = tbl
        self.dbconn = mock_db_conn(db)
        self.mock_tbl = table_side_effect(self.db, self.tbl)
        self.set_keys = list(self.mock_tbl.data.keys())
        self.del_keys = []


    def update(self):
        if self.state == PRE:
            s_keys, d_keys = self.mock_tbl.update()
            self.set_keys += s_keys
            self.del_keys += d_keys
            self.state = UPD


    def pop(self):
        v = None
        if self.set_keys:
            op = OP_SET
            k = self.set_keys.pop(0)
            v = self.mock_tbl.get(k)[1]
        elif self.del_keys:
            op = OP_DEL
            k = self.del_keys.pop(0)
        else:
            k = ""
            op = ""

        print("state={} k={} op={} v={}".format(self.state, k, op, str(v)))
        return (k, op, v)
   

    def getDbConnector(self):
        return self.dbconn


    def getTableName(self):
        return self.tbl


def subscriber_side_effect(db, tbl):
    global subscribers_returned

    key = "db_{}_tbl_{}".format(db, tbl)
    if not key in subscribers_returned:
        subscribers_returned[key] = mock_subscriber(db, tbl)
    return subscribers_returned[key]


def select_side_effect():
    global selector_returned

    if not selector_returned:
        selector_returned = mock_selector()
    return selector_returned


def table_side_effect(db, tbl):
    if not db in tables_returned:
        tables_returned[db] = {}
    if not tbl in tables_returned[db]:
        tables_returned[db][tbl] = Table(db, tbl)
    return tables_returned[db][tbl]


def set_mock(mock_table, mock_conn, mock_sel, mock_subs):
    mock_conn.side_effect = conn_side_effect
    mock_table.side_effect = table_side_effect
    mock_sel.side_effect = select_side_effect
    mock_subs.side_effect = subscriber_side_effect


class TestRouteCheck(object):
    def setup(self):
        pass

    def init(self):
        route_check.UNIT_TESTING = 1


    @patch("route_check.swsscommon.DBConnector")
    @patch("route_check.swsscommon.Table")
    @patch("route_check.swsscommon.Select")
    @patch("route_check.swsscommon.SubscriberStateTable")
    def test_server(self, mock_subs, mock_sel, mock_table, mock_conn):
        self.init()
        ret = 0

        set_mock(mock_table, mock_conn, mock_sel, mock_subs)
        for (i, ct_data) in test_data.items():
            do_start_test("route_test", i, ct_data)

            with patch('sys.argv', ct_data[ARGS].split()):
                ret, res = route_check.main()
                expect_ret = ct_data[RET] if RET in ct_data else 0
                expect_res = ct_data[RESULT] if RESULT in ct_data else None
                if res:
                    print("res={}".format(json.dumps(res, indent=4)))
                if expect_res:
                    print("expect_res={}".format(json.dumps(expect_res, indent=4)))
                assert ret == expect_ret
                assert res == expect_res


        # Test timeout
        route_check.TIMEOUT_SECONDS = 5
        mock_selector.EMULATE_HANG = True
        ex_raised = False

        try:
            ret, res = route_check.main()
        except Exception as err:
            ex_raised = True
            expect = "timeout occurred"
            ex_str = str(err)
            assert ex_str == expect, "{} != {}".format(ex_str, expect)
        assert ex_raised, "Exception expected"

        # Test print_msg
        route_check.PRINT_MSG_LEN_MAX = 5
        msg = route_check.print_message(syslog.LOG_ERR, "abcdefghi")
        assert len(msg) == 5
        msg = route_check.print_message(syslog.LOG_ERR, "ab")
        assert len(msg) == 2
        msg = route_check.print_message(syslog.LOG_ERR, "abcde")
        assert len(msg) == 5
        msg = route_check.print_message(syslog.LOG_ERR, "a", "b", "c", "d", "e", "f")
        assert len(msg) == 5
               
        





