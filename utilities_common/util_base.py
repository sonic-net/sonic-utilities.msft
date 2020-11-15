try:
    import imp
    import os

    from sonic_py_common import device_info
except ImportError as e:
    raise ImportError (str(e) + " - required module not found")

#
# Constants ====================================================================
#
PDDF_FILE_PATH = '/usr/share/sonic/platform/pddf_support'

EEPROM_MODULE_NAME = 'eeprom'
EEPROM_CLASS_NAME = 'board'


class UtilHelper(object):
    def __init__(self):
        pass

    # Loads platform specific psuutil module from source
    def load_platform_util(self, module_name, class_name):
        platform_util = None

        # Get path to platform and hwsku
        (platform_path, hwsku_path) = device_info.get_paths_to_platform_and_hwsku_dirs()

        try:
            module_file = os.path.join(platform_path, "plugins", module_name + ".py")
            module = imp.load_source(module_name, module_file)
        except IOError as e:
            raise IOError("Failed to load platform module '%s': %s" % (module_name, str(e)))

        try:
            platform_util_class = getattr(module, class_name)
            # board class of eeprom requires 4 paramerters, need special treatment here.
            if module_name == EEPROM_MODULE_NAME and class_name == EEPROM_CLASS_NAME:
                platform_util = platform_util_class('','','','')
            else:
                platform_util = platform_util_class()
        except AttributeError as e:
            raise AttributeError("Failed to instantiate '%s' class: %s" % (class_name, str(e)))

        return platform_util

    def check_pddf_mode(self):
        if os.path.exists(PDDF_FILE_PATH):
            return True
        else:
            return False
