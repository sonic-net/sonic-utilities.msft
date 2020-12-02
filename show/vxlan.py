import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsssdk import ConfigDBConnector
from tabulate import tabulate


#
# 'vxlan' command ("show vxlan")
#
@click.group(cls=clicommon.AliasedGroup)
def vxlan():
    """Show vxlan related information"""
    pass


@vxlan.command()
@click.argument('vxlan_name', required=True)
def name(vxlan_name):
    """Show vxlan name <vxlan_name> information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vxlan tunnel name', 'source ip', 'destination ip', 'tunnel map name', 'tunnel map mapping(vni -> vlan)']

    # Fetching data from config_db for VXLAN TUNNEL
    vxlan_data = config_db.get_entry('VXLAN_TUNNEL', vxlan_name)

    table = []
    if vxlan_data:
        r = []
        r.append(vxlan_name)
        r.append(vxlan_data.get('src_ip'))
        r.append(vxlan_data.get('dst_ip'))
        vxlan_map_keys = config_db.keys(config_db.CONFIG_DB,
                                        'VXLAN_TUNNEL_MAP{}{}{}*'.format(config_db.KEY_SEPARATOR, vxlan_name, config_db.KEY_SEPARATOR))
        if vxlan_map_keys:
            vxlan_map_mapping = config_db.get_all(config_db.CONFIG_DB, vxlan_map_keys[0])
            r.append(vxlan_map_keys[0].split(config_db.KEY_SEPARATOR, 2)[2])
            r.append("{} -> {}".format(vxlan_map_mapping.get('vni'), vxlan_map_mapping.get('vlan')))
        table.append(r)

    click.echo(tabulate(table, header))


@vxlan.command()
def tunnel():
    """Show vxlan tunnel information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vxlan tunnel name', 'source ip', 'destination ip', 'tunnel map name', 'tunnel map mapping(vni -> vlan)']

    # Fetching data from config_db for VXLAN TUNNEL
    vxlan_data = config_db.get_table('VXLAN_TUNNEL')
    vxlan_keys = natsorted(list(vxlan_data.keys()))

    table = []
    for k in vxlan_keys:
        r = []
        r.append(k)
        r.append(vxlan_data[k].get('src_ip'))
        r.append(vxlan_data[k].get('dst_ip'))
        vxlan_map_keys = config_db.keys(config_db.CONFIG_DB,
                                        'VXLAN_TUNNEL_MAP{}{}{}*'.format(config_db.KEY_SEPARATOR, k, config_db.KEY_SEPARATOR))
        if vxlan_map_keys:
            vxlan_map_mapping = config_db.get_all(config_db.CONFIG_DB, vxlan_map_keys[0])
            r.append(vxlan_map_keys[0].split(config_db.KEY_SEPARATOR, 2)[2])
            r.append("{} -> {}".format(vxlan_map_mapping.get('vni'), vxlan_map_mapping.get('vlan')))
        table.append(r)

    click.echo(tabulate(table, header))
