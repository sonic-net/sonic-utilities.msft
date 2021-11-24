import os
from .gu_common import genericUpdaterLogging

logger = genericUpdaterLogging.get_logger(title="Service Validator")

print_to_console = False

def set_verbose(verbose=False):
    global print_to_console, logger

    print_to_console = verbose
    if verbose:
        logger.set_min_log_priority_debug()
    else:
        logger.set_min_log_priority_notice()


def _service_restart(svc_name):
    rc = os.system(f"systemctl restart {svc_name}")
    logger.log(logger.LOG_PRIORITY_NOTICE,
            f"Restarted {svc_name}", print_to_console)
    return rc == 0


def rsyslog_validator(old_config, upd_config, keys):
    return _service_restart("rsyslog-config")


def dhcp_validator(old_config, upd_config, keys):
    return _service_restart("dhcp_relay")


def vlan_validator(old_config, upd_config, keys):
    old_vlan = old_config.get("VLAN", {})
    upd_vlan = upd_config.get("VLAN", {})

    for key in set(old_vlan.keys()).union(set(upd_vlan.keys())):
        if (old_vlan.get(key, {}).get("dhcp_servers", []) != 
                upd_vlan.get(key, {}).get("dhcp_servers", [])):
            return _service_restart("dhcp_relay")
    # No update to DHCP servers.
    return True

