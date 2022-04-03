"""
coredump_gen_handler script.
    This script is invoked by the coredump-compress script
    for auto techsupport invocation and cleanup core dumps.
    For more info, refer to the Event Driven TechSupport & CoreDump Mgmt HLD
"""
import os
import time
import argparse
import syslog
import re
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.auto_techsupport_helper import *

# Explicity Pass this to the subprocess invoking techsupport
ENV_VAR = os.environ
PATH_PREV = ENV_VAR["PATH"] if "PATH" in ENV_VAR else ""
ENV_VAR["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + PATH_PREV


def handle_coredump_cleanup(dump_name, db):
    _, num_bytes = get_stats(os.path.join(CORE_DUMP_DIR, CORE_DUMP_PTRN))

    if db.get(CFG_DB, AUTO_TS, CFG_STATE) != "enabled":
        msg = "coredump_cleanup is disabled. No cleanup is performed. current size occupied : {}"
        syslog.syslog(syslog.LOG_NOTICE, msg.format(pretty_size(num_bytes)))
        return

    core_usage = db.get(CFG_DB, AUTO_TS, CFG_CORE_USAGE)
    try:
        core_usage = float(core_usage)
    except ValueError:
        core_usage = 0.0

    if not core_usage:
        msg = "core-usage argument is not set. No cleanup is performed, current size occupied: {}"
        syslog.syslog(syslog.LOG_NOTICE, msg.format(pretty_size(num_bytes)))
        return

    cleanup_process(core_usage, CORE_DUMP_PTRN, CORE_DUMP_DIR)


class CriticalProcCoreDumpHandle():
    """
    Class to handle coredump creation event for critical processes
    """

    def __init__(self, core_name, container_name, db):
        self.core_name = core_name
        self.container = container_name
        self.db = db
        self.proc_mp = {}
        self.core_ts_map = {}

    def handle_core_dump_creation_event(self):
        if self.db.get(CFG_DB, AUTO_TS, CFG_STATE) != "enabled":
            syslog.syslog(syslog.LOG_NOTICE, "auto_invoke_ts is disabled. No cleanup is performed: core {}".format(self.core_name))
            return

        # Config made for the defaul instance applies to all the masic instances
        self.container = trim_masic_suffix(self.container)

        FEATURE_KEY = FEATURE.format(self.container)
        if self.db.get(CFG_DB, FEATURE_KEY, CFG_STATE) != "enabled":
            msg = "auto-techsupport feature for {} is not enabled. Techsupport Invocation is skipped. core: {}"
            syslog.syslog(syslog.LOG_NOTICE, msg.format(self.container, self.core_name))
            return

        global_cooloff = self.db.get(CFG_DB, AUTO_TS, COOLOFF)  
        container_cooloff = self.db.get(CFG_DB, FEATURE_KEY, COOLOFF)

        try:
            global_cooloff = float(global_cooloff)
        except ValueError:
            global_cooloff = 0.0

        try:
            container_cooloff = float(container_cooloff)
        except ValueError:
            container_cooloff = 0.0

        cooloff_passed = self.verify_rate_limit_intervals(global_cooloff, container_cooloff)
        if cooloff_passed:
            since_cfg = self.get_since_arg()
            new_file = self.invoke_ts_cmd(since_cfg)
            if new_file:
                self.write_to_state_db(int(time.time()), new_file)

    def write_to_state_db(self, timestamp, ts_dump):
        name = strip_ts_ext(ts_dump)
        key = TS_MAP + "|" + name
        self.db.set(STATE_DB, key, CORE_DUMP, self.core_name)
        self.db.set(STATE_DB, key, TIMESTAMP, str(timestamp))
        self.db.set(STATE_DB, key, CONTAINER, self.container)

    def get_since_arg(self):
        since_cfg = self.db.get(CFG_DB, AUTO_TS, CFG_SINCE)
        if not since_cfg:
            return SINCE_DEFAULT
        rc, _, stderr = subprocess_exec(["date", "--date={}".format(since_cfg)], env=ENV_VAR)
        if rc == 0:
            return since_cfg
        return SINCE_DEFAULT

    def parse_ts_dump_name(self, ts_stdout):
        """ Figure out the ts_dump name from the techsupport stdout """
        matches = re.findall(TS_PTRN, ts_stdout)
        if matches:
            return matches[-1]
        syslog.syslog(syslog.LOG_ERR, "stdout of the 'show techsupport' cmd doesn't have the dump name")
        return ""

    def invoke_ts_cmd(self, since_cfg, num_retry=0):
        cmd_opts = ["show", "techsupport", "--silent", "--since", since_cfg]
        cmd  = " ".join(cmd_opts)
        rc, stdout, stderr = subprocess_exec(cmd_opts, env=ENV_VAR)
        new_dump = ""
        if rc == EXT_LOCKFAIL:
            syslog.syslog(syslog.LOG_NOTICE, "Another instance of techsupport running, aborting this. stderr: {}".format(stderr))
        elif rc == EXT_RETRY:
            if num_retry <= MAX_RETRY_LIMIT:
                return self.invoke_ts_cmd(since_cfg, num_retry+1)
            else:
                syslog.syslog(syslog.LOG_ERR, "MAX_RETRY_LIMIT for show techsupport invocation exceeded, stderr: {}".format(stderr))
        elif rc != EXT_SUCCESS:
            syslog.syslog(syslog.LOG_ERR, "show techsupport failed with exit code {}, stderr: {}".format(rc, stderr))
        else: # EXT_SUCCESS
            new_dump = self.parse_ts_dump_name(stdout) # Parse the dump name
            if not new_dump:
                syslog.syslog(syslog.LOG_ERR, "{} was run, but no techsupport dump is found".format(cmd))
            else:
                syslog.syslog(syslog.LOG_INFO, "{} is successful, {} is created".format(cmd, new_dump))
        return new_dump

    def verify_rate_limit_intervals(self, global_cooloff, container_cooloff):
        """Verify both the global and per-proc rate_limit_intervals have passed"""
        curr_ts_list = get_ts_dumps(True)
        if global_cooloff and curr_ts_list:
            last_ts_dump_creation = os.path.getmtime(curr_ts_list[-1])
            if time.time() - last_ts_dump_creation < global_cooloff:
                msg = "Global rate_limit_interval period has not passed. Techsupport Invocation is skipped. Core: {}"
                syslog.syslog(syslog.LOG_INFO, msg.format(self.core_name))
                return False

        self.parse_ts_map()
        if container_cooloff and self.container in self.core_ts_map:
            last_creation_time = self.core_ts_map[self.container][0][0]
            if time.time() - last_creation_time < container_cooloff:
                msg = "Per Container rate_limit_interval for {} has not passed. Techsupport Invocation is skipped. Core: {}"
                syslog.syslog(syslog.LOG_INFO, msg.format(self.container, self.core_name))
                return False
        return True

    def parse_ts_map(self):
        """Create proc_name, ts_dump & creation_time map"""
        ts_keys = self.db.keys(STATE_DB, TS_MAP+"*")
        if not ts_keys:
            return
        for ts_key in ts_keys:
            data = self.db.get_all(STATE_DB, ts_key)
            if not data:
                continue
            container_name = data.get(CONTAINER, "")
            creation_time = data.get(TIMESTAMP, "")
            try:
                creation_time = int(creation_time)
            except Exception:
                continue  # if the creation time is invalid, skip the entry
            ts_dump = ts_key.split("|")[-1]
            if container_name and container_name not in self.core_ts_map:
                self.core_ts_map[container_name] = []
            self.core_ts_map[container_name].append((int(creation_time), ts_dump))
        for container_name in self.core_ts_map:
            self.core_ts_map[container_name].sort()

def main():
    parser = argparse.ArgumentParser(description='Auto Techsupport Invocation and CoreDump Mgmt Script')
    parser.add_argument('name', type=str, help='Core Dump Name')
    parser.add_argument('container', type=str, help='Container Name')
    args = parser.parse_args()
    syslog.openlog(logoption=syslog.LOG_PID)
    db = SonicV2Connector(use_unix_socket_path=True)
    db.connect(CFG_DB)
    db.connect(STATE_DB)
    file_path = os.path.join(CORE_DUMP_DIR, args.name)
    if not verify_recent_file_creation(file_path):
        syslog.syslog(syslog.LOG_INFO, "Spurious Invocation. {} is not created within last {} sec".format(file_path, TIME_BUF))
        return
    cls = CriticalProcCoreDumpHandle(args.name, args.container, db)
    cls.handle_core_dump_creation_event()
    handle_coredump_cleanup(args.name, db)


if __name__ == "__main__":
    main()
