from sonic_py_common import device_info
import re

def rdma_config_update_validator():
    version_info = device_info.get_sonic_version_info()
    asic_type = version_info.get('asic_type')

    if (asic_type != 'mellanox' and asic_type != 'broadcom' and asic_type != 'cisco-8000'):
        return False
    return True
