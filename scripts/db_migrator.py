#!/usr/bin/env python3

import os
import argparse
import json
import sys
import traceback
import re

from sonic_py_common import device_info, logger
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector, SonicDBConfig

INIT_CFG_FILE = '/etc/sonic/init_cfg.json'

# mock the redis for unit test purposes #
try:
    if os.environ["UTILITIES_UNIT_TESTING"] == "2":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        tests_path = os.path.join(modules_path, "tests")
        mocked_db_path = os.path.join(tests_path, "db_migrator_input")
        sys.path.insert(0, modules_path)
        sys.path.insert(0, tests_path)
        INIT_CFG_FILE = os.path.join(mocked_db_path, "init_cfg.json")
except KeyError:
    pass

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
        self.CURRENT_VERSION = 'version_2_0_2'

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

        self.stateDB = SonicV2Connector(host='127.0.0.1')
        if self.stateDB is not None:
            self.stateDB.connect(self.stateDB.STATE_DB)

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
        for key in data:
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
            for key in data:
                if not self.is_ip_prefix_in_key(key):
                    if_db.append(key)
                    continue

        for table in if_tables:
            data = self.configDB.get_table(table)
            for key in data:
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

    def migrate_feature_table(self):
        '''
        Combine CONTAINER_FEATURE and FEATURE tables into FEATURE table.
        '''
        feature_table = self.configDB.get_table('FEATURE')
        for feature, config in feature_table.items():
            state = config.get('status')
            if state is not None:
                config['state'] = state
                config.pop('status')
                self.configDB.set_entry('FEATURE', feature, config)

        container_feature_table = self.configDB.get_table('CONTAINER_FEATURE')
        for feature, config in container_feature_table.items():
            self.configDB.mod_entry('FEATURE', feature, config)
            self.configDB.set_entry('CONTAINER_FEATURE', feature, None)

    def migrate_config_db_buffer_tables_for_dynamic_calculation(self, speed_list, cable_len_list, default_dynamic_th, abandon_method, append_item_method):
        '''
        Migrate buffer tables to dynamic calculation mode
        parameters
        @speed_list - list of speed supported
        @cable_len_list - list of cable length supported
        @default_dynamic_th - default dynamic th
        @abandon_method - a function which is called to abandon the migration and keep the current configuration
                          if the current one doesn't match the default one
        @append_item_method - a function which is called to append an item to the list of pending commit items
                              any update to buffer configuration will be pended and won't be applied until
                              all configuration is checked and aligns with the default one

        1. Buffer profiles for lossless PGs in BUFFER_PROFILE table will be removed
           if their names have the convention of pg_lossless_<speed>_<cable_length>_profile
           where the speed and cable_length belongs speed_list and cable_len_list respectively
           and the dynamic_th is equal to default_dynamic_th
        2. Insert tables required for dynamic buffer calculation
           - DEFAULT_LOSSLESS_BUFFER_PARAMETER|AZURE: {'default_dynamic_th': default_dynamic_th}
           - LOSSLESS_TRAFFIC_PATTERN|AZURE: {'mtu': '1024', 'small_packet_percentage': '100'}
        3. For lossless dynamic PGs, remove the explicit referencing buffer profiles
           Before: BUFFER_PG|<port>|3-4: {'profile': 'BUFFER_PROFILE|pg_lossless_<speed>_<cable_length>_profile'}
           After:  BUFFER_PG|<port>|3-4: {'profile': 'NULL'}
        '''
        # Migrate BUFFER_PROFILEs, removing dynamically generated profiles
        dynamic_profile = self.configDB.get_table('BUFFER_PROFILE')
        profile_pattern = 'pg_lossless_([1-9][0-9]*000)_([1-9][0-9]*m)_profile'
        for name, info in dynamic_profile.items():
            m = re.search(profile_pattern, name)
            if not m:
                continue
            speed = m.group(1)
            cable_length = m.group(2)
            if speed in speed_list and cable_length in cable_len_list:
                append_item_method(('BUFFER_PROFILE', name, None))
                log.log_info("Lossless profile {} has been removed".format(name))

        # Migrate BUFFER_PGs, removing the explicit designated profiles
        buffer_pgs = self.configDB.get_table('BUFFER_PG')
        ports = self.configDB.get_table('PORT')
        all_cable_lengths = self.configDB.get_table('CABLE_LENGTH')
        if not buffer_pgs or not ports or not all_cable_lengths:
            log.log_notice("At lease one of tables BUFFER_PG, PORT and CABLE_LENGTH hasn't been defined, skip following migration")
            abandon_method()
            return True

        cable_lengths = all_cable_lengths[list(all_cable_lengths.keys())[0]]
        for name, profile in buffer_pgs.items():
            # do the db migration
            try:
                port, pg = name
                profile_name = profile['profile'][1:-1].split('|')[1]
                if pg == '0':
                    if profile_name != 'ingress_lossy_profile':
                        log.log_notice("BUFFER_PG table entry {} has non default profile {} configured".format(name, profile_name))
                        abandon_method()
                        return True
                    else:
                        continue
                elif pg != '3-4':
                    log.log_notice("BUFFER_PG table entry {} isn't default PG(0 or 3-4)".format(name))
                    abandon_method()
                    return True
                m = re.search(profile_pattern, profile_name)
                if not m:
                    log.log_notice("BUFFER_PG table entry {} has non-default profile name {}".format(name, profile_name))
                    abandon_method()
                    return True
                speed = m.group(1)
                cable_length = m.group(2)

                if speed == ports[port]['speed'] and cable_length == cable_lengths[port]:
                    append_item_method(('BUFFER_PG', name, {'profile': 'NULL'}))
                else:
                    log.log_notice("Lossless PG profile {} for port {} doesn't match its speed {} or cable length {}, keep using traditional buffer calculation mode".format(
                        profile_name, port, speed, cable_length))
                    abandon_method()
                    return True
            except Exception:
                log.log_notice("Exception occured during parsing the profiles")
                abandon_method()
                return True

        # Insert other tables required for dynamic buffer calculation
        metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
        metadata['buffer_model'] = 'dynamic'
        append_item_method(('DEVICE_METADATA', 'localhost', metadata))
        append_item_method(('DEFAULT_LOSSLESS_BUFFER_PARAMETER', 'AZURE', {'default_dynamic_th': default_dynamic_th}))
        append_item_method(('LOSSLESS_TRAFFIC_PATTERN', 'AZURE', {'mtu': '1024', 'small_packet_percentage': '100'}))

        return True

    def prepare_dynamic_buffer_for_warm_reboot(self, buffer_pools=None, buffer_profiles=None, buffer_pgs=None):
        '''
        This is the very first warm reboot of buffermgrd (dynamic) if the system reboot from old image by warm-reboot
        In this case steps need to be taken to get buffermgrd prepared (for warm reboot)

        During warm reboot, buffer tables should be installed in the first place.
        However, it isn't able to achieve that when system is warm-rebooted from an old image
        without dynamic buffer supported, because the buffer info wasn't in the APPL_DB in the old image.
        The solution is to copy that info from CONFIG_DB into APPL_DB in db_migrator.
        During warm-reboot, db_migrator adjusts buffer info in CONFIG_DB by removing some fields
        according to requirement from dynamic buffer calculation.
        The buffer info before that adjustment needs to be copied to APPL_DB.

        1. set WARM_RESTART_TABLE|buffermgrd as {restore_count: 0}
        2. Copy the following tables from CONFIG_DB into APPL_DB in case of warm reboot
           The separator in fields that reference objects in other table needs to be updated from '|' to ':'
           - BUFFER_POOL
           - BUFFER_PROFILE, separator updated for field 'pool'
           - BUFFER_PG, separator updated for field 'profile'
           - BUFFER_QUEUE, separator updated for field 'profile
           - BUFFER_PORT_INGRESS_PROFILE_LIST, separator updated for field 'profile_list'
           - BUFFER_PORT_EGRESS_PROFILE_LIST, separator updated for field 'profile_list'

        '''
        warmreboot_state = self.stateDB.get(self.stateDB.STATE_DB, 'WARM_RESTART_ENABLE_TABLE|system', 'enable')
        mmu_size = self.stateDB.get(self.stateDB.STATE_DB, 'BUFFER_MAX_PARAM_TABLE|global', 'mmu_size')
        if warmreboot_state == 'true' and not mmu_size:
            log.log_notice("This is the very first run of buffermgrd (dynamic), prepare info required from warm reboot")
        else:
            return True

        buffer_table_list = [
            ('BUFFER_POOL', buffer_pools, None),
            ('BUFFER_PROFILE', buffer_profiles, 'pool'),
            ('BUFFER_PG', buffer_pgs, 'profile'),
            ('BUFFER_QUEUE', None, 'profile'),
            ('BUFFER_PORT_INGRESS_PROFILE_LIST', None, 'profile_list'),
            ('BUFFER_PORT_EGRESS_PROFILE_LIST', None, 'profile_list')
        ]

        for pair in buffer_table_list:
            keys_copied = []
            keys_ignored = []
            table_name, entries, reference_field_name = pair
            app_table_name = table_name + "_TABLE"
            if not entries:
                entries = self.configDB.get_table(table_name)
            for key, items in entries.items():
                # copy items to appl db
                if reference_field_name:
                    confdb_ref = items.get(reference_field_name)
                    if not confdb_ref or confdb_ref == "NULL":
                        keys_ignored.append(key)
                        continue
                    items_referenced = confdb_ref.split(',')
                    appdb_ref = ""
                    first_item = True
                    for item in items_referenced:
                        if first_item:
                            first_item = False
                        else:
                            appdb_ref += ','
                        subitems = item.split('|')
                        first_key = True
                        for subitem in subitems:
                            if first_key:
                                appdb_ref += subitem + '_TABLE'
                                first_key = False
                            else:
                                appdb_ref += ':' + subitem

                    items[reference_field_name] = appdb_ref
                keys_copied.append(key)
                if type(key) is tuple:
                    appl_db_key = app_table_name + ':' + ':'.join(key)
                else:
                    appl_db_key = app_table_name + ':' + key
                for field, data in items.items():
                    self.appDB.set(self.appDB.APPL_DB, appl_db_key, field, data)

            if keys_copied:
                log.log_info("The following items in table {} in CONFIG_DB have been copied to APPL_DB: {}".format(table_name, keys_copied))
            if keys_ignored:
                log.log_info("The following items in table {} in CONFIG_DB have been ignored: {}".format(table_name, keys_copied))

        return True

    def migrate_config_db_port_table_for_auto_neg(self):
        table_name = 'PORT'
        port_table = self.configDB.get_table(table_name)
        for key, value in port_table.items():
            if 'autoneg' in value:
                if value['autoneg'] == '1':
                    self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, key), 'autoneg', 'on')
                    if 'speed' in value and 'adv_speeds' not in value:
                        self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, key), 'adv_speeds', value['speed'])
                elif value['autoneg'] == '0':
                    self.configDB.set(self.configDB.CONFIG_DB, '{}|{}'.format(table_name, key), 'autoneg', 'off')

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
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_2', 'version_1_0_3') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_3')
        else:
            self.set_version('version_1_0_3')
        return 'version_1_0_3'

    def version_1_0_3(self):
        """
        Version 1_0_3.
        """
        log.log_info('Handling version_1_0_3')

        self.migrate_feature_table()

        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_3', 'version_1_0_4') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_3', 'version_1_0_4') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_4')
        else:
            self.set_version('version_1_0_4')

        return 'version_1_0_4'

    def version_1_0_4(self):
        """
        Version 1_0_4.
        """
        log.log_info('Handling version_1_0_4')

        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_4', 'version_1_0_5') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_4', 'version_1_0_5') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_5')
        else:
            self.set_version('version_1_0_5')

        return 'version_1_0_5'

    def version_1_0_5(self):
        """
        Version 1_0_5.
        """
        log.log_info('Handling version_1_0_5')

        # Check ASIC type, if Mellanox platform then need DB migration
        if self.asic_type == "mellanox":
            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_5', 'version_1_0_6') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_5', 'version_1_0_6') \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration():
                self.set_version('version_1_0_6')
        else:
            self.set_version('version_1_0_6')

        return 'version_1_0_6'

    def version_1_0_6(self):
        """
        Version 1_0_6.
        """
        log.log_info('Handling version_1_0_6')
        if self.asic_type == "mellanox":
            speed_list = self.mellanox_buffer_migrator.default_speed_list
            cable_len_list = self.mellanox_buffer_migrator.default_cable_len_list
            buffer_pools = self.configDB.get_table('BUFFER_POOL')
            buffer_profiles = self.configDB.get_table('BUFFER_PROFILE')
            buffer_pgs = self.configDB.get_table('BUFFER_PG')
            abandon_method = self.mellanox_buffer_migrator.mlnx_abandon_pending_buffer_configuration
            append_method = self.mellanox_buffer_migrator.mlnx_append_item_on_pending_configuration_list

            if self.mellanox_buffer_migrator.mlnx_migrate_buffer_pool_size('version_1_0_6', 'version_2_0_0') \
               and self.mellanox_buffer_migrator.mlnx_migrate_buffer_profile('version_1_0_6', 'version_2_0_0') \
               and (not self.mellanox_buffer_migrator.mlnx_is_buffer_model_dynamic() or \
                    self.migrate_config_db_buffer_tables_for_dynamic_calculation(speed_list, cable_len_list, '0', abandon_method, append_method)) \
               and self.mellanox_buffer_migrator.mlnx_flush_new_buffer_configuration() \
               and self.prepare_dynamic_buffer_for_warm_reboot(buffer_pools, buffer_profiles, buffer_pgs):
                self.set_version('version_2_0_0')
        else:
            self.prepare_dynamic_buffer_for_warm_reboot()

            metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
            metadata['buffer_model'] = 'traditional'
            self.configDB.set_entry('DEVICE_METADATA', 'localhost', metadata)
            log.log_notice('Setting buffer_model to traditional')

            self.set_version('version_2_0_0')

        return 'version_2_0_0'

    def version_2_0_0(self):
        """
        Version 2_0_0.
        """
        log.log_info('Handling version_2_0_0')
        self.migrate_config_db_port_table_for_auto_neg()
        self.set_version('version_2_0_1')
        return 'version_2_0_1'

    def version_2_0_1(self):
        """
        Version 2_0_1.
        """
        log.log_info('Handling version_2_0_1')
        warmreboot_state = self.stateDB.get(self.stateDB.STATE_DB, 'WARM_RESTART_ENABLE_TABLE|system', 'enable')

        if warmreboot_state != 'true':
            portchannel_table = self.configDB.get_table('PORTCHANNEL')
            for name, data in portchannel_table.items():
                data['lacp_key'] = 'auto'
                self.configDB.set_entry('PORTCHANNEL', name, data)
        self.set_version('version_2_0_2')
        return 'version_2_0_2'

    def version_2_0_2(self):
        """
        Current latest version. Nothing to do here.
        """
        log.log_info('Handling version_2_0_2')
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
            log.log_info("Migrating table {} from INIT_CFG to config_db".format(init_cfg_table))
            for key in table_val:
                curr_cfg = self.configDB.get_entry(init_cfg_table, key)
                init_cfg = table_val[key]

                # Override init config with current config.
                # This will leave new fields from init_config
                # in new_config, but not override existing configuration.
                new_cfg = {**init_cfg, **curr_cfg}
                self.configDB.set_entry(init_cfg_table, key, new_cfg)

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
        else:
            SonicDBConfig.initialize()

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
