import os
import json
import filecmp
import config.main as config

from click.testing import CliRunner
from unittest import mock
from utilities_common.db import Db
from utilities_common.general import load_module_from_source
from minigraph import minigraph_encoder

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "config_override_input")
EMPTY_INPUT = os.path.join(DATA_DIR, "empty_input.json")
PARTIAL_CONFIG_OVERRIDE = os.path.join(DATA_DIR, "partial_config_override.json")
NEW_FEATURE_CONFIG = os.path.join(DATA_DIR, "new_feature_config.json")
FULL_CONFIG_OVERRIDE = os.path.join(DATA_DIR, "full_config_override.json")

# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')


def write_init_config_db(cfgdb, config):
    tables = cfgdb.get_config()
    # delete all tables then write config to configDB
    for table in tables:
        cfgdb.delete_table(table)
    data = dict()
    sonic_cfggen.deep_update(
        data, sonic_cfggen.FormatConverter.to_deserialized(config))
    cfgdb.mod_config(sonic_cfggen.FormatConverter.output_to_db(data))
    return


def read_config_db(cfgdb):
    data = dict()
    sonic_cfggen.deep_update(
        data, sonic_cfggen.FormatConverter.db_to_output(cfgdb.get_config()))
    return sonic_cfggen.FormatConverter.to_serialized(data)


def write_config_to_file(cfgdb, file):
    with open(file, 'w') as f:
        json.dump(cfgdb, f, sort_keys=True, indent=4, cls=minigraph_encoder)
    return


class TestConfigOverride(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        return

    def test_broken_json(self):
        def read_json_file_side_effect(filename):
            return {{"TABLE"}}
        with mock.patch('config.main.read_json_file',
                        mock.MagicMock(side_effect=read_json_file_side_effect)):
            db = Db()
            runner = CliRunner()
            result = runner.invoke(config.config.commands["override-config-table"],
                                   ['golden_config_db.json'], obj=db)

            assert result.exit_code == 1
            assert "Bad format: json file broken" in result.output

    def test_json_is_not_dict(self):
        def read_json_file_side_effect(filename):
            return [{}]
        with mock.patch('config.main.read_json_file',
                        mock.MagicMock(side_effect=read_json_file_side_effect)):
            db = Db()
            runner = CliRunner()
            result = runner.invoke(config.config.commands["override-config-table"],
                                   ['golden_config_db.json'], obj=db)

            assert result.exit_code == 1
            assert "Bad format: input_config_db is not a dict" in result.output

    def test_dry_run(self):
        def read_json_file_side_effect(filename):
            return {}
        db = Db()
        current_config = read_config_db(db.cfgdb)
        with mock.patch('config.main.read_json_file',
                        mock.MagicMock(side_effect=read_json_file_side_effect)):
            runner = CliRunner()
            result = runner.invoke(config.config.commands["override-config-table"],
                                   ['golden_config_db.json', '--dry-run'])

            assert result.exit_code == 0
            assert json.loads(result.output) == current_config

    def test_golden_config_db_empty(self):
        db = Db()
        with open(EMPTY_INPUT, "r") as f:
            read_data = json.load(f)
        self.check_override_config_table(
            db, config, read_data['running_config'], read_data['golden_config'],
            read_data['expected_config'])

    def test_golden_config_db_partial(self):
        """Golden Config only modify ACL_TABLE"""
        db = Db()
        with open(PARTIAL_CONFIG_OVERRIDE, "r") as f:
            read_data = json.load(f)
        self.check_override_config_table(
            db, config, read_data['running_config'], read_data['golden_config'],
            read_data['expected_config'])

    def test_golden_config_db_new_feature(self):
        """Golden Config append NEW_FEATURE_TABLE"""
        db = Db()
        with open(NEW_FEATURE_CONFIG, "r") as f:
            read_data = json.load(f)
        self.check_override_config_table(
            db, config, read_data['running_config'], read_data['golden_config'],
            read_data['expected_config'])

    def test_golden_config_db_full(self):
        """Golden Config makes change to every table in configDB"""
        db = Db()
        with open(FULL_CONFIG_OVERRIDE, "r") as f:
            read_data = json.load(f)
        self.check_override_config_table(
            db, config, read_data['running_config'], read_data['golden_config'],
            read_data['expected_config'])

    def check_override_config_table(self, db, config, running_config,
                                    golden_config, expected_config):
        def read_json_file_side_effect(filename):
            return golden_config
        with mock.patch('config.main.read_json_file',
                        mock.MagicMock(side_effect=read_json_file_side_effect)):
            write_init_config_db(db.cfgdb, running_config)

            runner = CliRunner()
            result = runner.invoke(config.config.commands["override-config-table"],
                                   ['golden_config_db.json'], obj=db)

            current_config = read_config_db(db.cfgdb)
            assert result.exit_code == 0
            assert current_config == expected_config

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        return
