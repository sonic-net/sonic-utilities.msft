import json
import os
import pytest
from deepdiff import DeepDiff
from dump.helper import create_template_dict
from dump.plugins.evpn import Evpn
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
evpn_files_path = os.path.join(dump_test_input, "vxlan")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['APPL_DB'] = os.path.join(evpn_files_path, "appl_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(evpn_files_path, "asic_db.json")
dedicated_dbs['STATE_DB'] = os.path.join(evpn_files_path, "state_db.json")


def populate_mock(db, db_names):
    for db_name in db_names:
        db.connect(db_name)
        # Delete any default data
        db.delete_all_by_pattern(db_name, "*")
        with open(dedicated_dbs[db_name]) as f:
            mock_json = json.load(f)
        for key in mock_json:
            for field, value in mock_json[key].items():
                db.set(db_name, key, field, value)


@pytest.fixture(scope="class", autouse=True)
def match_engine():

    print("SETUP")
    os.environ["VERBOSE"] = "1"

    # Monkey Patch the SonicV2Connector Object
    from ...mock_tables import dbconnector
    db = SonicV2Connector()

    # popualate the db with mock data
    db_names = list(dedicated_dbs.keys())
    try:
        populate_mock(db, db_names)
    except Exception as e:
        assert False, "Mock initialization failed: " + str(e)

    # Initialize connection pool
    conn_pool = ConnectionPool()
    DEF_NS = ''  # Default Namespace
    conn_pool.cache = {DEF_NS: {'conn': db,
                                'connected_to': set(db_names)}}

    # Initialize match_engine
    match_engine = MatchEngine(conn_pool)
    yield match_engine
    print("TEARDOWN")
    os.environ["VERBOSE"] = "0"


@pytest.mark.usefixtures("match_engine")
class TestEvpnModule:
    def test_working_state(self, match_engine):
        """
        Scenario: When the appl info is properly applied and propagated
        """
        params = {Evpn.ARG_NAME: "Vlan2345:11.1.0.32", "namespace": ""}
        m_evpn = Evpn(match_engine)
        returned = m_evpn.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["keys"].append("VXLAN_REMOTE_VNI_TABLE:Vlan2345:11.1.0.32")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:oid:0x2a0000000007e1")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY:oid:0x2b0000000007e1")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007ea")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007e9")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007ec")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007eb")
        expect["STATE_DB"]["keys"].append("VXLAN_TUNNEL_TABLE|EVPN_11.1.0.32")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_evpn_info(self, match_engine):
        """
        Scenario: When the application table is present and asic_db tables are missing
        """
        params = {Evpn.ARG_NAME: "Vlan2345:11.1.0.33", "namespace": ""}
        m_evpn = Evpn(match_engine)
        returned = m_evpn.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["keys"].append("VXLAN_REMOTE_VNI_TABLE:Vlan2345:11.1.0.33")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY")
        expect["STATE_DB"]["keys"].append("VXLAN_TUNNEL_TABLE|EVPN_11.1.0.33")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_evpn_term(self, match_engine):
        """
        Scenario: When the application table is applied and only SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY is missing
        """
        params = {Evpn.ARG_NAME: "Vlan2345:11.1.0.34", "namespace": ""}
        m_evpn = Evpn(match_engine)
        returned = m_evpn.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["keys"].append("VXLAN_REMOTE_VNI_TABLE:Vlan2345:11.1.0.34")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:oid:0x2a0000000007e2")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007ea")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007e9")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007ec")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007eb")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY")
        expect["STATE_DB"]["keys"].append("VXLAN_TUNNEL_TABLE|EVPN_11.1.0.34")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_state(self, match_engine):
        """
        Scenario: When the application table is applied and state_db table is missing
        """
        params = {Evpn.ARG_NAME: "Vlan2345:11.1.0.35", "namespace": ""}
        m_evpn = Evpn(match_engine)
        returned = m_evpn.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["keys"].append("VXLAN_REMOTE_VNI_TABLE:Vlan2345:11.1.0.35")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:oid:0x2a0000000007e3")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY:oid:0x2b0000000007e3")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007ea")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007e9")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007ec")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007eb")
        expect["STATE_DB"]["tables_not_found"].append("VXLAN_TUNNEL_TABLE")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_no_evpn(self, match_engine):
        """
        Scenario: When the application table is not present
        """
        params = {Evpn.ARG_NAME: "Vlan2345:11.1.0.36", "namespace": ""}
        m_evpn = Evpn(match_engine)
        returned = m_evpn.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["tables_not_found"].append("VXLAN_REMOTE_VNI_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
        expect["STATE_DB"]["tables_not_found"].append("VXLAN_TUNNEL_TABLE")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_all_args(self, match_engine):
        """
        Scenario: Verify Whether the get_all_args method is working as expected
        """
        m_evpn = Evpn(match_engine)
        returned = m_evpn.get_all_args("")
        expect = ["Vlan2345:11.1.0.32", "Vlan2345:11.1.0.33", "Vlan2345:11.1.0.34", "Vlan2345:11.1.0.35"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff
