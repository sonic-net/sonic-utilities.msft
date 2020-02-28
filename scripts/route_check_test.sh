#!/usr/bin/env bash

# add a route, interface & route-entry to simulate error
#
sonic-db-cli APPL_DB hmset "ROUTE_TABLE:20c0:d9b8:99:80::/64" "nexthop" "fc00::72,fc00::76,fc00::7a,fc00::7e" "ifname" "PortChannel01,PortChannel02,PortChannel03,PortChannel04"


sonic-db-cli ASIC_DB hmset "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest\":\"192.193.120.255/25\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000022\"}" "SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID" "oid:0x5000000000614"

sonic-db-cli APPL_DB hmset  "INTF_TABLE:PortChannel01:10.0.0.99/31" "scope" "global" "family" "IPv4"

echo "expect errors!\n------\nRunning Route Check...\n"
./route_check.py
echo "return value: $?"

sonic-db-cli APPL_DB del "ROUTE_TABLE:20c0:d9b8:99:80::/64"
sonic-db-cli ASIC_DB del "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest\":\"192.193.120.255/25\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000022\"}"
sonic-db-cli APPL_DB del "INTF_TABLE:PortChannel01:10.0.0.99/31"


echo "expect success!\n------\nRunning Route Check...\n"
./route_check.py
echo "return value: $?"
