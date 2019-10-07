import sys
import os
import pytest

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

from acl_loader import *
from acl_loader.main import *

class TestAclLoader(object):
    def setUp(self):
        pass

    def test_acl_empty(self):
        yang_acl = AclLoader.parse_acl_json(os.path.join(test_path, 'acl_input/empty_acl.json'))
        assert len(yang_acl.acl.acl_sets.acl_set) == 0

    def test_valid(self):
        yang_acl = AclLoader.parse_acl_json(os.path.join(test_path, 'acl_input/acl1.json'))
        assert len(yang_acl.acl.acl_sets.acl_set) == 4

    def test_invalid(self):
        with pytest.raises(AclLoaderException):
            yang_acl = AclLoader.parse_acl_json(os.path.join(test_path, 'acl_input/acl2.json'))

    def test_validate_mirror_action(self):
        ingress_mirror_rule_props = {
            "MIRROR_INGRESS_ACTION": "everflow0"
        }

        egress_mirror_rule_props = {
            "mirror_egress_action": "everflow0"
        }

        acl_loader = AclLoader()
        # switch capability taken from mock_tables/state_db.json SWITCH_CAPABILITY table
        assert acl_loader.validate_actions("EVERFLOW", ingress_mirror_rule_props)
        assert not acl_loader.validate_actions("EVERFLOW", egress_mirror_rule_props)

        assert not acl_loader.validate_actions("EVERFLOW_EGRESS", ingress_mirror_rule_props)
        assert acl_loader.validate_actions("EVERFLOW_EGRESS", egress_mirror_rule_props)

        forward_packet_action = {
            "PACKET_ACTION": "FORWARD"
        }

        drop_packet_action = {
            "PACKET_ACTION": "DROP"
        }

        # switch capability taken from mock_tables/state_db.json SWITCH_CAPABILITY table
        assert acl_loader.validate_actions("DATAACL", forward_packet_action)
        assert not acl_loader.validate_actions("DATAACL", drop_packet_action)
