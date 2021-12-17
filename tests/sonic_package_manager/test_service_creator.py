#!/usr/bin/env python

import os
import copy
from unittest.mock import Mock, MagicMock, call

import pytest

from sonic_package_manager.database import PackageEntry
from sonic_package_manager.manifest import Manifest
from sonic_package_manager.metadata import Metadata
from sonic_package_manager.package import Package
from sonic_package_manager.service_creator.creator import *
from sonic_package_manager.service_creator.feature import FeatureRegistry


@pytest.fixture
def manifest():
    return Manifest.marshal({
        'package': {
            'name': 'test',
            'version': '1.0.0',
        },
        'service': {
            'name': 'test',
            'requires': ['database'],
            'after': ['database', 'swss', 'syncd'],
            'before': ['ntp-config'],
            'dependent-of': ['swss'],
            'asic-service': False,
            'host-service': True,
            'warm-shutdown': {
                'before': ['syncd'],
                'after': ['swss'],
            },
            'fast-shutdown': {
                'before': ['swss'],
            },
        },
        'container': {
            'privileged': True,
            'volumes': [
                '/etc/sonic:/etc/sonic:ro'
            ]
        },
        'processes': [
            {
                'name': 'test-process',
                'reconciles': True,
            },
            {
                'name': 'test-process-2',
                'reconciles': False,
            },
            {
                'name': 'test-process-3',
                'reconciles': True,
            },
        ]
    })


def test_service_creator(sonic_fs, manifest, package_manager, mock_feature_registry, mock_sonic_db):
    creator = ServiceCreator(mock_feature_registry, mock_sonic_db)
    entry = PackageEntry('test', 'azure/sonic-test')
    package = Package(entry, Metadata(manifest))
    installed_packages = package_manager._get_installed_packages_and(package)
    creator.create(package)
    creator.generate_shutdown_sequence_files(installed_packages)

    assert sonic_fs.exists(os.path.join(ETC_SONIC_PATH, 'swss_dependent'))
    assert sonic_fs.exists(os.path.join(DOCKER_CTL_SCRIPT_LOCATION, 'test.sh'))
    assert sonic_fs.exists(os.path.join(SERVICE_MGMT_SCRIPT_LOCATION, 'test.sh'))
    assert sonic_fs.exists(os.path.join(SYSTEMD_LOCATION, 'test.service'))

    def read_file(name):
        with open(os.path.join(ETC_SONIC_PATH, name)) as file:
            return file.read()

    assert read_file('warm-reboot_order') == 'swss teamd test syncd'
    assert read_file('fast-reboot_order') == 'teamd test swss syncd'
    assert read_file('test_reconcile') == 'test-process test-process-3'


def test_service_creator_with_timer_unit(sonic_fs, manifest, mock_feature_registry, mock_sonic_db):
    creator = ServiceCreator(mock_feature_registry, mock_sonic_db)
    entry = PackageEntry('test', 'azure/sonic-test')
    package = Package(entry, Metadata(manifest))
    creator.create(package)

    assert not sonic_fs.exists(os.path.join(SYSTEMD_LOCATION, 'test.timer'))

    manifest['service']['delayed'] = True
    package = Package(entry, Metadata(manifest))
    creator.create(package)

    assert sonic_fs.exists(os.path.join(SYSTEMD_LOCATION, 'test.timer'))


def test_service_creator_with_debug_dump(sonic_fs, manifest, mock_feature_registry, mock_sonic_db):
    creator = ServiceCreator(mock_feature_registry, mock_sonic_db)
    entry = PackageEntry('test', 'azure/sonic-test')
    package = Package(entry, Metadata(manifest))
    creator.create(package)

    assert not sonic_fs.exists(os.path.join(DEBUG_DUMP_SCRIPT_LOCATION, 'test'))

    manifest['package']['debug-dump'] = '/some/command'
    package = Package(entry, Metadata(manifest))
    creator.create(package)

    assert sonic_fs.exists(os.path.join(DEBUG_DUMP_SCRIPT_LOCATION, 'test'))


