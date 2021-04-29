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


class FeatureRegistry:
    """ FeatureRegistry class provides an interface to
    register/de-register new feature persistently. """

    def __init__(self, sonic_db: Type[SonicDB]):
        self._sonic_db = sonic_db

    def register(self,
                 manifest: Manifest,
                 state: str = 'disabled',
                 owner: str = 'local'):
        name = manifest['service']['name']
        for table in self._get_tables():
            cfg_entries = self.get_default_feature_entries(state, owner)
            non_cfg_entries = self.get_non_configurable_feature_entries(manifest)

            exists, current_cfg = table.get(name)

            new_cfg = cfg_entries.copy()
            # Override configurable entries with CONFIG DB data.
            new_cfg = {**new_cfg, **dict(current_cfg)}
            # Override CONFIG DB data with non configurable entries.
            new_cfg = {**new_cfg, **non_cfg_entries}

            table.set(name, list(new_cfg.items()))

    def deregister(self, name: str):
        for table in self._get_tables():
            table._del(name)

    def is_feature_enabled(self, name: str) -> bool:
        """ Returns whether the feature is current enabled
        or not. Accesses running CONFIG DB. If no running CONFIG_DB
        table is found in tables returns False. """

        running_db_table = self._sonic_db.running_table(FEATURE)
        if running_db_table is None:
            return False

        exists, cfg = running_db_table.get(name)
        if not exists:
            return False
        cfg = dict(cfg)
        return cfg.get('state').lower() == 'enabled'

    def get_multi_instance_features(self):
        res = []
        init_db_table = self._sonic_db.initial_table(FEATURE)
        for feature in init_db_table.keys():
            exists, cfg = init_db_table.get(feature)
            assert exists
            cfg = dict(cfg)
            asic_flag = str(cfg.get('has_per_asic_scope', 'False'))
            if asic_flag.lower() == 'true':
                res.append(feature)
        return res

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

    def _get_tables(self):
        tables = []
        running = self._sonic_db.running_table(FEATURE)
        if running is not None:  # it's Ok if there is no database container running
            tables.append(running)
        persistent = self._sonic_db.persistent_table(FEATURE)
        if persistent is not None:  # it's Ok if there is no config_db.json
            tables.append(persistent)
        tables.append(self._sonic_db.initial_table(FEATURE))  # init_cfg.json is must

        return tables
