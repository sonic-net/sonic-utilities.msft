#!/usr/bin/env python

import argparse
import json
import os
import sys
import traceback

from sonic_py_common import device_info, logger
from swsssdk import ConfigDBConnector, SonicDBConfig
from swsscommon.swsscommon import SonicV2Connector

INIT_CFG_FILE = '/etc/sonic/init_cfg.json'
SYSLOG_IDENTIFIER = 'db_migrator'


# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)


class DBMigrator():
    def __init__(self, namespace, socket=None):
        """
        Version string format:
           version_<major>_<minor>_<build>
              major: starting from 1, sequentially incrementing in master
                     branch.
              minor: in github branches, minor version stays in 0. This minor
                     version creates space for private branches derived from
                     github public branches. These private branches shall use
                     none-zero values.
              build: sequentially increase within a minor version domain.
        """
        self.CURRENT_VERSION = 'version_1_0_4'

        self.TABLE_NAME      = 'VERSIONS'
        self.TABLE_KEY       = 'DATABASE'
        self.TABLE_FIELD     = 'VERSION'

        db_kwargs = {}
        if socket:
            db_kwargs['unix_socket_path'] = socket

        if namespace is None:
            self.configDB = ConfigDBConnector(**db_kwargs)
        else:
            self.configDB = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace, **db_kwargs)
        self.configDB.db_connect('CONFIG_DB')

        self.appDB = SonicV2Connector(host='127.0.0.1')
        if self.appDB is not None:
            self.appDB.connect(self.appDB.APPL_DB)

        version_info = device_info.get_sonic_version_info()
        asic_type = version_info.get('asic_type')
        self.asic_type = asic_type

        if asic_type == "mellanox":
            from mellanox_buffer_migrator import MellanoxBufferMigrator
            self.mellanox_buffer_migrator = MellanoxBufferMigrator(self.configDB)

    def migrate_pfc_wd_table(self):
        '''
        Migrate all data entries from table PFC_WD_TABLE to PFC_WD
        '''
        data = self.configDB.get_table('PFC_WD_TABLE')
        for key in data.keys():
            self.configDB.set_entry('PFC_WD', key, data[key])
        self.configDB.delete_table('PFC_WD_TABLE')

    def is_ip_prefix_in_key(self, key):
        '''
        Function to check if IP address is present in the key. If it
        is present, then the key would be a tuple or else, it shall be
        be string
        '''
        return (isinstance(key, tuple))

    def migrate_interface_table(self):
        '''
        Migrate all data from existing INTERFACE table with IP Prefix
        to have an additional ONE entry without IP Prefix. For. e.g, for an entry
        "Vlan1000|192.168.0.1/21": {}", this function shall add an entry without
        IP prefix as ""Vlan1000": {}". This is for VRF compatibility.
        '''
        if_db = []
        if_tables = {
                     'INTERFACE',
                     'PORTCHANNEL_INTERFACE',
                     'VLAN_INTERFACE',
                     'LOOPBACK_INTERFACE'
                    }
        for table in if_tables:
            data = self.configDB.get_table(table)
            for key in data.keys():
                if not self.is_ip_prefix_in_key(key):
                    if_db.append(key)
                    continue

        for table in if_tables:
            data = self.configDB.get_table(table)
            for key in data.keys():
                if not self.is_ip_prefix_in_key(key) or key[0] in if_db:
                    continue
                log.log_info('Migrating interface table for ' + key[0])
                self.configDB.set_entry(table, key[0], data[key])
                if_db.append(key[0])

    def migrate_intf_table(self):
        '''
        Migrate all data from existing INTF table in APP DB during warmboot with IP Prefix
        to have an additional ONE entry without IP Prefix. For. e.g, for an entry
        "Vlan1000:192.168.0.1/21": {}", this function shall add an entry without
        IP prefix as ""Vlan1000": {}". This also migrates 'lo' to 'Loopback0' interface
        '''

        if self.appDB is None:
            return

        data = self.appDB.keys(self.appDB.APPL_DB, "INTF_TABLE:*")

        if data is None:
            return

        if_db = []
        for key in data:
            if_name = key.split(":")[1]
            if if_name == "lo":
                self.appDB.delete(self.appDB.APPL_DB, key)
                key = key.replace(if_name, "Loopback0")
                log.log_info('Migrating lo entry to ' + key)
                self.appDB.set(self.appDB.APPL_DB, key, 'NULL', 'NULL')

            if '/' not in key:
                if_db.append(key.split(":")[1])
                continue

        data = self.appDB.keys(self.appDB.APPL_DB, "INTF_TABLE:*")
        for key in data:
            if_name = key.split(":")[1]
            if if_name in if_db:
                continue
            log.log_info('Migrating intf table for ' + if_name)
            table = "INTF_TABLE:" + if_name
            self.appDB.set(self.appDB.APPL_DB, table, 'NULL', 'NULL')
            if_db.append(if_name)

    def migrate_copp_table(self):
        '''
        Delete the existing COPP table
        '''
        if self.appDB is None:
            return

        keys = self.appDB.keys(self.appDB.APPL_DB, "COPP_TABLE:*")
        if keys is None:
            return
        for copp_key in keys:
            self.appDB.delete(self.appDB.APPL_DB, copp_key)

    def version_unknown(self):
        """
        version_unknown tracks all SONiC versions that doesn't have a version
        string defined in config_DB.
        Nothing can be assumped when migrating from this version to the next
        version.
        Any migration operation needs to test if the DB is in expected format
        before migrating date to the next version.
        """

        log.log_info('Handling version_unknown')

        # NOTE: Uncomment next 3 lines of code when the migration code is in
        #       place. Note that returning specific string is intentional,
        #       here we only intended to migrade to DB version 1.0.1.
        #       If new DB version is added in the future, the incremental
        #       upgrade will take care of the subsequent migrations.
        self.migrate_pfc_wd_table()
        self.migrate_interface_table()
        self.migrate_intf_table()
        self.set_version('version_1_0_2')
        return 'version_1_0_2'

    def version_1_0_1(self):
        """
        Version 1_0_1.
        """
        log.log_info('Handling version_1_0_1')

        self.migrate_interface_table()
        self.migrate_intf_table()
        self.set_version('version_1_0_2')
        return 'version_1_0_2'

    def version_1_0_2(self):
        """
        Version 1_0_2.
        """
        log.log_info('Handling version_1_0_2')
        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_2', 'version_1_0_3'):
                self.set_version('version_1_0_3')
        else:
            self.set_version('version_1_0_3')
        return 'version_1_0_3'

    def version_1_0_3(self):
        """
        Version 1_0_3.
        """
        log.log_info('Handling version_1_0_3')

        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_3', 'version_1_0_4') and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_3', 'version_1_0_4'):
                self.set_version('version_1_0_4')
        else:
            self.set_version('version_1_0_4')

        return 'version_1_0_4'

    def version_1_0_4(self):
        """
        Current latest version. Nothing to do here.
        """
        log.log_info('Handling version_1_0_4')

        return None

    def get_version(self):
        version = self.configDB.get_entry(self.TABLE_NAME, self.TABLE_KEY)
        if version and version[self.TABLE_FIELD]:
            return version[self.TABLE_FIELD]

        return 'version_unknown'


    def set_version(self, version=None):
        if not version:
            version = self.CURRENT_VERSION
        log.log_info('Setting version to ' + version)
        entry = { self.TABLE_FIELD : version }
        self.configDB.set_entry(self.TABLE_NAME, self.TABLE_KEY, entry)


    def common_migration_ops(self):
        try:
            with open(INIT_CFG_FILE) as f:
                init_db = json.load(f)
        except Exception as e:
            raise Exception(str(e))

        for init_cfg_table, table_val in init_db.items():
            data = self.configDB.get_table(init_cfg_table)
            if data:
                # Ignore overriding the values that pre-exist in configDB
                continue
            log.log_info("Migrating table {} from INIT_CFG to config_db".format(init_cfg_table))
            # Update all tables that do not exist in configDB but are present in INIT_CFG
            for init_table_key, init_table_val in table_val.items():
                self.configDB.set_entry(init_cfg_table, init_table_key, init_table_val)

        self.migrate_copp_table()

    def migrate(self):
        version = self.get_version()
        log.log_info('Upgrading from version ' + version)
        while version:
            next_version = getattr(self, version)()
            if next_version == version:
                raise Exception('Version migrate from %s stuck in same version' % version)
            version = next_version
        # Perform common migration ops
        self.common_migration_ops()

