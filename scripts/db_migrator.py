#!/usr/bin/env python

import traceback
import sys
import argparse
import syslog
from swsssdk import ConfigDBConnector, SonicDBConfig
from swsssdk import SonicV2Connector
import sonic_device_util


SYSLOG_IDENTIFIER = 'db_migrator'


def log_info(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()


def log_error(msg):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()


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
        self.CURRENT_VERSION = 'version_1_0_3'

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
                log_info('Migrating interface table for ' + key[0])
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

        if_db = []
        data = self.appDB.keys(self.appDB.APPL_DB, "INTF_TABLE:*")
        for key in data:
            if_name = key.split(":")[1]
            if if_name == "lo":
                self.appDB.delete(self.appDB.APPL_DB, key)
                key = key.replace(if_name, "Loopback0")
                log_info('Migrating lo entry to ' + key)
                self.appDB.set(self.appDB.APPL_DB, key, 'NULL', 'NULL')

            if '/' not in key:
                if_db.append(key.split(":")[1])
                continue

        data = self.appDB.keys(self.appDB.APPL_DB, "INTF_TABLE:*")
        for key in data:
            if_name = key.split(":")[1]
            if if_name in if_db:
                continue
            log_info('Migrating intf table for ' + if_name)
            table = "INTF_TABLE:" + if_name
            self.appDB.set(self.appDB.APPL_DB, table, 'NULL', 'NULL')
            if_db.append(if_name)

    def mlnx_migrate_buffer_pool_size(self):
        """
        On Mellanox platform the buffer pool size changed since 
        version with new SDK 4.3.3052, SONiC to SONiC update 
        from version with old SDK will be broken without migration.
        This migration is specifically for Mellanox platform. 
        """
        # Buffer pools defined in version 1_0_2
        buffer_pools = ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool']

        # Old default buffer pool values on Mellanox platform 
        spc1_t0_default_value = [{'ingress_lossless_pool': '4194304'}, {'egress_lossless_pool': '16777152'}, {'ingress_lossy_pool': '7340032'}, {'egress_lossy_pool': '7340032'}]
        spc1_t1_default_value = [{'ingress_lossless_pool': '2097152'}, {'egress_lossless_pool': '16777152'}, {'ingress_lossy_pool': '5242880'}, {'egress_lossy_pool': '5242880'}]
        spc2_t0_default_value = [{'ingress_lossless_pool': '8224768'}, {'egress_lossless_pool': '35966016'}, {'ingress_lossy_pool': '8224768'}, {'egress_lossy_pool': '8224768'}]
        spc2_t1_default_value = [{'ingress_lossless_pool': '12042240'}, {'egress_lossless_pool': '35966016'}, {'ingress_lossy_pool': '12042240'}, {'egress_lossy_pool': '12042240'}]

        # New default buffer pool configuration on Mellanox platform
        spc1_t0_default_config = {"ingress_lossless_pool": { "size": "5029836", "type": "ingress", "mode": "dynamic" },
                                  "ingress_lossy_pool": { "size": "5029836", "type": "ingress", "mode": "dynamic" },
                                  "egress_lossless_pool": { "size": "14024599", "type": "egress", "mode": "dynamic" },
                                  "egress_lossy_pool": {"size": "5029836", "type": "egress", "mode": "dynamic" } }
        spc1_t1_default_config = {"ingress_lossless_pool": { "size": "2097100", "type": "ingress", "mode": "dynamic" },
                                  "ingress_lossy_pool": { "size": "2097100", "type": "ingress", "mode": "dynamic" },
                                  "egress_lossless_pool": { "size": "14024599", "type": "egress", "mode": "dynamic" },
                                  "egress_lossy_pool": {"size": "2097100", "type": "egress", "mode": "dynamic" } }
        spc2_t0_default_config = {"ingress_lossless_pool": { "size": "14983147", "type": "ingress", "mode": "dynamic" },
                                  "ingress_lossy_pool": { "size": "14983147", "type": "ingress", "mode": "dynamic" },
                                  "egress_lossless_pool": { "size": "34340822", "type": "egress", "mode": "dynamic" },
                                  "egress_lossy_pool": {"size": "14983147", "type": "egress", "mode": "dynamic" } }
        spc2_t1_default_config = {"ingress_lossless_pool": { "size": "9158635", "type": "ingress", "mode": "dynamic" },
                                  "ingress_lossy_pool": { "size": "9158635", "type": "ingress", "mode": "dynamic" },
                                  "egress_lossless_pool": { "size": "34340822", "type": "egress", "mode": "dynamic" },
                                  "egress_lossy_pool": {"size": "9158635", "type": "egress", "mode": "dynamic" } }
        # 3800 platform has gearbox installed so the buffer pool size is different with other Spectrum2 platform
        spc2_3800_t0_default_config = {"ingress_lossless_pool": { "size": "28196784", "type": "ingress", "mode": "dynamic" },
                                  "ingress_lossy_pool": { "size": "28196784", "type": "ingress", "mode": "dynamic" },
                                  "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                  "egress_lossy_pool": {"size": "28196784", "type": "egress", "mode": "dynamic" } }
        spc2_3800_t1_default_config = {"ingress_lossless_pool": { "size": "17891280", "type": "ingress", "mode": "dynamic" },
                                  "ingress_lossy_pool": { "size": "17891280", "type": "ingress", "mode": "dynamic" },
                                  "egress_lossless_pool": { "size": "34340832", "type": "egress", "mode": "dynamic" },
                                  "egress_lossy_pool": {"size": "17891280", "type": "egress", "mode": "dynamic" } }
 
        # Try to get related info from DB
        buffer_pool_conf = {}
        device_data = self.configDB.get_table('DEVICE_METADATA')
        if 'localhost' in device_data.keys():
            hwsku = device_data['localhost']['hwsku']
            platform = device_data['localhost']['platform']
        else:
            log_error("Trying to get DEVICE_METADATA from DB but doesn't exist, skip migration")
            return False
        buffer_pool_conf = self.configDB.get_table('BUFFER_POOL')

        # Get current buffer pool configuration, only migrate configuration which 
        # with default values, if it's not default, leave it as is.
        pool_size_in_db_list = []
        pools_in_db = buffer_pool_conf.keys()

        # Buffer pool numbers is different with default, don't need migrate
        if len(pools_in_db) != len(buffer_pools):
            return True

        # If some buffer pool is not default ones, don't need migrate
        for buffer_pool in buffer_pools:
            if buffer_pool not in pools_in_db:
                return True
            pool_size_in_db_list.append({buffer_pool: buffer_pool_conf[buffer_pool]['size']})
        
        # To check if the buffer pool size is equal to old default values
        new_buffer_pool_conf = None
        if pool_size_in_db_list == spc1_t0_default_value:
            new_buffer_pool_conf = spc1_t0_default_config
        elif pool_size_in_db_list == spc1_t1_default_value:
            new_buffer_pool_conf = spc1_t1_default_config
        elif pool_size_in_db_list == spc2_t0_default_value:
            if platform == 'x86_64-mlnx_msn3800-r0':
                new_buffer_pool_conf = spc2_3800_t0_default_config
            else:
                new_buffer_pool_conf = spc2_t0_default_config
        elif pool_size_in_db_list == spc2_t1_default_value:
            if platform == 'x86_64-mlnx_msn3800-r0':
                new_buffer_pool_conf = spc2_3800_t1_default_config
            else:
                new_buffer_pool_conf = spc2_t1_default_config
        else:
            # It's not using default buffer pool configuration, no migration needed.
            log_info("buffer pool size is not old default value, no need to migrate")
            return True
        # Migrate old buffer conf to latest.
        for pool in buffer_pools:
            self.configDB.set_entry('BUFFER_POOL', pool, new_buffer_pool_conf[pool])
        log_info("Successfully migrate mlnx buffer pool size to the latest.")
        return True

    def version_unknown(self):
        """
        version_unknown tracks all SONiC versions that doesn't have a version
        string defined in config_DB.
        Nothing can be assumped when migrating from this version to the next
        version.
        Any migration operation needs to test if the DB is in expected format
        before migrating date to the next version.
        """

        log_info('Handling version_unknown')

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
        log_info('Handling version_1_0_1')

        self.migrate_interface_table()
        self.migrate_intf_table()
        self.set_version('version_1_0_2')
        return 'version_1_0_2'

    def version_1_0_2(self):
        """
        Version 1_0_2.
        """
        log_info('Handling version_1_0_2')
        # Check ASIC type, if Mellanox platform then need DB migration
        version_info = sonic_device_util.get_sonic_version_info()
        if version_info['asic_type'] == "mellanox":
            if self.mlnx_migrate_buffer_pool_size():
                self.set_version('version_1_0_3')
        else:
            self.set_version('version_1_0_3')
        return None

    def version_1_0_3(self):
        """
        Current latest version. Nothing to do here.
        """
        log_info('Handling version_1_0_3')

        return None

    def get_version(self):
        version = self.configDB.get_entry(self.TABLE_NAME, self.TABLE_KEY)
        if version and version[self.TABLE_FIELD]:
            return version[self.TABLE_FIELD]

        return 'version_unknown'


    def set_version(self, version=None):
        if not version:
            version = self.CURRENT_VERSION
        log_info('Setting version to ' + version)
        entry = { self.TABLE_FIELD : version }
        self.configDB.set_entry(self.TABLE_NAME, self.TABLE_KEY, entry)


    def migrate(self):
        version = self.get_version()
        log_info('Upgrading from version ' + version)
        while version:
            next_version = getattr(self, version)()
            if next_version == version:
                raise Exception('Version migrate from %s stuck in same version' % version)
            version = next_version


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
        log_error('Caught exception: ' + str(e))
        traceback.print_exc()
        print(str(e))
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
