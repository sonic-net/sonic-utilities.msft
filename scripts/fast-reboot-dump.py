#!/usr/bin/env python


import swsssdk
import json
from pprint import pprint


def generate_arp_entries(filename, all_available_macs):
    db = swsssdk.SonicV2Connector()
    db.connect(db.APPL_DB, False)   # Make one attempt only

    arp_output = []

    keys = db.keys(db.APPL_DB, 'NEIGH_TABLE:*')
    keys = [] if keys is None else keys
    for key in keys:
        entry = db.get_all(db.APPL_DB, key)
        if entry['neigh'].lower() not in all_available_macs:
            # print me to log
            continue
        obj = {
          key: entry,
          'OP': 'SET'
        }
        arp_output.append(obj)

    db.close(db.APPL_DB)

    with open(filename, 'w') as fp:
        json.dump(arp_output, fp, indent=2, separators=(',', ': '))

    return

def is_mac_unicast(mac):
    first_octet = mac.split(':')[0]

    if int(first_octet, 16) & 0x01 == 0:
        return True
    else:
        return False

def get_vlan_ifaces():
    vlans = []
    with open('/proc/net/dev') as fp:
        raw = fp.read()

    for line in raw.split('\n'):
        if 'Vlan' not in line:
            continue
        vlan_name = line.split(':')[0].strip()
        vlans.append(vlan_name)

    return vlans

def get_bridge_port_id_2_port_id(db):
    bridge_port_id_2_port_id = {}
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:*')
    keys = [] if keys is None else keys
    for key in keys:
        value = db.get_all(db.ASIC_DB, key)
        port_type = value['SAI_BRIDGE_PORT_ATTR_TYPE']
        if port_type != 'SAI_BRIDGE_PORT_TYPE_PORT':
            continue
        port_id = value['SAI_BRIDGE_PORT_ATTR_PORT_ID']
        # ignore admin status
        bridge_id = key.replace('ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:', '')
        bridge_port_id_2_port_id[bridge_id] = port_id

    return bridge_port_id_2_port_id

def get_map_port_id_2_iface_name(db):
    port_id_2_iface = {}
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:*')
    keys = [] if keys is None else keys
    for key in keys:
        value = db.get_all(db.ASIC_DB, key)
        port_id = value['SAI_HOSTIF_ATTR_OBJ_ID']
        iface_name = value['SAI_HOSTIF_ATTR_NAME']
        port_id_2_iface[port_id] = iface_name

    return port_id_2_iface

def get_map_bridge_port_id_2_iface_name(db):
    bridge_port_id_2_port_id = get_bridge_port_id_2_port_id(db)
    port_id_2_iface = get_map_port_id_2_iface_name(db)

    bridge_port_id_2_iface_name = {}

    for bridge_port_id, port_id in bridge_port_id_2_port_id.items():
        if port_id in port_id_2_iface:
            bridge_port_id_2_iface_name[bridge_port_id] = port_id_2_iface[port_id]
        else:
            print "Not found"

    return bridge_port_id_2_iface_name

def get_fdb(db, vlan_id, bridge_id_2_iface):
    fdb_types = {
      'SAI_FDB_ENTRY_TYPE_DYNAMIC': 'dynamic',
      'SAI_FDB_ENTRY_TYPE_STATIC' : 'static'
    }

    available_macs = set()

    entries = []
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{*\"vlan\":\"%d\"}' % vlan_id)
    keys = [] if keys is None else keys
    for key in keys:
        key_obj = json.loads(key.replace('ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:', ''))
        vlan = str(key_obj['vlan'])
        mac = str(key_obj['mac'])
        if not is_mac_unicast(mac):
            continue
        available_macs.add(mac.lower())
        mac = mac.replace(':', '-')
        # FIXME: mac is unicast
        # get attributes
        value = db.get_all(db.ASIC_DB, key)
        type = fdb_types[value['SAI_FDB_ENTRY_ATTR_TYPE']]
        if value['SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID'] not in bridge_id_2_iface:
            continue
        port = bridge_id_2_iface[value['SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID']]

        obj = {
          'FDB_TABLE:Vlan%d:%s' % (vlan_id, mac) : {
            'type': type,
            'port': port,
          },
          'OP': 'SET'
        }

        entries.append(obj)

    return entries, available_macs


def generate_fdb_entries(filename):
    fdb_entries = []

    db = swsssdk.SonicV2Connector()
    db.connect(db.ASIC_DB, False)   # Make one attempt only

    bridge_id_2_iface = get_map_bridge_port_id_2_iface_name(db)

    vlan_ifaces = get_vlan_ifaces()

    all_available_macs = set()
    for vlan in vlan_ifaces:
        vlan_id = int(vlan.replace('Vlan', ''))
        fdb_entry, available_macs = get_fdb(db, vlan_id, bridge_id_2_iface)
        all_available_macs |= available_macs
        fdb_entries.extend(fdb_entry)

    db.close(db.ASIC_DB)

    with open(filename, 'w') as fp:
        json.dump(fdb_entries, fp, indent=2, separators=(',', ': '))

    return all_available_macs

def main():
    all_available_macs = generate_fdb_entries('/tmp/fdb.json')
    generate_arp_entries('/tmp/arp.json', all_available_macs)

    return


if __name__ == '__main__':
    main()
