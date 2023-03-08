from sonic_py_common import device_info
import re

def rdma_config_update_validator():
    version_info = device_info.get_sonic_version_info()
    build_version = version_info.get('build_version')
    asic_type = version_info.get('asic_type')

    if (asic_type != 'mellanox' and asic_type != 'broadcom' and asic_type != 'cisco-8000'):
        return False

    version_substrings = build_version.split('.')
    branch_version = None

    for substring in version_substrings:
        if substring.isdigit() and re.match(r'^\d{8}$', substring):
            branch_version = substring
            break

    if branch_version is None:
        return False

    if asic_type == 'cisco-8000':
        return branch_version >= "20201200"
    else:
        return branch_version >= "20181100"
