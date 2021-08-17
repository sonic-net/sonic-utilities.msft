#!/usr/bin/env python

import pytest

from sonic_package_manager.constraint import ComponentConstraints
from sonic_package_manager.manifest import Manifest, ManifestError


def test_manifest_v1_defaults():
    manifest = Manifest.marshal({'package': {'name': 'test',
                                             'version': '1.0.0'},
                                 'service': {'name': 'test'}})
    assert manifest['package']['depends'] == []
    assert manifest['package']['breaks'] == []
    assert manifest['package']['base-os'] == ComponentConstraints()
    assert not manifest['service']['asic-service']
    assert manifest['service']['host-service']


def test_manifest_v1_invalid_version():
    with pytest.raises(ManifestError):
        Manifest.marshal({'package': {'version': 'abc', 'name': 'test'},
                          'service': {'name': 'test'}})


def test_manifest_v1_invalid_package_constraint():
    with pytest.raises(ManifestError):
        Manifest.marshal({'package': {'name': 'test', 'version': '1.0.0',
                                      'depends': ['swss>a']},
                          'service': {'name': 'test'}})


def test_manifest_v1_service_spec():
    manifest = Manifest.marshal({'package': {'name': 'test',
                                             'version': '1.0.0'},
                                 'service': {'name': 'test', 'asic-service': True}})
    assert manifest['service']['asic-service']


def test_manifest_v1_mounts():
    manifest = Manifest.marshal({'version': '1.0.0', 'package': {'name': 'test',
                                                                 'version': '1.0.0'},
                                 'service': {'name': 'cpu-report'},
                                 'container': {'privileged': True,
                                               'mounts': [{'source': 'a', 'target': 'b', 'type': 'bind'}]}})
    assert manifest['container']['mounts'][0]['source'] == 'a'
    assert manifest['container']['mounts'][0]['target'] == 'b'
    assert manifest['container']['mounts'][0]['type'] == 'bind'


def test_manifest_v1_mounts_invalid():
    with pytest.raises(ManifestError):
        Manifest.marshal({'version': '1.0.0', 'package': {'name': 'test', 'version': '1.0.0'},
                          'service': {'name': 'cpu-report'},
                          'container': {'privileged': True,
                                        'mounts': [{'not-source': 'a', 'target': 'b', 'type': 'bind'}]}})


def test_manifest_invalid_root_type():
    manifest_json_input = {'package': { 'name': 'test', 'version': '1.0.0'},
                           'service': {'name': 'test'}, 'container': 'abc'}
    with pytest.raises(ManifestError):
        Manifest.marshal(manifest_json_input)


def test_manifest_invalid_array_type():
    manifest_json_input = {'package': { 'name': 'test', 'version': '1.0.0'},
                           'service': {'name': 'test', 'warm-shutdown': {'after': 'bgp'}}}
    with pytest.raises(ManifestError):
        Manifest.marshal(manifest_json_input)


def test_manifest_v1_unmarshal():
    manifest_json_input = {'package': {'name': 'test', 'version': '1.0.0',
                                       'depends': [
                                           {
                                               'name': 'swss',
                                               'version': '>1.0.0',
                                               'components': {},
                                           }
                                        ]},
                           'service': {'name': 'test'}}
    manifest = Manifest.marshal(manifest_json_input)
    manifest_json = manifest.unmarshal()
    for key, section in manifest_json_input.items():
        for field, value in section.items():
            assert manifest_json[key][field] == value
