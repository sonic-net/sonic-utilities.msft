#!/usr/bin/env python
#
# log.py
#
# Logging library for command-line interface for interacting with platform components within SONiC
#

try:
    import syslog
    import click
except ImportError as e:
    raise ImportError("Required module not found: {}".format(str(e)))

# ========================= Constants ==========================================

SYSLOG_IDENTIFIER = "fwutil"

# ========================= Helper classes =====================================

class SyslogLogger(object):
    """
    SyslogLogger
    """
    def __init__(self, identifier):
        self.__syslog = syslog

        self.__syslog.openlog(
            ident=identifier,
            logoption=self.__syslog.LOG_NDELAY,
            facility=self.__syslog.LOG_USER
        )

    def __del__(self):
        self.__syslog.closelog()

    def log_error(self, msg):
        self.__syslog.syslog(self.__syslog.LOG_ERR, msg)

    def log_warning(self, msg):
        self.__syslog.syslog(self.__syslog.LOG_WARNING, msg)

    def log_notice(self, msg):
        self.__syslog.syslog(self.__syslog.LOG_NOTICE, msg)

    def log_info(self, msg):
        self.__syslog.syslog(self.__syslog.LOG_INFO, msg)

    def log_debug(self, msg):
        self.__syslog.syslog(self.__syslog.LOG_DEBUG, msg)


logger = SyslogLogger(SYSLOG_IDENTIFIER)


class LogHelper(object):
    """
    LogHelper
    """
    FW_ACTION_DOWNLOAD = "download"
    FW_ACTION_INSTALL = "install"
    FW_ACTION_UPDATE = "update"

    STATUS_SUCCESS = "success"
    STATUS_FAILURE = "failure"

    def __log_fw_action_start(self, action, component, firmware):
        caption = "Firmware {} started".format(action)
        template = "{}: component={}, firmware={}"

        logger.log_info(
            template.format(
                caption,
                component,
                firmware
            )
        )

    def __log_fw_action_end(self, action, component, firmware, status, exception=None):
        caption = "Firmware {} ended".format(action)

        status_template = "{}: component={}, firmware={}, status={}"
        exception_template = "{}: component={}, firmware={}, status={}, exception={}"

        if status:
            logger.log_info(
                status_template.format(
                    caption,
                    component,
                    firmware,
                    self.STATUS_SUCCESS
                )
            )
        else:
            if exception is None:
                logger.log_error(
                    status_template.format(
                        caption,
                        component,
                        firmware,
                        self.STATUS_FAILURE
                    )
                )
            else:
                logger.log_error(
                    exception_template.format(
                        caption,
                        component,
                        firmware,
                        self.STATUS_FAILURE,
                        str(exception)
                    )
                )

    def log_fw_download_start(self, component, firmware):
        self.__log_fw_action_start(self.FW_ACTION_DOWNLOAD, component, firmware)

    def log_fw_download_end(self, component, firmware, status, exception=None):
        self.__log_fw_action_end(self.FW_ACTION_DOWNLOAD, component, firmware, status, exception)

    def log_fw_install_start(self, component, firmware):
        self.__log_fw_action_start(self.FW_ACTION_INSTALL, component, firmware)

    def log_fw_install_end(self, component, firmware, status, exception=None):
        self.__log_fw_action_end(self.FW_ACTION_INSTALL, component, firmware, status, exception)

    def log_fw_update_start(self, component, firmware):
        self.__log_fw_action_start(self.FW_ACTION_UPDATE, component, firmware)

    def log_fw_update_end(self, component, firmware, status, exception=None):
        self.__log_fw_action_end(self.FW_ACTION_UPDATE, component, firmware, status, exception)

    def print_error(self, msg):
        click.echo("Error: {}.".format(msg))

    def print_warning(self, msg):
        click.echo("Warning: {}.".format(msg))

    def print_info(self, msg):
        click.echo("Info: {}.".format(msg))
