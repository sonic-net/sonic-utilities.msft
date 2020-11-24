import os

import pytest

from click.testing import CliRunner
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

show_ip_route_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 1d11h20m
B>*0.0.0.0/0 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                 via 10.0.0.5, PortChannel0005, 1d11h20m
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 1d11h20m
C>*8.0.0.0/32 is directly connected, Loopback4096, 1d11h21m
C>*10.0.0.0/31 is directly connected, PortChannel0002, 1d11h20m
C>*10.0.0.4/31 is directly connected, PortChannel0005, 1d11h20m
C>*10.1.0.32/32 is directly connected, Loopback0, 1d11h21m
B>*100.1.0.3/32 [20/0] via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.0/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                      via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.1/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                      via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.16/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.17/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.32/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.33/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.48/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.49/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.64/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.65/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.80/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.81/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.96/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.97/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                       via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.112/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.113/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.128/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.129/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.144/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.145/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.160/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.161/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.176/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.177/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.192/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.193/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.208/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.209/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.224/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.225/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.240/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
B>*192.168.0.241/32 [20/0] via 10.0.0.1, PortChannel0002, 1d11h20m
  *                        via 10.0.0.5, PortChannel0005, 1d11h20m
"""


show_specific_ip_route_expected_output = """\
Routing entry for 192.168.0.1/32
  Known via "bgp", distance 20, metric 0, best
  Last update 1d11h20m ago
  * 10.0.0.1, via PortChannel0002
  * 10.0.0.5, via PortChannel0005

"""

show_special_ip_route_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

C>*10.3.0.4/31 (blackhole)(vrf 2, PortChannel1014, inactive (recursive) 2d22h02m
C>*10.5.0.4/31 (ICMP unreachable) inactive 2d22h02m
C>*10.5.0.8/31 (ICMP admin-prohibited) inactive onlink, src 10.2.3.4 2d22h02m
C> 10.6.0.8/31 inactive 2d22h02m
C>q10.6.5.0/31 inactive 2d22h02m
C>r10.6.5.3/31 inactive 2d22h02m
C>*10.7.0.8/31 (ICMP admin-prohibited) inactive onlink, src 10.2.3.4, label IPv4 Explicit Null/OAM Alert/Extension/1212 2d22h02m
"""


show_ipv6_route_err_expected_output = """\
% Unknown command: show ipv6 route garbage
"""

show_ipv6_route_single_json_expected_output = """\
{
    "20c0:a8c7:0:81::/64": [
        {
            "destSelected": true,
            "distance": 20,
            "installed": true,
            "internalFlags": 8,
            "internalNextHopActiveNum": 2,
            "internalNextHopNum": 2,
            "internalStatus": 16,
            "metric": 0,
            "nexthops": [
                {
                    "active": true,
                    "afi": "ipv6",
                    "fib": true,
                    "flags": 3,
                    "interfaceIndex": 928,
                    "interfaceName": "PortChannel0011",
                    "ip": "fc00::e"
                },
                {
                    "active": true,
                    "afi": "ipv6",
                    "fib": true,
                    "flags": 3,
                    "interfaceIndex": 927,
                    "interfaceName": "PortChannel0008",
                    "ip": "fc00::a"
                }
            ],
            "prefix": "20c0:a8c7:0:81::/64",
            "protocol": "bgp",
            "selected": true,
            "table": 254,
            "uptime": "2d13h40m"
        }
    ]
}
"""

show_ipv6_route_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

B>*::/0 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *            via fc00::6, PortChannel0005, 1d11h34m
K *::/0 [210/0] via fd00::1, eth0, 1d11h34m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel0002, 1d11h34m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                      via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                          via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:10::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:11::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:30::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:31::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:40::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:41::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:50::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:51::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:60::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:61::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:70::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:71::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:80::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:81::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:90::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:91::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:a0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:a1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:b0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:b1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:c0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:c1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:d0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:d1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:e0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:e1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:f0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a800:0:f1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                      via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                          via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:10::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:11::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:20::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:21::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:30::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:31::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:40::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:41::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:50::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:51::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:60::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:61::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:70::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:71::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:80::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:81::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:90::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:91::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:a0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:a1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:b0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:b1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:c0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:c1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:d0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:d1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:e0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:e1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:f0::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
B>*20c0:a801:0:f1::/64 [20/0] via fc00::2, PortChannel0002, 1d11h34m
  *                           via fc00::6, PortChannel0005, 1d11h34m
C>*2603:10e2:400::/128 is directly connected, Loopback4096, 1d11h34m
C>*fc00::/126 is directly connected, PortChannel0002, 1d11h34m
C>*fc00::4/126 is directly connected, PortChannel0005, 1d11h34m
C>*fc00:1::32/128 is directly connected, Loopback0, 1d11h34m
C>*fd00::/80 is directly connected, eth0, 1d11h34m
C *fe80::/64 is directly connected, PortChannel0002, 1d11h34m
C *fe80::/64 is directly connected, PortChannel0005, 1d11h34m
C *fe80::/64 is directly connected, Ethernet20, 1d11h34m
C *fe80::/64 is directly connected, Ethernet16, 1d11h34m
C *fe80::/64 is directly connected, Ethernet4, 1d11h34m
C *fe80::/64 is directly connected, Ethernet0, 1d11h34m
C *fe80::/64 is directly connected, Loopback4096, 1d11h34m
C *fe80::/64 is directly connected, Loopback0, 1d11h34m
C>*fe80::/64 is directly connected, eth0, 1d11h34m
"""

class TestShowIpRouteCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        #in case someone did not clean up properly so undo the multi-asic mock here
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        import mock_tables.dbconnector

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_specific_route'], indirect=['setup_single_bgp_instance'])
    def test_show_specific_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["192.168.0.1"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_specific_ip_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_special_route'], indirect=['setup_single_bgp_instance'])
    def test_show_special_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_special_ip_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_specific_route'], indirect=['setup_single_bgp_instance'])
    def test_show_specific_ipv6_route_json(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["20c0:a8c7:0:81::", "json"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ipv6_route_single_json_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ipv6_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ipv6_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route_err'], indirect=['setup_single_bgp_instance'])
    def test_show_ipv6_route_err(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["garbage"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ipv6_route_err_expected_output
