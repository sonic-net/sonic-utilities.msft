#!/usr/bin/env python

""" This module implements new feature registration/de-registration in SONiC system. """

from typing import Dict, Type

from sonic_package_manager.manifest import Manifest
from sonic_package_manager.service_creator.sonic_db import SonicDB

FEATURE = 'FEATURE'
DEFAULT_FEATURE_CONFIG = {
    'state': 'disabled',
    'auto_restart': 'enabled',
    'high_mem_alert': 'disabled',
    'set_owner': 'local'
}


def is_enabled(cfg):
    return cfg.get('state', 'disabled').lower() == 'enabled'


def is_multi_instance(cfg):
    return str(cfg.get('has_per_asic_scope', 'False')).lower() == 'true'


class FeatureRegistry:
    """ FeatureRegistry class provides an interface to
    register/de-register new feature persistently. """

    def __init__(self, sonic_db: Type[SonicDB]):
        self._sonic_db = sonic_db

    def register(self,
                 manifest: Manifest,
                 state: str = 'disabled',
                 owner: str = 'local'):
        """ Register feature in CONFIG DBs.

        Args:
            manifest: Feature's manifest.
            state: Desired feature admin state.
            owner: Owner of this feature (kube/local).
        Returns:
            None.
        """

        name = manifest['service']['name']
        db_connectors = self._sonic_db.get_connectors()
        cfg_entries = self.get_default_feature_entries(state, owner)
        non_cfg_entries = self.get_non_configurable_feature_entries(manifest)

        for conn in db_connectors:
            current_cfg = conn.get_entry(FEATURE, name)

            new_cfg = cfg_entries.copy()
            # Override configurable entries with CONFIG DB data.
            new_cfg = {**new_cfg, **current_cfg}
            # Override CONFIG DB data with non configurable entries.
            new_cfg = {**new_cfg, **non_cfg_entries}

            conn.set_entry(FEATURE, name, new_cfg)

    def deregister(self, name: str):
        """ Deregister feature by name.

        Args:
            name: Name of the feature in CONFIG DB.
        Returns:
            None
        """

        db_connetors = self._sonic_db.get_connectors()
        for conn in db_connetors:
            conn.set_entry(FEATURE, name, None)

    def update(self,
               old_manifest: Manifest,
               new_manifest: Manifest):
        """ Migrate feature configuration. It can be that non-configurable
        feature entries have to be updated. e.g: "has_timer" for example if
        the new feature introduces a service timer or name of the service has
        changed, but user configurable entries are not changed).

        Args:
            old_manifest: Old feature manifest.
            new_manifest: New feature manifest.
        Returns:
            None
        """

        old_name = old_manifest['service']['name']
        new_name = new_manifest['service']['name']
        db_connectors = self._sonic_db.get_connectors()
        non_cfg_entries = self.get_non_configurable_feature_entries(new_manifest)

        for conn in db_connectors:
            current_cfg = conn.get_entry(FEATURE, old_name)
            conn.set_entry(FEATURE, old_name, None)

            new_cfg = current_cfg.copy()
            # Override CONFIG DB data with non configurable entries.
            new_cfg = {**new_cfg, **non_cfg_entries}

            conn.set_entry(FEATURE, new_name, new_cfg)

    def is_feature_enabled(self, name: str) -> bool:
        """ Returns whether the feature is current enabled
        or not. Accesses running CONFIG DB. If no running CONFIG_DB
        table is found in tables returns False. """

        conn = self._sonic_db.get_running_db_connector()
        if conn is None:
            return False

        cfg = conn.get_entry(FEATURE, name)
        return is_enabled(cfg)

    def get_multi_instance_features(self):
        """ Returns a list of features which run in asic namespace. """

        conn = self._sonic_db.get_initial_db_connector()
        features = conn.get_table(FEATURE)
        return [feature for feature, cfg in features.items() if is_multi_instance(cfg)]

    @staticmethod
    def get_default_feature_entries(state=None, owner=None) -> Dict[str, str]:
        """ Get configurable feature table entries:
        e.g. 'state', 'auto_restart', etc. """

        cfg = DEFAULT_FEATURE_CONFIG.copy()
        if state:
            cfg['state'] = state
        if owner:
            cfg['set_owner'] = owner
        return cfg

    @staticmethod
    def get_non_configurable_feature_entries(manifest) -> Dict[str, str]:
        """ Get non-configurable feature table entries: e.g. 'has_timer' """

        return {
            'has_per_asic_scope': str(manifest['service']['asic-service']),
            'has_global_scope': str(manifest['service']['host-service']),
            'has_timer': str(manifest['service']['delayed']),
        }
