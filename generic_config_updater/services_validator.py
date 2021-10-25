import os
from .gu_common import genericUpdaterLogging

logger = genericUpdaterLogging.get_logger(title="Service Validator")

def _service_restart(svc_name):
    os.system(f"systemctl restart {svc_name}")
    logger.log_notice(f"Restarted {svc_name}")


def ryslog_validator(old_config, upd_config, keys):
    _service_restart("rsyslog-config")


def dhcp_validator(old_config, upd_config, keys):
    _service_restart("dhcp_relay")

