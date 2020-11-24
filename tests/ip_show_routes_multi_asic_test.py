import os

import pytest

from click.testing import CliRunner
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

show_ip_route_multi_asic_display_all_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

asic0:
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h00m
B>*0.0.0.0/0 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                 via 10.0.0.1, PortChannel0002, 2d22h00m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h00m
C>*8.0.0.0/32 is directly connected, Loopback4096, 2d22h00m
C>*10.0.0.0/31 is directly connected, PortChannel4001, 2d22h00m
C>*10.0.0.4/31 is directly connected, PortChannel0005, 2d22h00m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h00m
B>*100.1.0.3/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
B>*192.168.0.0/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.1/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.32/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.96/32 [20/0] via 10.0.0.5, Ethernet-BP4, 2d22h00m
  *                       via 10.0.0.1, Ethernet-BP0, 2d22h00m
B>*192.168.0.97/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.192/32 [20/0] via 10.0.0.5, Ethernet-BP4, 2d22h00m
  *                        via 10.0.0.1, PortChannel4001, 2d22h00m
B>*192.168.0.193/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.208/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.209/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.224/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.225/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.240/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
B>*192.168.0.241/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
asic1:
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h01m
B>*0.0.0.0/0 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                 via 10.0.0.7, PortChannel0007, 2d22h01m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h01m
C>*8.0.0.1/32 is directly connected, Loopback4096, 2d22h01m
C>*10.0.0.0/31 is directly connected, PortChannel4009, 2d22h01m
C>*10.0.0.4/31 is directly connected, PortChannel0008, 2d22h01m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h01m
B>*100.1.0.3/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
B>*192.168.0.0/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                      via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.1/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                      via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.32/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                       via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.96/32 [20/0] via 10.0.0.8, Ethernet-BP260, 2d22h01m
  *                       via 10.0.0.7, Ethernet-BP256, 2d22h01m
B>*192.168.0.97/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                       via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.192/32 [20/0] via 10.0.0.8, Ethernet-BP260, 2d22h01m
  *                        via 10.0.0.7, PortChannel4009, 2d22h01m
B>*192.168.0.193/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.208/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.209/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.224/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.225/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, 2d22h01m
B>*192.168.0.240/32 [20/0] via 10.0.0.8, Ethernet-BP260, 2d22h01m
  *                        via 10.0.0.7, PortChannel4009, 2d22h01m
B>*192.168.0.241/32 [20/0] via 10.0.0.8, PortChannel0008, 2d22h01m
  *                        via 10.0.0.7, PortChannel0007, 2d22h01m
asic2:
K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h02m
B>*0.0.0.0/0 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                 via 10.0.0.15, PortChannel1015, 2d22h02m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h02m
C>*8.0.0.2/32 is directly connected, Loopback4096, 2d22h02m
C>*10.0.0.0/31 is directly connected, PortChannel4001, 2d22h02m
C>*10.0.0.4/31 is directly connected, PortChannel1016, 2d22h02m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h02m
B>*100.1.0.3/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
B>*192.168.0.0/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                      via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.1/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                      via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.32/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                       via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.96/32 [20/0] via 10.0.0.16, Ethernet-BP24, 2d22h02m
  *                       via 10.0.0.15, Ethernet-BP20, 2d22h02m
B>*192.168.0.97/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                       via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.192/32 [20/0] via 10.0.0.16, Ethernet-BP24, 2d22h02m
  *                        via 10.0.0.15, PortChannel4001, 2d22h02m
B>*192.168.0.193/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.208/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.209/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.224/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.225/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.240/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, 2d22h02m
B>*192.168.0.241/32 [20/0] via 10.0.0.16, PortChannel1016, 2d22h02m
  *                        via 10.0.0.15, PortChannel1015, 2d22h02m
