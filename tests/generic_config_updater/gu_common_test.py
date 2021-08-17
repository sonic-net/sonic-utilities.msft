import json
import jsonpatch
import unittest
from unittest.mock import MagicMock, Mock
from .gutest_helpers import create_side_effect_dict, Files

import generic_config_updater.gu_common as gu_common

# import sys
# sys.path.insert(0,'../../generic_config_updater')
# import gu_common

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
