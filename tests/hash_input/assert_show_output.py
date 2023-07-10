"""
Module holding the correct values for show CLI command outputs for the hash_test.py
"""

show_hash_empty="""\
ECMP HASH    LAG HASH
-----------  ----------
"""

show_hash_ecmp="""\
ECMP HASH          LAG HASH
-----------------  ----------
DST_MAC            N/A
SRC_MAC
ETHERTYPE
IP_PROTOCOL
DST_IP
SRC_IP
L4_DST_PORT
L4_SRC_PORT
INNER_DST_MAC
INNER_SRC_MAC
INNER_ETHERTYPE
INNER_IP_PROTOCOL
INNER_DST_IP
INNER_SRC_IP
INNER_L4_DST_PORT
INNER_L4_SRC_PORT
"""

show_hash_lag="""\
ECMP HASH    LAG HASH
-----------  -----------------
N/A          DST_MAC
             SRC_MAC
             ETHERTYPE
             IP_PROTOCOL
             DST_IP
             SRC_IP
             L4_DST_PORT
             L4_SRC_PORT
             INNER_DST_MAC
             INNER_SRC_MAC
             INNER_ETHERTYPE
             INNER_IP_PROTOCOL
             INNER_DST_IP
             INNER_SRC_IP
             INNER_L4_DST_PORT
             INNER_L4_SRC_PORT
"""

show_hash_ecmp_and_lag="""\
ECMP HASH          LAG HASH
-----------------  -----------------
DST_MAC            DST_MAC
SRC_MAC            SRC_MAC
ETHERTYPE          ETHERTYPE
IP_PROTOCOL        IP_PROTOCOL
DST_IP             DST_IP
SRC_IP             SRC_IP
L4_DST_PORT        L4_DST_PORT
L4_SRC_PORT        L4_SRC_PORT
INNER_DST_MAC      INNER_DST_MAC
INNER_SRC_MAC      INNER_SRC_MAC
INNER_ETHERTYPE    INNER_ETHERTYPE
INNER_IP_PROTOCOL  INNER_IP_PROTOCOL
INNER_DST_IP       INNER_DST_IP
INNER_SRC_IP       INNER_SRC_IP
INNER_L4_DST_PORT  INNER_L4_DST_PORT
INNER_L4_SRC_PORT  INNER_L4_SRC_PORT
"""

show_hash_capabilities_no="""\
ECMP HASH        LAG HASH
---------------  ---------------
no capabilities  no capabilities
"""

show_hash_capabilities_na="""\
ECMP HASH    LAG HASH
-----------  ----------
N/A          N/A
"""

show_hash_capabilities_empty="""\
ECMP HASH      LAG HASH
-------------  -------------
not supported  not supported
"""

show_hash_capabilities_ecmp="""\
ECMP HASH          LAG HASH
-----------------  -------------
IN_PORT            not supported
DST_MAC
SRC_MAC
ETHERTYPE
VLAN_ID
IP_PROTOCOL
DST_IP
SRC_IP
L4_DST_PORT
L4_SRC_PORT
INNER_DST_MAC
INNER_SRC_MAC
INNER_ETHERTYPE
INNER_IP_PROTOCOL
INNER_DST_IP
INNER_SRC_IP
INNER_L4_DST_PORT
INNER_L4_SRC_PORT
"""

show_hash_capabilities_lag="""\
ECMP HASH      LAG HASH
-------------  -----------------
not supported  IN_PORT
               DST_MAC
               SRC_MAC
               ETHERTYPE
               VLAN_ID
               IP_PROTOCOL
               DST_IP
               SRC_IP
               L4_DST_PORT
               L4_SRC_PORT
               INNER_DST_MAC
               INNER_SRC_MAC
               INNER_ETHERTYPE
               INNER_IP_PROTOCOL
               INNER_DST_IP
               INNER_SRC_IP
               INNER_L4_DST_PORT
               INNER_L4_SRC_PORT
"""

show_hash_capabilities_ecmp_and_lag="""\
ECMP HASH          LAG HASH
-----------------  -----------------
IN_PORT            IN_PORT
DST_MAC            DST_MAC
SRC_MAC            SRC_MAC
ETHERTYPE          ETHERTYPE
VLAN_ID            VLAN_ID
IP_PROTOCOL        IP_PROTOCOL
DST_IP             DST_IP
SRC_IP             SRC_IP
L4_DST_PORT        L4_DST_PORT
L4_SRC_PORT        L4_SRC_PORT
INNER_DST_MAC      INNER_DST_MAC
INNER_SRC_MAC      INNER_SRC_MAC
INNER_ETHERTYPE    INNER_ETHERTYPE
INNER_IP_PROTOCOL  INNER_IP_PROTOCOL
INNER_DST_IP       INNER_DST_IP
INNER_SRC_IP       INNER_SRC_IP
INNER_L4_DST_PORT  INNER_L4_DST_PORT
INNER_L4_SRC_PORT  INNER_L4_SRC_PORT
"""