def main():
    try:
        parser = argparse.ArgumentParser()

        parser.add_argument('-o',
                            dest='operation',
                            metavar='operation (migrate, set_version, get_version)',
                            type = str,
                            required = False,
                            choices=['migrate', 'set_version', 'get_version'],
                            help = 'operation to perform [default: get_version]',
                            default='get_version')
        parser.add_argument('-s',
                        dest='socket',
                        metavar='unix socket',
                        type = str,
                        required = False,
                        help = 'the unix socket that the desired database listens on',
                        default = None )
        parser.add_argument('-n',
                        dest='namespace',
                        metavar='asic namespace',
                        type = str,
                        required = False,
                        help = 'The asic namespace whose DB instance we need to connect',
                        default = None )
        args = parser.parse_args()
        operation = args.operation
        socket_path = args.socket
        namespace = args.namespace

        if args.namespace is not None:
            SonicDBConfig.load_sonic_global_db_config(namespace=args.namespace)

        if socket_path:
            dbmgtr = DBMigrator(namespace, socket=socket_path)
        else:
            dbmgtr = DBMigrator(namespace)

        result = getattr(dbmgtr, operation)()
        if result:
            print(str(result))

    except Exception as e:
        log.log_error('Caught exception: ' + str(e))
        traceback.print_exc()
        print(str(e))
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
