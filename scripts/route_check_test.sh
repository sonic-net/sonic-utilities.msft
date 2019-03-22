#!/usr/bin/env bash

# add a route, interface & route-entry to simulate error
#
redis-cli -n 0 hmset "ROUTE_TABLE:20c0:d9b8:99:80::/64" "nexthop" "fc00::72,fc00::76,fc00::7a,fc00::7e" "ifname" "PortChannel01,PortChannel02,PortChannel03,PortChannel04"


redis-cli -n 1 hmset "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest\":\"192.193.120.255/25\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000022\"}" "SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID" "oid:0x5000000000614"

redis-cli -n 0 hmset  "INTF_TABLE:PortChannel01:10.0.0.99/31" "scope" "global" "family" "IPv4"

echo "expect errors!\n------\nRunning Route Check...\n"
./route_check.py
echo "return value: $?"

redis-cli -n 0 del "ROUTE_TABLE:20c0:d9b8:99:80::/64"
redis-cli -n 1 del "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest\":\"192.193.120.255/25\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000022\"}"
redis-cli -n 0 del "INTF_TABLE:PortChannel01:10.0.0.99/31"


echo "expect success!\n------\nRunning Route Check...\n"
./route_check.py
echo "return value: $?"
