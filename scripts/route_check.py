#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
What it is:
    The routes flow from APPL-DB to ASIC-DB, via orchagent.
    This tool's job is to verify that all routes added to APPL-DB do
    get into ASIC-DB.


How:
    NOTE: The flow from APPL-DB to ASIC-DB takes non zero milliseconds.
    1) Initiate subscribe for ASIC-DB updates.
    2) Read APPL-DB & ASIC-DB 
    3) Get the diff.
    4) If any diff, 
        4.1) Collect subscribe messages for a second
        4.2) check diff against the subscribe messages 
    5) Rule out local interfaces & default routes
    6) If still outstanding diffs, report failure.

To verify:
    Run this tool in SONiC switch and watch the result. In case of failure
    checkout the result to validate the failure.
    To simulate failure:
        Stop Orchagent.
        Run this tool, and likely you would see some failures.
        You could potentially remove / add routes in APPL / ASIC DBs with orchagent
        down to ensure failure.
        Analyze the reported failures to match expected.
    You may use the exit code to verify the result as success or not.
    


"""

import argparse
from enum import Enum
import ipaddress
import json
import os
import re
import sys
import syslog
import time
import signal
import traceback

from swsscommon import swsscommon
from utilities_common import chassis

APPL_DB_NAME = 'APPL_DB'
ASIC_DB_NAME = 'ASIC_DB'
ASIC_TABLE_NAME = 'ASIC_STATE'
ASIC_KEY_PREFIX = 'SAI_OBJECT_TYPE_ROUTE_ENTRY:'

SUBSCRIBE_WAIT_SECS = 1

# Max of 2 minutes
TIMEOUT_SECONDS = 120

UNIT_TESTING = 0

os.environ['PYTHONUNBUFFERED']='True'

PREFIX_SEPARATOR = '/'
IPV6_SEPARATOR = ':'

MIN_SCAN_INTERVAL = 10      # Every 10 seconds
MAX_SCAN_INTERVAL = 3600    # An hour

PRINT_MSG_LEN_MAX = 1000

class Level(Enum):
    ERR = 'ERR'
    INFO = 'INFO'
    DEBUG = 'DEBUG'

    def __str__(self):
        return self.value


report_level = syslog.LOG_WARNING
write_to_syslog = False

def handler(signum, frame):
    print_message(syslog.LOG_ERR,
            "Aborting routeCheck.py upon timeout signal after {} seconds".
            format(TIMEOUT_SECONDS))
    print_message(syslog.LOG_ERR, str(traceback.extract_stack()))
    raise Exception("timeout occurred")


def set_level(lvl, log_to_syslog):
    """
    Sets the log level
    :param lvl: Log level as ERR/INFO/DEBUG; default: syslog.LOG_ERR
    :param log_to_syslog; True - write into syslog. False: skip
    :return None
    """
    global report_level
    global write_to_syslog

    write_to_syslog = log_to_syslog
    if (lvl == Level.INFO):
        report_level = syslog.LOG_INFO

    if (lvl == Level.DEBUG):
        report_level = syslog.LOG_DEBUG


def print_message(lvl, *args):
    """
    print and log the message for given level.
    :param lvl: Log level for this message as ERR/INFO/DEBUG
    :param args: message as list of strings or convertible to string
    :return None
    """
    msg = ""
    if (lvl <= report_level):
        for arg in args:
            rem_len = PRINT_MSG_LEN_MAX - len(msg)
            if rem_len <= 0:
                break
            msg += str(arg)[0:rem_len]

        print(msg)
        if write_to_syslog:
            syslog.syslog(lvl, msg)

    return msg


def add_prefix(ip):
    """
    helper add static prefix based on IP type
    :param ip: IP to add prefix as string.
    :return ip + "/32 or /128"
    """
    if ip.find(IPV6_SEPARATOR) == -1:
        ip = ip + PREFIX_SEPARATOR + "32"
    else:
        ip = ip + PREFIX_SEPARATOR + "128"
    return ip


def add_prefix_ifnot(ip):
    """
    helper add static prefix if absent
    :param ip: IP to add prefix as string.
    :return ip with prefix
    """
    return ip if ip.find(PREFIX_SEPARATOR) != -1 else add_prefix(ip)


def is_local(ip):
    """
    helper to check if this IP qualify as link local
    :param ip: IP to check as string
    :return True if link local, else False
    """
    t = ipaddress.ip_address(ip.split("/")[0])
    return t.is_link_local


def is_default_route(ip):
    """
    helper to check if this IP is default route
    :param ip: IP to check as string
    :return True if default, else False
    """
    t = ipaddress.ip_address(ip.split("/")[0])
    return t.is_unspecified and ip.split("/")[1] == "0"


def cmps(s1, s2):
    """
    helper to compare two strings
    :param s1: left string
    :param s2: right string
    :return comparison result as -1/0/1
    """
    if (s1 == s2):
        return 0
    if (s1 < s2):
        return -1
    return 1


def diff_sorted_lists(t1, t2):
    """
    helper to compare two sorted lists.
    :param t1: list 1
    :param t2: list 2
    :return (<t1 entries that are not in t2>, <t2 entries that are not in t1>)
    """
    t1_x = t2_x = 0
    t1_miss = []
    t2_miss = []
    t1_len = len(t1);
    t2_len = len(t2);
    while t1_x < t1_len and t2_x < t2_len:
        d = cmps(t1[t1_x], t2[t2_x])
        if (d == 0):
            t1_x += 1
            t2_x += 1
        elif (d < 0):
            t1_miss.append(t1[t1_x])
            t1_x += 1
        else:
            t2_miss.append(t2[t2_x])
            t2_x += 1

    while t1_x < t1_len:
        t1_miss.append(t1[t1_x])
        t1_x += 1

    while t2_x < t2_len:
        t2_miss.append(t2[t2_x])
        t2_x += 1
    return t1_miss, t2_miss


def checkout_rt_entry(k):
    """
    helper to filter out correct keys and strip out IP alone.
    :param ip: key to check as string
    :return (True, ip) or (False, None)
    """
    if k.startswith(ASIC_KEY_PREFIX):
        e = k.lower().split("\"", -1)[3]
        if not is_local(e):
            return True, e
    return False, None


def get_subscribe_updates(selector, subs):
    """
    helper to collect subscribe messages for a period
    :param selector: Selector object to wait
    :param subs: Subscription object to pop messages
    :return (add, del) messages as sorted
    """
    adds = []
    deletes = []
    t_end = time.time() + SUBSCRIBE_WAIT_SECS
    t_wait = SUBSCRIBE_WAIT_SECS

    while t_wait > 0:
        selector.select(t_wait)
        t_wait = int(t_end - time.time())
        while True:
            key, op, val = subs.pop()
            if not key:
                break
            res, e = checkout_rt_entry(key)
            if res:
                if op == "SET":
                    adds.append(e)
                elif op == "DEL":
                    deletes.append(e)

    print_message(syslog.LOG_DEBUG, "adds={}".format(adds))
    print_message(syslog.LOG_DEBUG, "dels={}".format(deletes))
    return (sorted(adds), sorted(deletes))


def is_vrf(k):
    return k.startswith("Vrf")


def get_routes():
    """
    helper to read route table from APPL-DB.
    :return list of sorted routes with prefix ensured
    """
    db = swsscommon.DBConnector(APPL_DB_NAME, 0)
    print_message(syslog.LOG_DEBUG, "APPL DB connected for routes")
    tbl = swsscommon.Table(db, 'ROUTE_TABLE')
    keys = tbl.getKeys()

    valid_rt = []
    for k in keys:
        if not is_vrf(k) and not is_local(k):
            valid_rt.append(add_prefix_ifnot(k.lower()))

    print_message(syslog.LOG_DEBUG, json.dumps({"ROUTE_TABLE": sorted(valid_rt)}, indent=4))
    return sorted(valid_rt)


def get_route_entries():
    """
    helper to read present route entries from ASIC-DB and 
    as well initiate selector for ASIC-DB:ASIC-state updates.
    :return (selector,  subscriber, <list of sorted routes>)
    """
    db = swsscommon.DBConnector(ASIC_DB_NAME, 0)
    subs = swsscommon.SubscriberStateTable(db, ASIC_TABLE_NAME)
    print_message(syslog.LOG_DEBUG, "ASIC DB connected")

    rt = []
    while True:
        k, _, _ = subs.pop()
        if not k:
            break
        res, e = checkout_rt_entry(k)
        if res:
            rt.append(e)
                                
    print_message(syslog.LOG_DEBUG, json.dumps({"ASIC_ROUTE_ENTRY": sorted(rt)}, indent=4))

    selector = swsscommon.Select()
    selector.addSelectable(subs)
    return (selector, subs, sorted(rt))


def get_interfaces():
    """
    helper to read interface table from APPL-DB.
    :return sorted list of IP addresses with added prefix
    """
    db = swsscommon.DBConnector(APPL_DB_NAME, 0)
    print_message(syslog.LOG_DEBUG, "APPL DB connected for interfaces")
    tbl = swsscommon.Table(db, 'INTF_TABLE')
    keys = tbl.getKeys()

    intf = []
    for k in keys:
        lst = re.split(':', k.lower(), maxsplit=1)
        if len(lst) == 1:
            # No IP address in key; ignore
            continue

        ip = add_prefix(lst[1].split("/", -1)[0])
        if not is_local(ip):
            intf.append(ip)

    print_message(syslog.LOG_DEBUG, json.dumps({"APPL_DB_INTF": sorted(intf)}, indent=4))
    return sorted(intf)


def filter_out_local_interfaces(keys):
    """
    helper to filter out local interfaces
    :param keys: APPL-DB:ROUTE_TABLE Routes to check.
    :return keys filtered out of local
    """
    rt = []
    local_if_lst = {'eth0', 'docker0'}
    local_if_lo = [r'tun0', r'lo', r'Loopback\d+']

    chassis_local_intfs = chassis.get_chassis_local_interfaces()
    local_if_lst.update(set(chassis_local_intfs))
    
    db = swsscommon.DBConnector(APPL_DB_NAME, 0)
    tbl = swsscommon.Table(db, 'ROUTE_TABLE')

    for k in keys:
        e = dict(tbl.get(k)[1])

        ifname = e.get('ifname', '')
        if ifname in local_if_lst:
            continue

        if any([re.match(x, ifname) for x in local_if_lo]):
            nh = e.get('nexthop')
            if not nh or ipaddress.ip_address(nh).is_unspecified:
                continue

        rt.append(k)

    return rt


def filter_out_voq_neigh_routes(keys):
    """
    helper to filter out voq neigh routes. These are the
    routes statically added for the voq neighbors. We skip
    writing route entries in asic db for these. We filter
    out reporting error on all the host routes written on
    inband interface prefixed with "Ethernte-IB"
    :param keys: APPL-DB:ROUTE_TABLE Routes to check.
    :return keys filtered out for voq neigh routes
    """
    rt = []
    local_if_re = [r'Ethernet-IB\d+']

    db = swsscommon.DBConnector(APPL_DB_NAME, 0)
    tbl = swsscommon.Table(db, 'ROUTE_TABLE')

    for k in keys:
        prefix = k.split("/")
        e = dict(tbl.get(k)[1])
        if not e:
            # Prefix might have been added. So try w/o it.
            e = dict(tbl.get(prefix[0])[1])
        if not e or all([not (re.match(x, e['ifname']) and
            ((prefix[1] == "32" and e['nexthop'] == "0.0.0.0") or
                (prefix[1] == "128" and e['nexthop'] == "::"))) for x in local_if_re]):
            rt.append(k)

    return rt


def filter_out_default_routes(lst):
    """
    helper to filter out default routes
    :param lst: list to filter
    :return filtered list.
    """
    upd = []

    for rt in lst:
        if not is_default_route(rt):
            upd.append(rt)

    return upd


def filter_out_vnet_routes(routes):
    """
    Helper to filter out VNET routes
    :param routes: list of routes to filter
    :return filtered list of routes.
    """
    db = swsscommon.DBConnector('APPL_DB', 0)

    vnet_route_table = swsscommon.Table(db, 'VNET_ROUTE_TABLE')
    vnet_route_tunnel_table = swsscommon.Table(db, 'VNET_ROUTE_TUNNEL_TABLE')

    vnet_routes_db_keys = vnet_route_table.getKeys() + vnet_route_tunnel_table.getKeys()

    vnet_routes = []

    for vnet_route_db_key in vnet_routes_db_keys:
        vnet_route_attrs = vnet_route_db_key.split(':')
        vnet_name = vnet_route_attrs[0]
        vnet_route = vnet_route_attrs[1]
        vnet_routes.append(vnet_route)

    updated_routes = []

    for route in routes:
        if not (route in vnet_routes):
            updated_routes.append(route)

    return updated_routes


def is_dualtor(config_db):
    device_metadata = config_db.get_table('DEVICE_METADATA')
    subtype = device_metadata['localhost'].get('subtype', '')
    return subtype.lower() == 'dualtor'


def filter_out_standalone_tunnel_routes(routes):
    config_db = swsscommon.ConfigDBConnector()
    config_db.connect()

    if not is_dualtor(config_db):
        return routes

    app_db = swsscommon.DBConnector('APPL_DB', 0)
    neigh_table = swsscommon.Table(app_db, 'NEIGH_TABLE')
    neigh_keys = neigh_table.getKeys()
    standalone_tunnel_route_ips = []
    updated_routes = []

    for neigh in neigh_keys:
        _, mac = neigh_table.hget(neigh, 'neigh')
        if mac == '00:00:00:00:00:00':
            # remove preceding 'VlanXXXX' to get just the neighbor IP
            neigh_ip = ':'.join(neigh.split(':')[1:])
            standalone_tunnel_route_ips.append(neigh_ip)

    if not standalone_tunnel_route_ips:
        return routes

    for route in routes:
        ip, subnet = route.split('/')
        ip_version = ipaddress.ip_address(ip).version

        # we want to keep the route if it is not a standalone tunnel route.
        # if the route subnet contains more than one address, it is not a
        # standalone tunnel route
        if (ip not in standalone_tunnel_route_ips) or \
           ((ip_version == 6 and subnet != '128') or (ip_version == 4 and subnet != '32')):
            updated_routes.append(route)

    return updated_routes


def get_soc_ips(config_db):
    mux_table = config_db.get_table('MUX_CABLE')
    soc_ips = []
    for _, mux_entry in mux_table.items():
        if mux_entry.get("cable_type", "") == "active-active" and "soc_ipv4" in mux_entry:
            soc_ips.append(mux_entry["soc_ipv4"])

    return soc_ips


def filter_out_soc_ip_routes(routes):
    """
    Ignore ASIC only routes for SOC IPs

    For active-active cables, we want the tunnel route for SOC IPs
    to only be programmed to the ASIC and not to the kernel. This is to allow
    gRPC connections coming from ycabled to always use the direct link (since this
    will use the kernel routing table), but still provide connectivity to any external
    traffic in case of a link issue (since this traffic will be forwarded by the ASIC).
    """
    config_db = swsscommon.ConfigDBConnector()
    config_db.connect()

    if not is_dualtor(config_db):
        return routes

    soc_ips = get_soc_ips(config_db)

    if not soc_ips:
        return routes
    
    updated_routes = []
    for route in routes:
        if route not in soc_ips:
            updated_routes.append(route)

    return updated_routes


def check_routes():
    """
    The heart of this script which runs the checks.
    Read APPL-DB & ASIC-DB, the relevant tables for route checking.
    Checkout routes in ASIC-DB to match APPL-DB, discounting local & 
    default routes. In case of missed / unexpected entries in ASIC,
    it might be due to update latency between APPL & ASIC DBs. So collect
    ASIC-DB subscribe updates for a second, and checkout if you see SET
    command for missing ones & DEL command for unexpectes ones in ASIC.

    If there are still some unjustifiable diffs, between APPL & ASIC DB,
    related to routes report failure, else all good.

    :return (0, None) on sucess, else (-1, results) where results holds
    the unjustifiable entries.
    """
    intf_appl_miss = []
    rt_appl_miss = []
    rt_asic_miss = []

    results = {}
    adds = []
    deletes = []

    selector, subs, rt_asic = get_route_entries()

    rt_appl = get_routes()
    intf_appl = get_interfaces()

    # Diff APPL-DB routes & ASIC-DB routes
    rt_appl_miss, rt_asic_miss = diff_sorted_lists(rt_appl, rt_asic)

    # Check missed ASIC routes against APPL-DB INTF_TABLE
    _, rt_asic_miss = diff_sorted_lists(intf_appl, rt_asic_miss)
    rt_asic_miss = filter_out_default_routes(rt_asic_miss)
    rt_asic_miss = filter_out_vnet_routes(rt_asic_miss)
    rt_asic_miss = filter_out_standalone_tunnel_routes(rt_asic_miss)
    rt_asic_miss = filter_out_soc_ip_routes(rt_asic_miss)

    # Check APPL-DB INTF_TABLE with ASIC table route entries
    intf_appl_miss, _ = diff_sorted_lists(intf_appl, rt_asic)

    if rt_appl_miss:
        rt_appl_miss = filter_out_local_interfaces(rt_appl_miss)

    if rt_appl_miss:
        rt_appl_miss = filter_out_voq_neigh_routes(rt_appl_miss)

    if rt_appl_miss or rt_asic_miss:
        # Look for subscribe updates for a second
        adds, deletes = get_subscribe_updates(selector, subs)

        # Drop all those for which SET received
        rt_appl_miss, _ = diff_sorted_lists(rt_appl_miss, adds)

        # Drop all those for which DEL received
        rt_asic_miss, _ = diff_sorted_lists(rt_asic_miss, deletes)

    if rt_appl_miss:
        results["missed_ROUTE_TABLE_routes"] = rt_appl_miss

    if intf_appl_miss:
        results["missed_INTF_TABLE_entries"] = intf_appl_miss

    if rt_asic_miss:
        results["Unaccounted_ROUTE_ENTRY_TABLE_entries"] = rt_asic_miss

    if results:
        print_message(syslog.LOG_WARNING, "Failure results: {",  json.dumps(results, indent=4), "}")
        print_message(syslog.LOG_WARNING, "Failed. Look at reported mismatches above")
        print_message(syslog.LOG_WARNING, "add: ", json.dumps(adds, indent=4))
        print_message(syslog.LOG_WARNING, "del: ", json.dumps(deletes, indent=4))
        return -1, results
    else:
        print_message(syslog.LOG_INFO, "All good!")
        return 0, None


def main():
    """
    main entry point, which mainly parses the args and call check_routes
    In case of single run, it returns on one call or stays in forever loop
    with given interval in-between calls to check_route
    :return Same return value as returned by check_route.
    """
    interval = 0
    parser=argparse.ArgumentParser(description="Verify routes between APPL-DB & ASIC-DB are in sync")
    parser.add_argument('-m', "--mode", type=Level, choices=list(Level), default='ERR')
    parser.add_argument("-i", "--interval", type=int, default=0, help="Scan interval in seconds")
    parser.add_argument("-s", "--log_to_syslog", action="store_true", default=True, help="Write message to syslog")
    args = parser.parse_args()

    set_level(args.mode, args.log_to_syslog)

    if args.interval:
        if (args.interval < MIN_SCAN_INTERVAL):
            interval = MIN_SCAN_INTERVAL
        elif (args.interval > MAX_SCAN_INTERVAL):
            interval = MAX_SCAN_INTERVAL
        else:
            interval = args.interval
        if UNIT_TESTING:
            interval = 1

    signal.signal(signal.SIGALRM, handler)

    while True:
        signal.alarm(TIMEOUT_SECONDS)
        ret, res= check_routes()
        signal.alarm(0)

        if interval:
            time.sleep(interval)
            if UNIT_TESTING:
                return ret, res
        else:
            return ret, res
            


if __name__ == "__main__":
    sys.exit(main()[0])