"""

show_ip_route_multi_asic_display_all_front_expected_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

K *0.0.0.0/0 [210/0] via 240.127.1.1, eth0, 2d22h00m
B>*0.0.0.0/0 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                 via 10.0.0.1, PortChannel0002, 2d22h00m
  *                 via 10.0.0.15, PortChannel1015, 2d22h00m
  *                 via 10.0.0.16, PortChannel1016, 2d22h00m
S 0.0.0.0/0 [200/0] via 10.3.146.1, inactive 2d22h00m
C>*8.0.0.0/32 is directly connected, Loopback4096, 2d22h00m
C>*8.0.0.2/32 is directly connected, Loopback4096, 2d22h02m
C>*10.0.0.4/31 is directly connected, PortChannel0005, 2d22h00m
C>*10.0.0.4/31 is directly connected, PortChannel1016, 2d22h02m
C>*10.1.0.32/32 is directly connected, Loopback0, 2d22h00m
B>*100.1.0.3/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                    via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.0/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, 2d22h00m
  *                      via 10.0.0.15, PortChannel1015, 2d22h00m
  *                      via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.1/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                      via 10.0.0.1, PortChannel0002, 2d22h00m
  *                      via 10.0.0.15, PortChannel1015, 2d22h00m
  *                      via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.32/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, 2d22h00m
  *                       via 10.0.0.15, PortChannel1015, 2d22h00m
  *                       via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.97/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                       via 10.0.0.1, PortChannel0002, 2d22h00m
  *                       via 10.0.0.15, PortChannel1015, 2d22h00m
  *                       via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.193/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.208/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.209/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.224/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.225/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.240/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, 2d22h00m
B>*192.168.0.241/32 [20/0] via 10.0.0.5, PortChannel0005, 2d22h00m
  *                        via 10.0.0.1, PortChannel0002, 2d22h00m
  *                        via 10.0.0.15, PortChannel1015, 2d22h00m
  *                        via 10.0.0.16, PortChannel1016, 2d22h00m
"""

show_ipv6_route_multi_asic_all_namesapce_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

K *::/0 [210/0] via fd00::1, eth0, 2d22h00m
B>*::/0 [20/0] via fc00::6, PortChannel0005, 2d22h00m
  *            via fc00::2, PortChannel0002, 2d22h00m
  *            via fc00::2, PortChannel1015, 2d22h00m
  *            via fc00::6, PortChannel1016, 2d22h00m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel0002, 2d22h00m
  *                       via fc00::2, PortChannel1015, 2d22h00m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel0005, 2d22h00m
  *                       via fc00::6, PortChannel1016, 2d22h00m
B>*20c0:a800:0:1::/64 [20/0] via fc00::6, PortChannel0005, 2d22h00m
  *                          via fc00::2, PortChannel0002, 2d22h00m
  *                          via fc00::2, PortChannel1015, 2d22h00m
  *                          via fc00::6, PortChannel1016, 2d22h00m
B>*20c0:a800:0:10::/64 [20/0] via fc00::6, PortChannel0005, 2d22h00m
  *                           via fc00::2, PortChannel0002, 2d22h00m
  *                           via fc00::2, PortChannel1015, 2d22h00m
  *                           via fc00::6, PortChannel1016, 2d22h00m
B>*20c0:a800:0:11::/64 [20/0] via fc00::6, PortChannel0002, 2d22h00m
  *                           via fc00::6, PortChannel1015, 2d22h00m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel0002, 2d22h00m
  *                           via fc00::2, PortChannel1015, 2d22h00m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel0002, 2d22h00m
  *                           via fc00::2, PortChannel1015, 2d22h00m
C>*2603:10e2:400::/128 is directly connected, Loopback4096, 2d22h00m
C>*2603:10e2:400::2/128 is directly connected, Loopback4096, 2d22h02m
C>*fc00::4/126 is directly connected, PortChannel0005, 2d22h00m
C>*fc00::4/126 is directly connected, PortChannel1016, 2d22h02m
C>*fc00:1::32/128 is directly connected, Loopback0, 2d22h00m
C>*fd00::/80 is directly connected, eth0, 2d22h00m
C>*fe80::/64 is directly connected, eth0, 2d22h00m
C *fe80::/64 is directly connected, Loopback0, 2d22h00m
C *fe80::/64 is directly connected, Loopback4096, 2d22h00m
C *fe80::/64 is directly connected, Ethernet16, 2d22h00m
C *fe80::/64 is directly connected, Ethernet20, 2d22h00m
C *fe80::/64 is directly connected, PortChannel0005, 2d22h00m
C *fe80::/64 is directly connected, PortChannel1016, 2d22h02m
C *fe80::/64 is directly connected, Ethernet24, 2d22h02m
"""

show_ipv6_route_multi_asic_single_namesapce_output = """\
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