def test_service_creator_initial_config(sonic_fs, manifest, mock_feature_registry, mock_sonic_db):
    mock_connector = Mock()
    mock_connector.get_config = Mock(return_value={})
    mock_sonic_db.get_connectors = Mock(return_value=[mock_connector])

    creator = ServiceCreator(mock_feature_registry, mock_sonic_db)

    entry = PackageEntry('test', 'azure/sonic-test')
    package = Package(entry, Metadata(manifest))
    creator.create(package)

    assert not sonic_fs.exists(os.path.join(DEBUG_DUMP_SCRIPT_LOCATION, 'test'))

    manifest['package']['init-cfg'] = {
        'TABLE_A': {
            'key_a': {
                'field_1': 'value_1',
                'field_2': 'value_2'
            },
        },
    }
    package = Package(entry, Metadata(manifest))

    creator.create(package)
    mock_connector.mod_config.assert_called_with(
        {
            'TABLE_A': {
	            'key_a': {
	                'field_1': 'value_1',
	                'field_2': 'value_2',
	            },
	        },
	    }
    )

    creator.remove(package)
    mock_connector.set_entry.assert_called_with('TABLE_A', 'key_a', None)


def test_feature_registration(mock_sonic_db, manifest):
    mock_connector = Mock()
    mock_connector.get_entry = Mock(return_value={})
    mock_sonic_db.get_connectors = Mock(return_value=[mock_connector])
    feature_registry = FeatureRegistry(mock_sonic_db)
    feature_registry.register(manifest)
    mock_connector.set_entry.assert_called_with('FEATURE', 'test', {
        'state': 'disabled',
        'auto_restart': 'enabled',
        'high_mem_alert': 'disabled',
        'set_owner': 'local',
        'has_per_asic_scope': 'False',
        'has_global_scope': 'True',
        'has_timer': 'False',
    })


def test_feature_update(mock_sonic_db, manifest):
    curr_feature_config = {
        'state': 'enabled',
        'auto_restart': 'enabled',
        'high_mem_alert': 'disabled',
        'set_owner': 'local',
        'has_per_asic_scope': 'False',
        'has_global_scope': 'True',
        'has_timer': 'False',
    }
    mock_connector = Mock()
    mock_connector.get_entry = Mock(return_value=curr_feature_config)
    mock_sonic_db.get_connectors = Mock(return_value=[mock_connector])
    feature_registry = FeatureRegistry(mock_sonic_db)

    new_manifest = copy.deepcopy(manifest)
    new_manifest['service']['name'] = 'test_new'
    new_manifest['service']['delayed'] = True

    feature_registry.update(manifest, new_manifest)

    mock_connector.set_entry.assert_has_calls([
        call('FEATURE', 'test', None),
        call('FEATURE', 'test_new', {
            'state': 'enabled',
            'auto_restart': 'enabled',
            'high_mem_alert': 'disabled',
            'set_owner': 'local',
            'has_per_asic_scope': 'False',
            'has_global_scope': 'True',
            'has_timer': 'True',
        }),
    ], any_order=True)


def test_feature_registration_with_timer(mock_sonic_db, manifest):
    manifest['service']['delayed'] = True
    mock_connector = Mock()
    mock_connector.get_entry = Mock(return_value={})
    mock_sonic_db.get_connectors = Mock(return_value=[mock_connector])
    feature_registry = FeatureRegistry(mock_sonic_db)
    feature_registry.register(manifest)
    mock_connector.set_entry.assert_called_with('FEATURE', 'test', {
        'state': 'disabled',
        'auto_restart': 'enabled',
        'high_mem_alert': 'disabled',
        'set_owner': 'local',
        'has_per_asic_scope': 'False',
        'has_global_scope': 'True',
        'has_timer': 'True',
    })


def test_feature_registration_with_non_default_owner(mock_sonic_db, manifest):
    mock_connector = Mock()
    mock_connector.get_entry = Mock(return_value={})
    mock_sonic_db.get_connectors = Mock(return_value=[mock_connector])
    feature_registry = FeatureRegistry(mock_sonic_db)
    feature_registry.register(manifest, owner='kube')
    mock_connector.set_entry.assert_called_with('FEATURE', 'test', {
        'state': 'disabled',
        'auto_restart': 'enabled',
        'high_mem_alert': 'disabled',
        'set_owner': 'kube',
        'has_per_asic_scope': 'False',
        'has_global_scope': 'True',
        'has_timer': 'False',
    })
