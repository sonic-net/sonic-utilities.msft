#!/usr/bin/env python


import swsssdk
import json
from pprint import pprint


def generate_arp_entries(filename):
    db = swsssdk.SonicV2Connector()
    db.connect(db.APPL_DB, False)   # Make one attempt only

    arp_output = []

    keys = db.keys(db.APPL_DB, 'NEIGH_TABLE:*')
    keys = [] if keys is None else keys
    for key in keys:
        obj = {
          'OP': 'SET',
          key: db.get_all(db.APPL_DB, key)
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

def get_map_port_id_2_iface_name(db):
    port_id_2_iface = {}
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:*')
    keys = [] if keys is None else keys
    for key in keys:
        value = db.get_all(db.ASIC_DB, key)
        port_id = value['SAI_HOSTIF_ATTR_RIF_OR_PORT_ID']
        iface_name = value['SAI_HOSTIF_ATTR_NAME']
        port_id_2_iface[port_id] = iface_name

    return port_id_2_iface

def get_fdb(db, vlan_id, port_id_2_iface):
    fdb_types = {
      'SAI_FDB_ENTRY_TYPE_DYNAMIC': 'dynamic',
      'SAI_FDB_ENTRY_TYPE_STATIC' : 'static'
    }

    entries = []
    keys = db.keys(db.ASIC_DB, 'ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{*\"vlan\":\"%d\"}' % vlan_id)
    keys = [] if keys is None else keys
    for key in keys:
        key_obj = json.loads(key.replace('ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:', ''))
        vlan = str(key_obj['vlan'])
        mac = str(key_obj['mac'])
        if not is_mac_unicast(mac):
            continue
        mac = mac.replace(':', '-')
        # FIXME: mac is unicast
        # get attributes
        value = db.get_all(db.ASIC_DB, key)
        type = fdb_types[value['SAI_FDB_ENTRY_ATTR_TYPE']]
        port = port_id_2_iface[value['SAI_FDB_ENTRY_ATTR_PORT_ID']]

        obj = {
          'FDB_TABLE:Vlan%d:%s' % (vlan_id, mac) : {
            'type': type,
            'port': port,
          },
          'OP': 'SET'
        }

        entries.append(obj)

    return entries


def generate_fdb_entries(filename):
    fdb_entries = []

    db = swsssdk.SonicV2Connector()
    db.connect(db.ASIC_DB, False)   # Make one attempt only

    port_id_2_iface = get_map_port_id_2_iface_name(db)

    vlan_ifaces = get_vlan_ifaces()

    for vlan in vlan_ifaces:
        vlan_id = int(vlan.replace('Vlan', ''))
        fdb_entries.extend(get_fdb(db, vlan_id, port_id_2_iface))

    db.close(db.ASIC_DB)

    with open(filename, 'w') as fp:
        json.dump(fdb_entries, fp, indent=2, separators=(',', ': '))

    return

def main():
    generate_arp_entries('/tmp/arp.json')
    generate_fdb_entries('/tmp/fdb.json')

    return


if __name__ == '__main__':
    main()
