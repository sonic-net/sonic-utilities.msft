import sys
import os
import pytest
from unittest import mock
import subprocess
from swsscommon.swsscommon import ConfigDBConnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

from imp import load_source
load_source('neighbor_advertiser', scripts_path+'/neighbor_advertiser')
import neighbor_advertiser

class TestNeighborAdvertiser(object):
    @pytest.fixture
    def set_up(self):
        neighbor_advertiser.connect_config_db()
        neighbor_advertiser.connect_app_db()

    def test_neighbor_advertiser_slice(self, set_up):
        neighbor_advertiser.get_link_local_addr = mock.MagicMock(return_value='fe80::1e34:daff:fe1e:2800')
        output = neighbor_advertiser.construct_neighbor_advertiser_slice()
        expected_output = dict(
            {
                'respondingSchemes': {'durationInSec': 300},
                'switchInfo': {'ipv6Addr': '', 'hwSku': 'Mellanox-SN3800-D112C8', 'ipv4Addr': '', 'name': 'sonic-switch'},
                'vlanInterfaces': [{
                        'ipv4AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': '192.168.0.1', 'ipPrefixLen': '32'}
                        ],
                        'ipv6AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fc02:1000::1', 'ipPrefixLen': '128'},
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fe80::1e34:daff:fe1e:2800', 'ipPrefixLen': '128'}
                        ],
                        'vxlanId': '1000',
                        'vlanId': '1000',
                        'vxlanPort': '13550'
                    },
                    {
                        'ipv4AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': '192.168.0.10', 'ipPrefixLen': '21'}
                        ],
                        'ipv6AddrMappings': [
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fc02:1011::1', 'ipPrefixLen': '64'},
                            {'macAddr': '1d:34:db:16:a6:00', 'ipAddr': 'fe80::1e34:daff:fe1e:2800', 'ipPrefixLen': '128'}
                        ],
                        'vxlanId': '2000',
                        'vlanId': '2000',
                        'vxlanPort': '13550'
                    }]
            }
        )
        assert output == expected_output