K *::/0 [210/0] via fd00::1, eth0, 2d22h02m
B>*::/0 [20/0] via fc00::6, PortChannel1016, 2d22h02m
  *            via fc00::2, PortChannel1015, 2d22h02m
B>*2064:100::1/128 [20/0] via fc00::2, PortChannel1015, 2d22h02m
B>*2064:100::3/128 [20/0] via fc00::6, PortChannel1016, 2d22h02m
B>*20c0:a800:0:1::/64 [20/0] via fc00::6, PortChannel1016, 2d22h02m
  *                          via fc00::2, PortChannel1015, 2d22h02m
B>*20c0:a800:0:10::/64 [20/0] via fc00::6, PortChannel1016, 2d22h02m
  *                           via fc00::2, PortChannel1015, 2d22h02m
B>*20c0:a800:0:11::/64 [20/0] via fc00::6, PortChannel1015, 2d22h02m
B>*20c0:a800:0:20::/64 [20/0] via fc00::2, PortChannel1015, 2d22h02m
B>*20c0:a800:0:21::/64 [20/0] via fc00::2, PortChannel1015, 2d22h02m
C>*2603:10e2:400::2/128 is directly connected, Loopback4096, 2d22h02m
C>*fc00::4/126 is directly connected, PortChannel1016, 2d22h02m
C>*fc00:1::32/128 is directly connected, Loopback0, 2d22h02m
C>*fd00::/80 is directly connected, eth0, 2d22h02m
C>*fe80::/64 is directly connected, eth0, 2d22h02m
C *fe80::/64 is directly connected, Loopback0, 2d22h02m
C *fe80::/64 is directly connected, Loopback4096, 2d22h02m
C *fe80::/64 is directly connected, Ethernet24, 2d22h02m
C *fe80::/64 is directly connected, Ethernet20, 2d22h02m
C *fe80::/64 is directly connected, PortChannel1016, 2d22h02m
"""

show_ip_route_multi_asic_invalid_namesapce_err_output = """\
namespace 'asic7' is not valid. valid name spaces are:
['asic0', 'asic1', 'asic2']
"""

show_ip_route_multi_asic_invalid_display_err_output = """\
dislay option 'everything' is not a valid option.
"""

show_ip_route_multi_asic_specific_route_output = """\
Routing entry for 10.0.0.4/31
  Known via "connected", distance 0, metric 0, best
  Last update 2d22h00m ago
  * directly connected, PortChannel0005


Routing entry for 10.0.0.4/31
  Known via "connected", distance 0, metric 0, best
  Last update 2d22h02m ago
  * directly connected, PortChannel1016


"""

show_ipv6_route_multi_asic_specific_route_output = """\
Routing entry for 2603:10e2:400::/128
  Known via "connected", distance 0, metric 0, best
  Last update 2d22h00m ago
  * directly connected, Loopback4096


"""

class TestMultiAiscShowIpRouteDisplayAllCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import mock_multi_asic_3_asics
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_front_end(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-dfrontend"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_multi_asic_display_all_front_expected_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_all(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-dall"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_multi_asic_display_all_expected_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_specific_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_specific(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["10.0.0.4"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_multi_asic_specific_route_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_specific_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_specific(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["2603:10e2:400::"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ipv6_route_multi_asic_specific_route_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_namespace_option_err(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-nasic7"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_multi_asic_invalid_namesapce_err_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_display_option_err(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-deverything"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_multi_asic_invalid_display_err_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_all_namespace(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["-dfrontend"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ipv6_route_multi_asic_all_namesapce_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_single_namespace(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["-nasic2"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ipv6_route_multi_asic_single_namesapce_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        import imp
        from sonic_py_common import multi_asic
        imp.reload(multi_asic)
        import mock_tables.dbconnector
