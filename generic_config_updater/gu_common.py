import json
import jsonpatch
import sonic_yang
import subprocess
import copy

YANG_DIR = "/usr/local/yang-models"

class GenericConfigUpdaterError(Exception):
    pass

class JsonChange:
    # TODO: Implement JsonChange
    pass

class ConfigWrapper:
    def __init__(self, yang_dir = YANG_DIR):
        self.yang_dir = YANG_DIR

    def get_config_db_as_json(self):
        text = self._get_config_db_as_text()
        return json.loads(text)

    def _get_config_db_as_text(self):
        # TODO: Getting configs from CLI is very slow, need to get it from sonic-cffgen directly
        cmd = "show runningconfiguration all"
        result = subprocess.Popen(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        text, err = result.communicate()
        return_code = result.returncode
        if return_code: # non-zero means failure
            raise GenericConfigUpdaterError(f"Failed to get running config, Return code: {return_code}, Error: {err}")
        return text

    def get_sonic_yang_as_json(self):
        config_db_json = self.get_config_db_as_json()
        return self.convert_config_db_to_sonic_yang(config_db_json)

    def convert_config_db_to_sonic_yang(self, config_db_as_json):
        sy = sonic_yang.SonicYang(self.yang_dir)
        sy.loadYangModel()

        # Crop config_db tables that do not have sonic yang models
        cropped_config_db_as_json = self.crop_tables_without_yang(config_db_as_json)

        sonic_yang_as_json = dict()

        sy._xlateConfigDBtoYang(cropped_config_db_as_json, sonic_yang_as_json)

        return sonic_yang_as_json

    def convert_sonic_yang_to_config_db(self, sonic_yang_as_json):
        sy = sonic_yang.SonicYang(self.yang_dir)
        sy.loadYangModel()

        # replace container of the format 'module:table' with just 'table'
        new_sonic_yang_json = {}
        for module_top in sonic_yang_as_json:
            new_sonic_yang_json[module_top] = {}
            for container in sonic_yang_as_json[module_top]:
                tokens = container.split(':')
                if len(tokens) > 2:
                    raise ValueError(f"Expecting '<module>:<table>' or '<table>', found {container}")
                table = container if len(tokens) == 1 else tokens[1]
                new_sonic_yang_json[module_top][table] = sonic_yang_as_json[module_top][container]

        config_db_as_json = dict()
        sy.xlateJson = new_sonic_yang_json
        sy.revXlateJson = config_db_as_json
        sy._revXlateYangtoConfigDB(new_sonic_yang_json, config_db_as_json)

        return config_db_as_json

    def validate_sonic_yang_config(self, sonic_yang_as_json):
        config_db_as_json = self.convert_sonic_yang_to_config_db(sonic_yang_as_json)

        sy = sonic_yang.SonicYang(self.yang_dir)
        sy.loadYangModel()

        try:
            sy.loadData(config_db_as_json)

            sy.validate_data_tree()
            return True
        except sonic_yang.SonicYangException as ex:
            return False

    def validate_config_db_config(self, config_db_as_json):
        sy = sonic_yang.SonicYang(self.yang_dir)
        sy.loadYangModel()

        try:
            tmp_config_db_as_json = copy.deepcopy(config_db_as_json)

            sy.loadData(tmp_config_db_as_json)

            sy.validate_data_tree()
            return True
        except sonic_yang.SonicYangException as ex:
            return False

    def crop_tables_without_yang(self, config_db_as_json):
        sy = sonic_yang.SonicYang(self.yang_dir)
        sy.loadYangModel()

        sy.jIn = copy.deepcopy(config_db_as_json)

        sy.tablesWithOutYang = dict()

        sy._cropConfigDB()

        return sy.jIn

    def _create_and_connect_config_db(self):
        if self.default_config_db_connector != None:
            return self.default_config_db_connector

        config_db = ConfigDBConnector()
        config_db.connect()
        return config_db

class DryRunConfigWrapper(ConfigWrapper):
    # TODO: implement DryRunConfigWrapper
    # This class will simulate all read/write operations to ConfigDB on a virtual storage unit.
    pass

class PatchWrapper:
    def __init__(self, config_wrapper=None):
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper()

    def validate_config_db_patch_has_yang_models(self, patch):
        config_db = {}
        for operation in patch:
            tokens = operation['path'].split('/')[1:]
            if len(tokens) == 0: # Modifying whole config_db
                tables_dict = {table_name: {} for table_name in operation['value']}
                config_db.update(tables_dict)
            elif not tokens[0]: # Not empty
                raise ValueError("Table name in patch cannot be empty")
            else:
                config_db[tokens[0]] = {}

        cropped_config_db = self.config_wrapper.crop_tables_without_yang(config_db)

        # valid if no tables dropped during cropping
        return len(cropped_config_db.keys()) == len(config_db.keys())

    def verify_same_json(self, expected, actual):
        # patch will be [] if no diff, [] evaluates to False
        return not jsonpatch.make_patch(expected, actual)

    def generate_patch(self, current, target):
        return jsonpatch.make_patch(current, target)

    def simulate_patch(self, patch, jsonconfig):
        return patch.apply(jsonconfig)

    def convert_config_db_patch_to_sonic_yang_patch(self, patch):
        if not(self.validate_config_db_patch_has_yang_models(patch)):
            raise ValueError(f"Given patch is not valid")

        current_config_db = self.config_wrapper.get_config_db_as_json()
        target_config_db = self.simulate_patch(patch, current_config_db)

        current_yang = self.config_wrapper.convert_config_db_to_sonic_yang(current_config_db)
        target_yang = self.config_wrapper.convert_config_db_to_sonic_yang(target_config_db)

        return self.generate_patch(current_yang, target_yang)

    def convert_sonic_yang_patch_to_config_db_patch(self, patch):
        current_yang = self.config_wrapper.get_sonic_yang_as_json()
        target_yang = self.simulate_patch(patch, current_yang)

        current_config_db = self.config_wrapper.convert_sonic_yang_to_config_db(current_yang)
        target_config_db = self.config_wrapper.convert_sonic_yang_to_config_db(target_yang)

        return self.generate_patch(current_config_db, target_config_db)
