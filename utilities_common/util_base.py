
import os
import sonic_platform

# Constants ====================================================================
PDDF_SUPPORT_FILE = '/usr/share/sonic/platform/pddf_support'

# Helper classs


class UtilHelper(object):
    def __init__(self):
        pass

    # try get information from platform API and return a default value if caught NotImplementedError
    def try_get(self, callback, default=None):
        """
        Handy function to invoke the callback and catch NotImplementedError
        :param callback: Callback to be invoked
        :param default: Default return value if exception occur
        :return: Default return value if exception occur else return value of the callback
        """
        try:
            ret = callback()
            if ret is None:
                ret = default
        except NotImplementedError:
            ret = default

        return ret

    # Instantiate platform-specific Chassis class
    def load_platform_chassis(self):
        chassis = None

        # Load 2.0 platform API chassis class
        try:
            chassis = sonic_platform.platform.Platform().get_chassis()
        except Exception as e:
            raise Exception("Failed to load chassis due to {}".format(repr(e)))

        return chassis

    # Check for PDDF mode enabled
    def check_pddf_mode(self):
        if os.path.exists(PDDF_SUPPORT_FILE):
            return True
        else:
            return False
