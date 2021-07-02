#!/usr/bin/env python

import os
from unittest.mock import Mock, MagicMock

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
    mock_table = Mock()
    mock_table.get = Mock(return_value=(True, (('field_2', 'original_value_2'),)))
    mock_sonic_db.initial_table = Mock(return_value=mock_table)
    mock_sonic_db.persistent_table = Mock(return_value=mock_table)
    mock_sonic_db.running_table = Mock(return_value=mock_table)

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
    mock_table.set.assert_called_with('key_a', [('field_1', 'value_1'),
                                                ('field_2', 'original_value_2')])

    creator.remove(package)
    mock_table._del.assert_called_with('key_a')


def test_feature_registration(mock_sonic_db, manifest):
    mock_feature_table = Mock()
    mock_feature_table.get = Mock(return_value=(False, ()))
    mock_sonic_db.initial_table = Mock(return_value=mock_feature_table)
    mock_sonic_db.persistent_table = Mock(return_value=mock_feature_table)
    mock_sonic_db.running_table = Mock(return_value=mock_feature_table)
    feature_registry = FeatureRegistry(mock_sonic_db)
    feature_registry.register(manifest)
    mock_feature_table.set.assert_called_with('test', [
        ('state', 'disabled'),
        ('auto_restart', 'enabled'),
        ('high_mem_alert', 'disabled'),
        ('set_owner', 'local'),
        ('has_per_asic_scope', 'False'),
        ('has_global_scope', 'True'),
        ('has_timer', 'False'),
    ])


def test_feature_registration_with_timer(mock_sonic_db, manifest):
    manifest['service']['delayed'] = True
    mock_feature_table = Mock()
    mock_feature_table.get = Mock(return_value=(False, ()))
    mock_sonic_db.initial_table = Mock(return_value=mock_feature_table)
    mock_sonic_db.persistent_table = Mock(return_value=mock_feature_table)
    mock_sonic_db.running_table = Mock(return_value=mock_feature_table)
    feature_registry = FeatureRegistry(mock_sonic_db)
    feature_registry.register(manifest)
    mock_feature_table.set.assert_called_with('test', [
        ('state', 'disabled'),
        ('auto_restart', 'enabled'),
        ('high_mem_alert', 'disabled'),
        ('set_owner', 'local'),
        ('has_per_asic_scope', 'False'),
        ('has_global_scope', 'True'),
        ('has_timer', 'True'),
    ])


def test_feature_registration_with_non_default_owner(mock_sonic_db, manifest):
    mock_feature_table = Mock()
    mock_feature_table.get = Mock(return_value=(False, ()))
    mock_sonic_db.initial_table = Mock(return_value=mock_feature_table)
    mock_sonic_db.persistent_table = Mock(return_value=mock_feature_table)
    mock_sonic_db.running_table = Mock(return_value=mock_feature_table)
    feature_registry = FeatureRegistry(mock_sonic_db)
    feature_registry.register(manifest, owner='kube')
    mock_feature_table.set.assert_called_with('test', [
        ('state', 'disabled'),
        ('auto_restart', 'enabled'),
        ('high_mem_alert', 'disabled'),
        ('set_owner', 'kube'),
        ('has_per_asic_scope', 'False'),
        ('has_global_scope', 'True'),
        ('has_timer', 'False'),
    ])
