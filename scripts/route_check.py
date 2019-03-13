#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import getopt
import ipaddress
import json
from swsssdk import ConfigDBConnector

os.environ['PYTHONUNBUFFERED']='True'

PREFIX_SEPARATOR = '/'
IPV6_SEPARATOR = ':'

# Modes of operation from quiet to noisy
MODE_QUIET = 0
MODE_ERR = 1
MODE_INFO = 2
MODE_DEBUG = 3

mode = MODE_ERR

def set_mode(m):
    global mode
    if (m == 'QUIET'):
        mode = MODE_QUIET
    elif (m == 'ERR'):
        mode = MODE_ERR
    elif (m == 'INFO'):
        mode = MODE_INFO
    elif (m == 'DEBUG'):
        mode = MODE_DEBUG
    return mode

def print_message(lvl, *args):
    if (lvl <= mode):
        for arg in args:
            print arg

def add_prefix(ip):
    if ip.find(IPV6_SEPARATOR) == -1:
        ip = ip + PREFIX_SEPARATOR + "32"
    else:
        ip = ip + PREFIX_SEPARATOR + "128"
    return ip

def add_prefix_ifnot(ip):
    return ip if ip.find(PREFIX_SEPARATOR) != -1 else add_prefix(ip)

def ip_subnet(ip):
    if ip.find(":") == -1:
        net = ipaddress.IPv4Network(ip, False)
    else:
        net = ipaddress.IPv6Network(ip, False)
    return net.with_prefixlen

def cmps(s1, s2):
    if (s1 == s2):
        return 0
    if (s1 < s2):
        return -1
    return 1

def do_diff(t1, t2):
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


def get_routes():
    db = ConfigDBConnector()
    db.db_connect('APPL_DB')
    print_message(MODE_DEBUG, "APPL DB connected for routes")
    keys = db.get_keys('ROUTE_TABLE')
    print_message(MODE_DEBUG, json.dumps({"ROUTE_TABLE": keys}, indent=4))

    valid_rt = []
    skip_rt = []
    for k in keys:
        if db.get_entry('ROUTE_TABLE', k)['nexthop'] != '':
            valid_rt.append(add_prefix_ifnot(k))
        else:
            skip_rt.append(k)

    print_message(MODE_INFO, json.dumps({"skipped_routes" : skip_rt}, indent=4))
    return sorted(valid_rt)

def get_route_entries():
    db = ConfigDBConnector()
    db.db_connect('ASIC_DB')
    print_message(MODE_DEBUG, "ASIC DB connected")
    keys = db.get_keys('ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY', False)
    print_message(MODE_DEBUG, json.dumps({"ASIC_ROUTE_ENTRY": keys}, indent=4))

    rt = []
    for k in keys:
        rt.append(k.split("\"", -1)[3])
    return sorted(rt)


def get_interfaces():
    db = ConfigDBConnector()
    db.db_connect('APPL_DB')
    print_message(MODE_DEBUG, "APPL DB connected for interfaces")

    intf = []
    keys = db.get_keys('INTF_TABLE')
    print_message(MODE_DEBUG, json.dumps({"APPL_DB_INTF": keys}, indent=4))

    for k in keys:
        subk = k.split(':', -1)
        alias = subk[0]
        ip_prefix = ":".join(subk[1:])
        ip = add_prefix(ip_prefix.split("/", -1)[0])
        if (subk[0] == "eth0") or (subk[0] == "docker0"):
            continue
        if (subk[0] != "lo"):
            intf.append(ip_subnet(ip_prefix))
        intf.append(ip)
    return sorted(intf)

def check_routes():
    intf_miss = []
    rt_miss = []
    re_miss = []

    results = {}
    err_present = False

    rt_miss, re_miss = do_diff(get_routes(), get_route_entries())
    intf_miss, re_miss = do_diff(get_interfaces(), re_miss)

    if (len(rt_miss) != 0):
        results["missed_ROUTE_TABLE_routes"] = rt_miss
        err_present = True

    if (len(intf_miss) != 0):
        results["missed_INTF_TABLE_entries"] = intf_miss
        err_present = True

    if (len(re_miss) != 0):
        results["Unaccounted_ROUTE_ENTRY_TABLE_entries"] = re_miss
        err_present = True

    if err_present:
        print_message(MODE_ERR, "results: {",  json.dumps(results, indent=4), "}")
        print_message(MODE_ERR, "Failed. Look at reported mismatches above")
        return -1
    else:
        print_message(MODE_ERR, "All good!")
        return 0

def usage():
    print sys.argv[0], "[-m <QUIET|ERR|INFO|DEBUG>]"
    print sys.argv[0], "[--mode=<QUIET|ERR|INFO|DEBUG>]"
    sys.exit(-1)

def main(argv):
    try:
        opts, argv = getopt.getopt(argv, "m:", ["mode="])
    except getopt.GetoptError:
        usage()

    for opt, arg in opts:
        if opt in ("-m", "--mode"):
            set_mode(arg)

    ret = check_routes()
    sys.exit(ret)


if __name__ == "__main__":
    main(sys.argv[1:])
