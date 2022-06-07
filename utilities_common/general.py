import importlib.machinery
import importlib.util
import sys

from sonic_py_common.multi_asic import is_multi_asic
from swsscommon import swsscommon

def load_module_from_source(module_name, file_path):
    """
    This function will load the Python source file specified by <file_path>
    as a module named <module_name> and return an instance of the module
    """
    loader = importlib.machinery.SourceFileLoader(module_name, file_path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    sys.modules[module_name] = module

    return module

def load_db_config():
    '''
    Load the correct database config file:
     - database_global.json for multi asic
     - database_config.json for single asic
    '''
    if is_multi_asic():
        if not swsscommon.SonicDBConfig.isGlobalInit():
            swsscommon.SonicDBConfig.load_sonic_global_db_config()
    else:
        if not swsscommon.SonicDBConfig.isInit():
            swsscommon.SonicDBConfig.load_sonic_db_config()

def get_optional_value_for_key_in_config_tbl(config_db, port, key, table):
    info_dict = {}
    info_dict = config_db.get_entry(table, port)
    if info_dict is None:
        return None

    value = info_dict.get(key, None)
        
    return value

