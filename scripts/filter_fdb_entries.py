#!/usr/bin/env python

import json
import sys
import os
import argparse
import syslog
import traceback
import time

from collections import defaultdict

def get_arp_entries_map(filename):
    """
        Generate map for ARP entries

        ARP entry map is using the MAC as a key for the arp entry. The map key is reformated in order
        to match FDB table formatting

        Args:
            filename(str): ARP entry file name

        Returns:
            arp_map(dict) map of ARP entries using MAC as key.
    """
    with open(filename, 'r') as fp:
        arp_entries = json.load(fp)

    arp_map = defaultdict()
    for arp in arp_entries:
        for key, config in arp.items():
            if 'NEIGH_TABLE' in key:
                arp_map[config["neigh"].replace(':', '-')] = ""

    return arp_map

def filter_fdb_entries(fdb_filename, arp_filename, backup_file):
    """
        Filter FDB entries based on MAC presence into ARP entries

        FDB entries that do not have MAC entry in the ARP table are filtered out. New FDB entries
        file will be created if it has fewer entries than original one.

        Args:
            fdb_filename(str): FDB entries file name
            arp_filename(str): ARP entry file name
            backup_file(bool): Create backup copy of FDB file before creating new one

        Returns:
            None
    """
    arp_map = get_arp_entries_map(arp_filename)

    with open(fdb_filename, 'r') as fp:
        fdb_entries = json.load(fp)

    def filter_fdb_entry(fdb_entry):
        for key, _ in fdb_entry.items():
            if 'FDB_TABLE' in key:
                return key.split(':')[-1] in arp_map

        # malformed entry, default to False so it will be deleted
        return False

    new_fdb_entries = list(filter(filter_fdb_entry, fdb_entries))

    if len(new_fdb_entries) < len(fdb_entries):
        if backup_file:
            os.rename(fdb_filename, fdb_filename + '-' + time.strftime("%Y%m%d-%H%M%S"))

        with open(fdb_filename, 'w') as fp:
            json.dump(new_fdb_entries, fp, indent=2, separators=(',', ': '))

def file_exists_or_raise(filename):
    """
        Check if file exists on the file system

        Args:
            filename(str): File name

        Returns:
            None

        Raises:
            Exception file does not exist
    """
    if not os.path.exists(filename):
        raise Exception("file '{0}' does not exist".format(filename))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--fdb', type=str, default='/tmp/fdb.json', help='fdb file name')
    parser.add_argument('-a', '--arp', type=str, default='/tmp/arp.json', help='arp file name')
    parser.add_argument('-b', '--backup_file', type=bool, default=True, help='Back up old fdb entries file')
    args = parser.parse_args()

    fdb_filename = args.fdb
    arp_filename = args.arp
    backup_file = args.backup_file

    try:
        file_exists_or_raise(fdb_filename)
        file_exists_or_raise(arp_filename)
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Got an exception %s: Traceback: %s" % (str(e), traceback.format_exc()))
    else:
        filter_fdb_entries(fdb_filename, arp_filename, backup_file)

    return 0

if __name__ == '__main__':
    res = 0
    try:
        syslog.openlog('filter_fdb_entries')
        res = main()
    except KeyboardInterrupt:
        syslog.syslog(syslog.LOG_NOTICE, "SIGINT received. Quitting")
        res = 1
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Got an exception %s: Traceback: %s" % (str(e), traceback.format_exc()))
        res = 2
    finally:
        syslog.closelog()
    try:
        sys.exit(res)
    except SystemExit:
        os._exit(res)
