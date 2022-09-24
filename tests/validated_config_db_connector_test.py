import imp
import os
import mock

imp.load_source('validated_config_db_connector', \
    os.path.join(os.path.dirname(__file__), '..', 'config', 'validated_config_db_connector.py'))
import validated_config_db_connector

from unittest import TestCase
from mock import patch
from generic_config_updater.gu_common import EmptyTableError
from utilities_common.db import Db

SAMPLE_TABLE = 'VLAN'
SAMPLE_KEY = 'Vlan1000'
SAMPLE_VALUE_EMPTY = None


class TestValidatedConfigDBConnector(TestCase):
    '''

        Test Class for validated_config_db_connector.py

    '''
    def test_validated_config_db_connector_empty_table(self): 
        mock_generic_updater = mock.Mock()
        mock_generic_updater.apply_patch = mock.Mock(side_effect=EmptyTableError)
        with mock.patch('validated_config_db_connector.GenericUpdater', return_value=mock_generic_updater):
            remove_entry_success = validated_config_db_connector.validated_set_entry(SAMPLE_TABLE, SAMPLE_KEY, SAMPLE_VALUE_EMPTY)
            assert not remove_entry_success
