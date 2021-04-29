#!/usr/bin/env python

from sonic_package_manager.registry import RegistryResolver


def test_get_registry_for():
    resolver = RegistryResolver()
    registry = resolver.get_registry_for('debian')
    assert registry is resolver.DockerHubRegistry
    registry = resolver.get_registry_for('Azure/sonic')
    assert registry is resolver.DockerHubRegistry
    registry = resolver.get_registry_for('registry-server:5000/docker')
    assert registry.url == 'https://registry-server:5000'
    registry = resolver.get_registry_for('registry-server.com/docker')
    assert registry.url == 'https://registry-server.com'
