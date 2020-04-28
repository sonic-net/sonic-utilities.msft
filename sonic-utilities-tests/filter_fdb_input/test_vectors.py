"""
    Filter FDB entries test vector
"""
filterFdbEntriesTestVector = [
    {
        "arp":[
        ],
        "fdb": [
        ],
        "expected_fdb": [
        ],
    },
    {
        "arp":[
            {
                "NEIGH_TABLE:Vlan1000:192.168.0.10": {
                    "neigh": "72:06:00:01:00:08",
                    "family": "IPv4"
                },
                "OP": "SET"
            },
        ],
        "fdb": [
            {
                "FDB_TABLE:Vlan1000:72-06-00-01-01-16": {
                    "type": "dynamic",
                    "port": "Ethernet22"
                },
                "OP": "SET"
            },
        ],
        "expected_fdb": [
        ],
    },
    {
        "arp":[
            {
                "NEIGH_TABLE:Vlan1000:192.168.0.10": {
                    "neigh": "72:06:00:01:01:16",
                    "family": "IPv4"
                },
                "OP": "SET"
            },
        ],
        "fdb": [
            {
                "FDB_TABLE:Vlan1000:72-06-00-01-01-16": {
                    "type": "dynamic",
                    "port": "Ethernet22"
                },
                "OP": "SET"
            },
        ],
        "expected_fdb": [
            {
                "FDB_TABLE:Vlan1000:72-06-00-01-01-16": {
                    "type": "dynamic",
                    "port": "Ethernet22"
                },
                "OP": "SET"
            },
        ],
    },
    {
        "arp": "sonic-utilities-tests/filter_fdb_input/arp.json",
        "fdb": "sonic-utilities-tests/filter_fdb_input/fdb.json",
        "expected_fdb": "sonic-utilities-tests/filter_fdb_input/expected_fdb.json"
    },
]
