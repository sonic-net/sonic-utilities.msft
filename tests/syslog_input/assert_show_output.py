"""
Module holding the correct values for show CLI command outputs for the syslog_test.py
"""

show_syslog_empty="""\
SERVER IP    SOURCE IP    PORT    VRF
-----------  -----------  ------  -----
"""


show_syslog="""\
SERVER IP    SOURCE IP    PORT    VRF
-----------  -----------  ------  --------
2.2.2.2      1.1.1.1      514     default
3.3.3.3      1.1.1.1      514     mgmt
2222::2222   1111::1111   514     Vrf-Data
"""
