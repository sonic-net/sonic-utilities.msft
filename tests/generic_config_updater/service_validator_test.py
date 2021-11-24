import copy
import json
import jsondiff
import os
import unittest
from collections import defaultdict
from unittest.mock import patch

from generic_config_updater.services_validator import vlan_validator
import generic_config_updater.gu_common


# Mimics os.system call
#
os_system_expected_cmd = ""
msg = ""

def os_system_cfggen(cmd):
    assert cmd == os_system_expected_cmd, msg
    return 0


test_data = [
        { "old": {}, "upd": {}, "cmd": "" },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "cmd": ""
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.11" ] } } },
            "cmd": "systemctl restart dhcp_relay"
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": {
                "XXX": { "dhcp_servers": [ "10.10.10.10" ] },
                "YYY": { "dhcp_servers": [ ] } } },
            "cmd": ""
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": { "VLAN": {
                "XXX": { "dhcp_servers": [ "10.10.10.10" ] },
                "YYY": { "dhcp_servers": [ "10.12.12.1" ] } } },
            "cmd": "systemctl restart dhcp_relay"
        },
        {
            "old": { "VLAN": { "XXX": { "dhcp_servers": [ "10.10.10.10" ] } } },
            "upd": {},
            "cmd": "systemctl restart dhcp_relay"
        }
    ]

class TestServiceValidator(unittest.TestCase):

    @patch("generic_config_updater.change_applier.os.system")
    def test_change_apply(self, mock_os_sys):
        global os_system_expected_cmd

        mock_os_sys.side_effect = os_system_cfggen

        i = 0
        for entry in test_data:
            os_system_expected_cmd = entry["cmd"]
            msg = "case failed: {}".format(str(entry))

            vlan_validator(entry["old"], entry["upd"], None)


