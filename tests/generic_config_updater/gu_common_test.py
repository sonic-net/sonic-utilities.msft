import json
import jsonpatch
import sonic_yang
import unittest
from unittest.mock import MagicMock, Mock

from .gutest_helpers import create_side_effect_dict, Files
import generic_config_updater.gu_common as gu_common

class TestConfigWrapper(unittest.TestCase):
    def setUp(self):
        self.config_wrapper_mock = gu_common.ConfigWrapper()
        self.config_wrapper_mock.get_config_db_as_json=MagicMock(return_value=Files.CONFIG_DB_AS_JSON)

    def test_ctor__default_values_set(self):
        config_wrapper = gu_common.ConfigWrapper()

        self.assertEqual("/usr/local/yang-models", gu_common.YANG_DIR)

    def test_get_sonic_yang_as_json__returns_sonic_yang_as_json(self):
        # Arrange
        config_wrapper = self.config_wrapper_mock
        expected = Files.SONIC_YANG_AS_JSON

        # Act
        actual = config_wrapper.get_sonic_yang_as_json()

        # Assert
        self.assertDictEqual(expected, actual)

    def test_convert_config_db_to_sonic_yang__empty_config_db__returns_empty_sonic_yang(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = {}

        # Act
        actual = config_wrapper.convert_config_db_to_sonic_yang({})

        # Assert
        self.assertDictEqual(expected, actual)

    def test_convert_config_db_to_sonic_yang__non_empty_config_db__returns_sonic_yang_as_json(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = Files.SONIC_YANG_AS_JSON

        # Act
        actual = config_wrapper.convert_config_db_to_sonic_yang(Files.CONFIG_DB_AS_JSON)

        # Assert
        self.assertDictEqual(expected, actual)

    def test_convert_sonic_yang_to_config_db__empty_sonic_yang__returns_empty_config_db(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = {}

        # Act
        actual = config_wrapper.convert_sonic_yang_to_config_db({})

        # Assert
        self.assertDictEqual(expected, actual)

    def test_convert_sonic_yang_to_config_db__non_empty_sonic_yang__returns_config_db_as_json(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = Files.CROPPED_CONFIG_DB_AS_JSON

        # Act
        actual = config_wrapper.convert_sonic_yang_to_config_db(Files.SONIC_YANG_AS_JSON)

        # Assert
        self.assertDictEqual(expected, actual)

    def test_convert_sonic_yang_to_config_db__table_name_without_colons__returns_config_db_as_json(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = Files.CROPPED_CONFIG_DB_AS_JSON

        # Act
        actual = config_wrapper.convert_sonic_yang_to_config_db(Files.SONIC_YANG_AS_JSON_WITHOUT_COLONS)

        # Assert
        self.assertDictEqual(expected, actual)

    def test_convert_sonic_yang_to_config_db__table_name_with_unexpected_colons__returns_config_db_as_json(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = Files.CROPPED_CONFIG_DB_AS_JSON

        # Act and assert
        self.assertRaises(ValueError,
                          config_wrapper.convert_sonic_yang_to_config_db,
                          Files.SONIC_YANG_AS_JSON_WITH_UNEXPECTED_COLONS)

    def test_validate_sonic_yang_config__valid_config__returns_true(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = True

        # Act
        actual = config_wrapper.validate_sonic_yang_config(Files.SONIC_YANG_AS_JSON)

        # Assert
        self.assertEqual(expected, actual)

    def test_validate_sonic_yang_config__invvalid_config__returns_false(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = False

        # Act
        actual = config_wrapper.validate_sonic_yang_config(Files.SONIC_YANG_AS_JSON_INVALID)

        # Assert
        self.assertEqual(expected, actual)

    def test_validate_config_db_config__valid_config__returns_true(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = True

        # Act
        actual = config_wrapper.validate_config_db_config(Files.CONFIG_DB_AS_JSON)

        # Assert
        self.assertEqual(expected, actual)

    def test_validate_config_db_config__invalid_config__returns_false(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = False

        # Act
        actual = config_wrapper.validate_config_db_config(Files.CONFIG_DB_AS_JSON_INVALID)

        # Assert
        self.assertEqual(expected, actual)

    def test_crop_tables_without_yang__returns_cropped_config_db_as_json(self):
        # Arrange
        config_wrapper = gu_common.ConfigWrapper()
        expected = Files.CROPPED_CONFIG_DB_AS_JSON

        # Act
        actual = config_wrapper.crop_tables_without_yang(Files.CONFIG_DB_AS_JSON)

        # Assert
        self.assertDictEqual(expected, actual)

class TestPatchWrapper(unittest.TestCase):
    def setUp(self):
        self.config_wrapper_mock = gu_common.ConfigWrapper()
        self.config_wrapper_mock.get_config_db_as_json=MagicMock(return_value=Files.CONFIG_DB_AS_JSON)

    def test_validate_config_db_patch_has_yang_models__table_without_yang_model__returns_false(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()
        patch = [ { 'op': 'remove', 'path': '/TABLE_WITHOUT_YANG' } ]
        expected = False

        # Act
        actual = patch_wrapper.validate_config_db_patch_has_yang_models(patch)

        # Assert
        self.assertEqual(expected, actual)

    def test_validate_config_db_patch_has_yang_models__table_with_yang_model__returns_true(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()
        patch = [ { 'op': 'remove', 'path': '/ACL_TABLE' } ]
        expected = True

        # Act
        actual = patch_wrapper.validate_config_db_patch_has_yang_models(patch)

        # Assert
        self.assertEqual(expected, actual)

    def test_convert_config_db_patch_to_sonic_yang_patch__invalid_config_db_patch__failure(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()
        patch = [ { 'op': 'remove', 'path': '/TABLE_WITHOUT_YANG' } ]

        # Act and Assert
        self.assertRaises(ValueError, patch_wrapper.convert_config_db_patch_to_sonic_yang_patch, patch)

    def test_same_patch__no_diff__returns_true(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()

        # Act and Assert
        self.assertTrue(patch_wrapper.verify_same_json(Files.CONFIG_DB_AS_JSON, Files.CONFIG_DB_AS_JSON))

    def test_same_patch__diff__returns_false(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()

        # Act and Assert
        self.assertFalse(patch_wrapper.verify_same_json(Files.CONFIG_DB_AS_JSON, Files.CROPPED_CONFIG_DB_AS_JSON))

    def test_generate_patch__no_diff__empty_patch(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()

        # Act
        patch = patch_wrapper.generate_patch(Files.CONFIG_DB_AS_JSON, Files.CONFIG_DB_AS_JSON)

        # Assert
        self.assertFalse(patch)

    def test_simulate_patch__empty_patch__no_changes(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()
        patch = jsonpatch.JsonPatch([])
        expected = Files.CONFIG_DB_AS_JSON

        # Act
        actual = patch_wrapper.simulate_patch(patch, Files.CONFIG_DB_AS_JSON)

        # Assert
        self.assertDictEqual(expected, actual)

    def test_simulate_patch__non_empty_patch__changes_applied(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()
        patch = Files.SINGLE_OPERATION_CONFIG_DB_PATCH
        expected = Files.SINGLE_OPERATION_CONFIG_DB_PATCH.apply(Files.CONFIG_DB_AS_JSON)

        # Act
        actual = patch_wrapper.simulate_patch(patch, Files.CONFIG_DB_AS_JSON)

        # Assert
        self.assertDictEqual(expected, actual)

    def test_generate_patch__diff__non_empty_patch(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper()
        after_update_json = Files.SINGLE_OPERATION_CONFIG_DB_PATCH.apply(Files.CONFIG_DB_AS_JSON)
        expected = Files.SINGLE_OPERATION_CONFIG_DB_PATCH

        # Act
        actual = patch_wrapper.generate_patch(Files.CONFIG_DB_AS_JSON, after_update_json)

        # Assert
        self.assertTrue(actual)
        self.assertEqual(expected, actual)

    def test_convert_config_db_patch_to_sonic_yang_patch__empty_patch__returns_empty_patch(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper(config_wrapper = self.config_wrapper_mock)
        patch = jsonpatch.JsonPatch([])
        expected = jsonpatch.JsonPatch([])

        # Act
        actual = patch_wrapper.convert_config_db_patch_to_sonic_yang_patch(patch)

        # Assert
        self.assertEqual(expected, actual)

    def test_convert_config_db_patch_to_sonic_yang_patch__single_operation_patch__returns_sonic_yang_patch(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper(config_wrapper = self.config_wrapper_mock)
        patch = Files.SINGLE_OPERATION_CONFIG_DB_PATCH
        expected = Files.SINGLE_OPERATION_SONIC_YANG_PATCH

        # Act
        actual = patch_wrapper.convert_config_db_patch_to_sonic_yang_patch(patch)

        # Assert
        self.assertEqual(expected, actual)

    def test_convert_config_db_patch_to_sonic_yang_patch__multiple_operations_patch__returns_sonic_yang_patch(self):
        # Arrange
        config_wrapper = self.config_wrapper_mock
        patch_wrapper = gu_common.PatchWrapper(config_wrapper = config_wrapper)
        config_db_patch = Files.MULTI_OPERATION_CONFIG_DB_PATCH

        # Act
        sonic_yang_patch = patch_wrapper.convert_config_db_patch_to_sonic_yang_patch(config_db_patch)

        # Assert
        self.__assert_same_patch(config_db_patch, sonic_yang_patch, config_wrapper, patch_wrapper)

    def test_convert_sonic_yang_patch_to_config_db_patch__empty_patch__returns_empty_patch(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper(config_wrapper = self.config_wrapper_mock)
        patch = jsonpatch.JsonPatch([])
        expected = jsonpatch.JsonPatch([])

        # Act
        actual = patch_wrapper.convert_sonic_yang_patch_to_config_db_patch(patch)

        # Assert
        self.assertEqual(expected, actual)

    def test_convert_sonic_yang_patch_to_config_db_patch__single_operation_patch__returns_config_db_patch(self):
        # Arrange
        patch_wrapper = gu_common.PatchWrapper(config_wrapper = self.config_wrapper_mock)
        patch = Files.SINGLE_OPERATION_SONIC_YANG_PATCH
        expected = Files.SINGLE_OPERATION_CONFIG_DB_PATCH

        # Act
        actual = patch_wrapper.convert_sonic_yang_patch_to_config_db_patch(patch)

        # Assert
        self.assertEqual(expected, actual)

    def test_convert_sonic_yang_patch_to_config_db_patch__multiple_operations_patch__returns_config_db_patch(self):
        # Arrange
        config_wrapper = self.config_wrapper_mock
        patch_wrapper = gu_common.PatchWrapper(config_wrapper = config_wrapper)
        sonic_yang_patch = Files.MULTI_OPERATION_SONIC_YANG_PATCH

        # Act
        config_db_patch = patch_wrapper.convert_sonic_yang_patch_to_config_db_patch(sonic_yang_patch)

        # Assert
        self.__assert_same_patch(config_db_patch, sonic_yang_patch, config_wrapper, patch_wrapper)

    def __assert_same_patch(self, config_db_patch, sonic_yang_patch, config_wrapper, patch_wrapper):
        sonic_yang = config_wrapper.get_sonic_yang_as_json()
        config_db = config_wrapper.get_config_db_as_json()

        after_update_sonic_yang = patch_wrapper.simulate_patch(sonic_yang_patch, sonic_yang)
        after_update_config_db = patch_wrapper.simulate_patch(config_db_patch, config_db)
        after_update_config_db_cropped = config_wrapper.crop_tables_without_yang(after_update_config_db)

        after_update_sonic_yang_as_config_db = \
            config_wrapper.convert_sonic_yang_to_config_db(after_update_sonic_yang)

        self.assertTrue(patch_wrapper.verify_same_json(after_update_config_db_cropped, after_update_sonic_yang_as_config_db))

class TestPathAddressing(unittest.TestCase):
    def setUp(self):
        self.path_addressing = gu_common.PathAddressing()
        self.sy_only_models = sonic_yang.SonicYang(gu_common.YANG_DIR)
        self.sy_only_models.loadYangModel()

    def test_get_path_tokens(self):
        def check(path, tokens):
            expected=tokens
            actual=self.path_addressing.get_path_tokens(path)
            self.assertEqual(expected, actual)

        check("", [])
        check("/", [""])
        check("/token", ["token"])
        check("/more/than/one/token", ["more", "than", "one", "token"])
        check("/has/numbers/0/and/symbols/^", ["has", "numbers", "0", "and", "symbols", "^"])
        check("/~0/this/is/telda", ["~", "this", "is", "telda"])
        check("/~1/this/is/forward-slash", ["/", "this", "is", "forward-slash"])
        check("/\\\\/no-escaping", ["\\\\", "no-escaping"])
        check("////empty/tokens/are/ok", ["", "", "", "empty", "tokens", "are", "ok"])

    def test_create_path(self):
        def check(tokens, path):
            expected=path
            actual=self.path_addressing.create_path(tokens)
            self.assertEqual(expected, actual)

        check([], "",)
        check([""], "/",)
        check(["token"], "/token")
        check(["more", "than", "one", "token"], "/more/than/one/token")
        check(["has", "numbers", "0", "and", "symbols", "^"], "/has/numbers/0/and/symbols/^")
        check(["~", "this", "is", "telda"], "/~0/this/is/telda")
        check(["/", "this", "is", "forward-slash"], "/~1/this/is/forward-slash")
        check(["\\\\", "no-escaping"], "/\\\\/no-escaping")
        check(["", "", "", "empty", "tokens", "are", "ok"], "////empty/tokens/are/ok")
        check(["~token", "telda-not-followed-by-0-or-1"], "/~0token/telda-not-followed-by-0-or-1")

    def test_get_xpath_tokens(self):
        def check(path, tokens):
            expected=tokens
            actual=self.path_addressing.get_xpath_tokens(path)
            self.assertEqual(expected, actual)

        self.assertRaises(ValueError, check, "", [])
        check("/", [])
        check("/token", ["token"])
        check("/more/than/one/token", ["more", "than", "one", "token"])
        check("/multi/tokens/with/empty/last/token/", ["multi", "tokens", "with", "empty", "last", "token", ""])
        check("/has/numbers/0/and/symbols/^", ["has", "numbers", "0", "and", "symbols", "^"])
        check("/has[a='predicate']/in/the/beginning", ["has[a='predicate']", "in", "the", "beginning"])
        check("/ha/s[a='predicate']/in/the/middle", ["ha", "s[a='predicate']", "in", "the", "middle"])
        check("/ha/s[a='predicate-in-the-end']", ["ha", "s[a='predicate-in-the-end']"])
        check("/it/has[more='than'][one='predicate']/somewhere", ["it", "has[more='than'][one='predicate']", "somewhere"])
        check("/ha/s[a='predicate\"with']/double-quotes/inside", ["ha", "s[a='predicate\"with']", "double-quotes", "inside"])
        check('/a/predicate[with="double"]/quotes', ["a", 'predicate[with="double"]', "quotes"])
        check('/multiple["predicate"][with="double"]/quotes', ['multiple["predicate"][with="double"]', "quotes"])
        check('/multiple["predicate"][with="double"]/quotes', ['multiple["predicate"][with="double"]', "quotes"])
        check('/ha/s[a="predicate\'with"]/single-quote/inside', ["ha", 's[a="predicate\'with"]', "single-quote", "inside"])
        # XPATH 1.0 does not support single-quote within single-quoted string. str literal can be '[^']*'
        # Not validating no single-quote within single-quoted string
        check("/a/mix['of''quotes\"does']/not/work/well", ["a", "mix['of''quotes\"does']", "not", "work", "well"])
        # XPATH 1.0 does not support double-quotes within double-quoted string. str literal can be "[^"]*"
        # Not validating no double-quotes within double-quoted string
        check('/a/mix["of""quotes\'does"]/not/work/well', ["a", 'mix["of""quotes\'does"]', "not", "work", "well"])

    def test_create_xpath(self):
        def check(tokens, xpath):
            expected=xpath
            actual=self.path_addressing.create_xpath(tokens)
            self.assertEqual(expected, actual)

        check([], "/")
        check(["token"], "/token")
        check(["more", "than", "one", "token"], "/more/than/one/token")
        check(["multi", "tokens", "with", "empty", "last", "token", ""], "/multi/tokens/with/empty/last/token/")
        check(["has", "numbers", "0", "and", "symbols", "^"], "/has/numbers/0/and/symbols/^")
        check(["has[a='predicate']", "in", "the", "beginning"], "/has[a='predicate']/in/the/beginning")
        check(["ha", "s[a='predicate']", "in", "the", "middle"], "/ha/s[a='predicate']/in/the/middle")
        check(["ha", "s[a='predicate-in-the-end']"], "/ha/s[a='predicate-in-the-end']")
        check(["it", "has[more='than'][one='predicate']", "somewhere"], "/it/has[more='than'][one='predicate']/somewhere")
        check(["ha", "s[a='predicate\"with']", "double-quotes", "inside"], "/ha/s[a='predicate\"with']/double-quotes/inside")
        check(["a", 'predicate[with="double"]', "quotes"], '/a/predicate[with="double"]/quotes')
        check(['multiple["predicate"][with="double"]', "quotes"], '/multiple["predicate"][with="double"]/quotes')
        check(['multiple["predicate"][with="double"]', "quotes"], '/multiple["predicate"][with="double"]/quotes')
        check(["ha", 's[a="predicate\'with"]', "single-quote", "inside"], '/ha/s[a="predicate\'with"]/single-quote/inside')
        # XPATH 1.0 does not support single-quote within single-quoted string. str literal can be '[^']*'
        # Not validating no single-quote within single-quoted string
        check(["a", "mix['of''quotes\"does']", "not", "work", "well"], "/a/mix['of''quotes\"does']/not/work/well", )
        # XPATH 1.0 does not support double-quotes within double-quoted string. str literal can be "[^"]*"
        # Not validating no double-quotes within double-quoted string
        check(["a", 'mix["of""quotes\'does"]', "not", "work", "well"], '/a/mix["of""quotes\'does"]/not/work/well')

    def test_find_ref_paths__ref_is_the_whole_key__returns_ref_paths(self):
        # Arrange
        path = "/PORT/Ethernet0"
        expected = [
            "/ACL_TABLE/NO-NSW-PACL-V4/ports/0",
            "/VLAN_MEMBER/Vlan1000|Ethernet0",
        ]

        # Act
        actual = self.path_addressing.find_ref_paths(path, Files.CROPPED_CONFIG_DB_AS_JSON)

        # Assert
        self.assertCountEqual(expected, actual)

    def test_find_ref_paths__ref_is_a_part_of_key__returns_ref_paths(self):
        # Arrange
        path = "/VLAN/Vlan1000"
        expected = [
            "/VLAN_MEMBER/Vlan1000|Ethernet0",
            "/VLAN_MEMBER/Vlan1000|Ethernet4",
            "/VLAN_MEMBER/Vlan1000|Ethernet8",
        ]

        # Act
        actual = self.path_addressing.find_ref_paths(path, Files.CROPPED_CONFIG_DB_AS_JSON)

        # Assert
        self.assertCountEqual(expected, actual)

    def test_find_ref_paths__ref_is_in_multilist__returns_ref_paths(self):
        # Arrange
        path = "/PORT/Ethernet8"
        expected = [
            "/INTERFACE/Ethernet8",
            "/INTERFACE/Ethernet8|10.0.0.1~130",
        ]

        # Act
        actual = self.path_addressing.find_ref_paths(path, Files.CONFIG_DB_WITH_INTERFACE)

        # Assert
        self.assertCountEqual(expected, actual)

    def test_find_ref_paths__ref_is_in_leafref_union__returns_ref_paths(self):
        # Arrange
        path = "/PORTCHANNEL/PortChannel0001"
        expected = [
            "/ACL_TABLE/NO-NSW-PACL-V4/ports/1",
        ]

        # Act
        actual = self.path_addressing.find_ref_paths(path, Files.CONFIG_DB_WITH_PORTCHANNEL_AND_ACL)

        # Assert
        self.assertCountEqual(expected, actual)

    def test_find_ref_paths__path_is_table__returns_ref_paths(self):
        # Arrange
        path = "/PORT"
        expected = [
            "/ACL_TABLE/DATAACL/ports/0",
            "/ACL_TABLE/EVERFLOW/ports/0",
            "/ACL_TABLE/EVERFLOWV6/ports/0",
            "/ACL_TABLE/EVERFLOWV6/ports/1",
            "/ACL_TABLE/NO-NSW-PACL-V4/ports/0",
            "/VLAN_MEMBER/Vlan1000|Ethernet0",
            "/VLAN_MEMBER/Vlan1000|Ethernet4",
            "/VLAN_MEMBER/Vlan1000|Ethernet8",
        ]

        # Act
        actual = self.path_addressing.find_ref_paths(path, Files.CROPPED_CONFIG_DB_AS_JSON)

        # Assert
        self.assertCountEqual(expected, actual)

    def test_find_ref_paths__whole_config_path__returns_all_refs(self):
        # Arrange
        path = ""
        expected = [
            "/ACL_TABLE/DATAACL/ports/0",
            "/ACL_TABLE/EVERFLOW/ports/0",
            "/ACL_TABLE/EVERFLOWV6/ports/0",
            "/ACL_TABLE/EVERFLOWV6/ports/1",
            "/ACL_TABLE/NO-NSW-PACL-V4/ports/0",
            "/VLAN_MEMBER/Vlan1000|Ethernet0",
            "/VLAN_MEMBER/Vlan1000|Ethernet4",
            "/VLAN_MEMBER/Vlan1000|Ethernet8",
        ]

        # Act
        actual = self.path_addressing.find_ref_paths(path, Files.CROPPED_CONFIG_DB_AS_JSON)

        # Assert
        self.assertCountEqual(expected, actual)

    def test_convert_path_to_xpath(self):
        def check(path, xpath, config=None):
            if not config:
                config = Files.CROPPED_CONFIG_DB_AS_JSON

            expected=xpath
            actual=self.path_addressing.convert_path_to_xpath(path, config, self.sy_only_models)
            self.assertEqual(expected, actual)

        check(path="", xpath="/")
        check(path="/VLAN_MEMBER", xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER")
        check(path="/VLAN/Vlan1000/dhcp_servers",
              xpath="/sonic-vlan:sonic-vlan/VLAN/VLAN_LIST[name='Vlan1000']/dhcp_servers")
        check(path="/VLAN/Vlan1000/dhcp_servers/0",
              xpath="/sonic-vlan:sonic-vlan/VLAN/VLAN_LIST[name='Vlan1000']/dhcp_servers[.='192.0.0.1']")
        check(path="/PORT/Ethernet0/lanes", xpath="/sonic-port:sonic-port/PORT/PORT_LIST[name='Ethernet0']/lanes")
        check(path="/ACL_TABLE/NO-NSW-PACL-V4/ports/0",
              xpath="/sonic-acl:sonic-acl/ACL_TABLE/ACL_TABLE_LIST[ACL_TABLE_NAME='NO-NSW-PACL-V4']/ports[.='Ethernet0']")
        check(path="/ACL_TABLE/NO-NSW-PACL-V4/ports/0",
              xpath="/sonic-acl:sonic-acl/ACL_TABLE/ACL_TABLE_LIST[ACL_TABLE_NAME='NO-NSW-PACL-V4']/ports[.='Ethernet0']")
        check(path="/VLAN_MEMBER/Vlan1000|Ethernet8/tagging_mode",
             xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode")
        check(path="/VLAN_MEMBER/Vlan1000|Ethernet8",
              xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']")
        check(path="/DEVICE_METADATA/localhost/hwsku",
              xpath="/sonic-device_metadata:sonic-device_metadata/DEVICE_METADATA/localhost/hwsku",
              config=Files.CONFIG_DB_WITH_DEVICE_METADATA)
        check(path="/FLEX_COUNTER_TABLE/BUFFER_POOL_WATERMARK/FLEX_COUNTER_STATUS",
              xpath="/sonic-flex_counter:sonic-flex_counter/FLEX_COUNTER_TABLE/BUFFER_POOL_WATERMARK/FLEX_COUNTER_STATUS",
              config=Files.CONTRAINER_WITH_CONTAINER_CONFIG_DB)
        check(path="/ACL_RULE/SSH_ONLY|RULE1/L4_SRC_PORT",
              xpath="/sonic-acl:sonic-acl/ACL_RULE/ACL_RULE_LIST[ACL_TABLE_NAME='SSH_ONLY'][RULE_NAME='RULE1']/L4_SRC_PORT",
              config=Files.CONFIG_DB_CHOICE)
        check(path="/INTERFACE/Ethernet8",
              xpath="/sonic-interface:sonic-interface/INTERFACE/INTERFACE_LIST[name='Ethernet8']",
              config=Files.CONFIG_DB_WITH_INTERFACE)
        check(path="/INTERFACE/Ethernet8|10.0.0.1~130",
              xpath="/sonic-interface:sonic-interface/INTERFACE/INTERFACE_IPPREFIX_LIST[name='Ethernet8'][ip-prefix='10.0.0.1/30']",
              config=Files.CONFIG_DB_WITH_INTERFACE)
        check(path="/INTERFACE/Ethernet8|10.0.0.1~130/scope",
              xpath="/sonic-interface:sonic-interface/INTERFACE/INTERFACE_IPPREFIX_LIST[name='Ethernet8'][ip-prefix='10.0.0.1/30']/scope",
              config=Files.CONFIG_DB_WITH_INTERFACE)
        check(path="/PORTCHANNEL_INTERFACE",
              xpath="/sonic-portchannel:sonic-portchannel/PORTCHANNEL_INTERFACE",
              config=Files.CONFIG_DB_WITH_PORTCHANNEL_INTERFACE)
        check(path="/PORTCHANNEL_INTERFACE/PortChannel0001|1.1.1.1~124",
              xpath="/sonic-portchannel:sonic-portchannel/PORTCHANNEL_INTERFACE/PORTCHANNEL_INTERFACE_IPPREFIX_LIST[name='PortChannel0001'][ip_prefix='1.1.1.1/24']",
              config=Files.CONFIG_DB_WITH_PORTCHANNEL_INTERFACE)

    def test_convert_xpath_to_path(self):
        def check(xpath, path, config=None):
            if not config:
                config = Files.CROPPED_CONFIG_DB_AS_JSON

            expected=path
            actual=self.path_addressing.convert_xpath_to_path(xpath, config, self.sy_only_models)
            self.assertEqual(expected, actual)

        check(xpath="/",path="")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER", path="/VLAN_MEMBER")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST",path="/VLAN_MEMBER")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']",
              path="/VLAN_MEMBER/Vlan1000|Ethernet8")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/name",
              path="/VLAN_MEMBER/Vlan1000|Ethernet8")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/port",
              path="/VLAN_MEMBER/Vlan1000|Ethernet8")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode",
              path="/VLAN_MEMBER/Vlan1000|Ethernet8/tagging_mode")
        check(xpath="/sonic-vlan:sonic-acl/ACL_RULE", path="/ACL_RULE")
        check(xpath="/sonic-vlan:sonic-acl/ACL_RULE/ACL_RULE_LIST[ACL_TABLE_NAME='SSH_ONLY'][RULE_NAME='RULE1']",
              path="/ACL_RULE/SSH_ONLY|RULE1",
              config=Files.CONFIG_DB_CHOICE)
        check(xpath="/sonic-acl:sonic-acl/ACL_RULE/ACL_RULE_LIST[ACL_TABLE_NAME='SSH_ONLY'][RULE_NAME='RULE1']/L4_SRC_PORT",
              path="/ACL_RULE/SSH_ONLY|RULE1/L4_SRC_PORT",
              config=Files.CONFIG_DB_CHOICE)
        check(xpath="/sonic-vlan:sonic-vlan/VLAN/VLAN_LIST[name='Vlan1000']/dhcp_servers",
              path="/VLAN/Vlan1000/dhcp_servers")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN/VLAN_LIST[name='Vlan1000']/dhcp_servers[.='192.0.0.1']",
              path="/VLAN/Vlan1000/dhcp_servers/0")
        check(xpath="/sonic-port:sonic-port/PORT/PORT_LIST[name='Ethernet0']/lanes", path="/PORT/Ethernet0/lanes")
        check(xpath="/sonic-acl:sonic-acl/ACL_TABLE/ACL_TABLE_LIST[ACL_TABLE_NAME='NO-NSW-PACL-V4']/ports[.='Ethernet0']",
              path="/ACL_TABLE/NO-NSW-PACL-V4/ports/0")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']/tagging_mode",
              path="/VLAN_MEMBER/Vlan1000|Ethernet8/tagging_mode")
        check(xpath="/sonic-vlan:sonic-vlan/VLAN_MEMBER/VLAN_MEMBER_LIST[name='Vlan1000'][port='Ethernet8']",
              path="/VLAN_MEMBER/Vlan1000|Ethernet8")
        check(xpath="/sonic-device_metadata:sonic-device_metadata/DEVICE_METADATA/localhost/hwsku",
              path="/DEVICE_METADATA/localhost/hwsku",
              config=Files.CONFIG_DB_WITH_DEVICE_METADATA)
        check(xpath="/sonic-flex_counter:sonic-flex_counter/FLEX_COUNTER_TABLE/BUFFER_POOL_WATERMARK",
              path="/FLEX_COUNTER_TABLE/BUFFER_POOL_WATERMARK",
              config=Files.CONTRAINER_WITH_CONTAINER_CONFIG_DB)
        check(xpath="/sonic-flex_counter:sonic-flex_counter/FLEX_COUNTER_TABLE/BUFFER_POOL_WATERMARK/FLEX_COUNTER_STATUS",
              path="/FLEX_COUNTER_TABLE/BUFFER_POOL_WATERMARK/FLEX_COUNTER_STATUS",
              config=Files.CONTRAINER_WITH_CONTAINER_CONFIG_DB)
        check(xpath="/sonic-interface:sonic-interface/INTERFACE/INTERFACE_LIST[name='Ethernet8']",
              path="/INTERFACE/Ethernet8",
              config=Files.CONFIG_DB_WITH_INTERFACE)
        check(xpath="/sonic-interface:sonic-interface/INTERFACE/INTERFACE_IPPREFIX_LIST[name='Ethernet8'][ip-prefix='10.0.0.1/30']",
              path="/INTERFACE/Ethernet8|10.0.0.1~130",
              config=Files.CONFIG_DB_WITH_INTERFACE)
        check(xpath="/sonic-interface:sonic-interface/INTERFACE/INTERFACE_IPPREFIX_LIST[name='Ethernet8'][ip-prefix='10.0.0.1/30']/scope",
              path="/INTERFACE/Ethernet8|10.0.0.1~130/scope",
              config=Files.CONFIG_DB_WITH_INTERFACE)
        check(xpath="/sonic-portchannel:sonic-portchannel/PORTCHANNEL_INTERFACE",
              path="/PORTCHANNEL_INTERFACE",
              config=Files.CONFIG_DB_WITH_PORTCHANNEL_INTERFACE)
        check(xpath="/sonic-portchannel:sonic-portchannel/PORTCHANNEL_INTERFACE/PORTCHANNEL_INTERFACE_IPPREFIX_LIST[name='PortChannel0001'][ip_prefix='1.1.1.1/24']",
              path="/PORTCHANNEL_INTERFACE/PortChannel0001|1.1.1.1~124",
              config=Files.CONFIG_DB_WITH_PORTCHANNEL_INTERFACE)

