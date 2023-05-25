#!/usr/bin/env python3

from scapy.config import conf
conf.ipv6_enabled = False
from scapy.all import sendp, sniff
from swsscommon.swsscommon import ConfigDBConnector
import time, threading, traceback
import syslog

SYSLOG_ID = 'lag_keepalive'


def log_info(msg):
    syslog.openlog(SYSLOG_ID)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()


def log_error(msg):
    syslog.openlog(SYSLOG_ID)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()


def sniff_lacpdu(device_mac, lag_member, lag_member_to_packet):
    sniffed_packet = sniff(iface=lag_member,
        filter="ether proto 0x8809 and ether src {}".format(device_mac),
        count=1, timeout=30)
    lag_member_to_packet[lag_member] = sniffed_packet


def get_lacpdu_per_lag_member():
    appDB = ConfigDBConnector()
    appDB.db_connect('APPL_DB')
    appDB_lag_info = appDB.get_keys('LAG_MEMBER_TABLE')
    configDB = ConfigDBConnector()
    configDB.db_connect('CONFIG_DB')
    device_mac = configDB.get(configDB.CONFIG_DB,  "DEVICE_METADATA|localhost", "mac")
    hwsku = configDB.get(configDB.CONFIG_DB,  "DEVICE_METADATA|localhost", "hwsku")
    active_lag_members = list()
    lag_member_to_packet = dict()
    sniffer_threads = list()
    for lag_entry in appDB_lag_info:
        lag_name = str(lag_entry[0])
        oper_status = appDB.get(appDB.APPL_DB,"LAG_TABLE:{}".format(lag_name), "oper_status")
        if oper_status == "up":
            # only apply the workaround for active lags
            lag_member = str(lag_entry[1])
            active_lag_members.append(lag_member)
            # use threading to capture lacpdus from several lag members simultaneously
            sniffer_thread = threading.Thread(target=sniff_lacpdu,
                args=(device_mac, lag_member, lag_member_to_packet))
            sniffer_thread.start()
            sniffer_threads.append(sniffer_thread)

    # sniff for lacpdu should finish in <= 30s. sniff timeout is also set to 30s
    for sniffer in sniffer_threads:
        sniffer.join(timeout=30)
    
    return active_lag_members, lag_member_to_packet


def lag_keepalive(lag_member_to_packet):
    while True:
        for lag_member, packet in lag_member_to_packet.items():
            try:
                sendp(packet, iface=lag_member, verbose=False)
            except Exception:
                # log failure and continue to send lacpdu
                traceback_msg = traceback.format_exc()
                log_error("Failed to send LACPDU packet from interface {} with error: {}".format(
                    lag_member, traceback_msg))
                continue
        log_info("sent LACPDU packets via {}".format(lag_member_to_packet.keys()))
        time.sleep(1)


def main():
    while True:
        try:
            active_lag_members, lag_member_to_packet = get_lacpdu_per_lag_member()
            if len(active_lag_members) != len(lag_member_to_packet.keys()):
                log_error("Failed to capture LACPDU packets for some lag members. " +\
                "Active lag members: {}. LACPDUs captured for: {}".format(
                    active_lag_members, lag_member_to_packet.keys()))

            log_info("ready to send LACPDU packets via {}".format(lag_member_to_packet.keys()))
        except Exception:
            traceback_msg = traceback.format_exc()
            log_error("Failed to get LAG members and LACPDUs with error: {}".format(
                traceback_msg))
            # keep attempting until sniffed packets are ready
            continue
        # if no exceptions are thrown, break from loop as LACPDUs are ready to be sent
        break

    if lag_member_to_packet:
        # start an infinite loop to keep sending lacpdus from lag member ports
        lag_keepalive(lag_member_to_packet)

if __name__ == "__main__":
    main()
