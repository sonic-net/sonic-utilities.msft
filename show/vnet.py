import click
import utilities_common.cli as clicommon
from natsort import natsorted
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from tabulate import tabulate


#
# 'vnet' command ("show vnet")
#
@click.group(cls=clicommon.AliasedGroup)
def vnet():
    """Show vnet related information"""
    pass


@vnet.command()
@click.argument('vnet_name', required=True)
def name(vnet_name):
    """Show vnet name <vnet name> information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vnet name', 'vxlan tunnel', 'vni', 'peer list']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_entry('VNET', vnet_name)

    def tablelize(vnet_key, vnet_data):
        table = []
        if vnet_data:
            r = []
            r.append(vnet_key)
            r.append(vnet_data.get('vxlan_tunnel'))
            r.append(vnet_data.get('vni'))
            r.append(vnet_data.get('peer_list'))
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_name, vnet_data), header))


@vnet.command()
def brief():
    """Show vnet brief information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['vnet name', 'vxlan tunnel', 'vni', 'peer list']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_table('VNET')
    vnet_keys = natsorted(list(vnet_data.keys()))

    def tablelize(vnet_keys, vnet_data):
        table = []
        for k in vnet_keys:
            r = []
            r.append(k)
            r.append(vnet_data[k].get('vxlan_tunnel'))
            r.append(vnet_data[k].get('vni'))
            r.append(vnet_data[k].get('peer_list'))
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_keys, vnet_data), header))


@vnet.command()
@click.argument('vnet_alias', required=False)
def alias(vnet_alias):
    """Show vnet alias to name information"""
    config_db = ConfigDBConnector()
    config_db.connect()
    header = ['Alias', 'Name']

    # Fetching data from config_db for VNET
    vnet_data = config_db.get_table('VNET')
    vnet_keys = natsorted(list(vnet_data.keys()))

    def tablelize(vnet_keys, vnet_data, vnet_alias):
        table = []
        for k in vnet_keys:
            r = []
            if vnet_alias is not None:
                if vnet_data[k].get('guid') == vnet_alias:
                    r.append(vnet_data[k].get('guid'))
                    r.append(k)
                    table.append(r)
                    return table
                else:
                    continue

            r.append(vnet_data[k].get('guid'))
            r.append(k)
            table.append(r)
        return table

    click.echo(tabulate(tablelize(vnet_keys, vnet_data, vnet_alias), header))


@vnet.command()
def interfaces():
    """Show vnet interfaces information"""
    config_db = ConfigDBConnector()
    config_db.connect()

    header = ['vnet name', 'interfaces']

    # Fetching data from config_db for interfaces
    intfs_data = config_db.get_table("INTERFACE")
    vlan_intfs_data = config_db.get_table("VLAN_INTERFACE")

    vnet_intfs = {}
    for k, v in intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    for k, v in vlan_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    table = []
    for k, v in vnet_intfs.items():
        r = []
        r.append(k)
        r.append(",".join(natsorted(v)))
        table.append(r)

    click.echo(tabulate(table, header))


@vnet.command()
def neighbors():
    """Show vnet neighbors information"""
    config_db = ConfigDBConnector()
    config_db.connect()

    header = ['<vnet_name>', 'neighbor', 'mac_address', 'interfaces']

    # Fetching data from config_db for interfaces
    intfs_data = config_db.get_table("INTERFACE")
    vlan_intfs_data = config_db.get_table("VLAN_INTERFACE")

    vnet_intfs = {}
    for k, v in intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    for k, v in vlan_intfs_data.items():
        if 'vnet_name' in v:
            vnet_name = v['vnet_name']
            if vnet_name in vnet_intfs:
                vnet_intfs[vnet_name].append(k)
            else:
                vnet_intfs[vnet_name] = [k]

    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    # Fetching data from appl_db for neighbors
    nbrs = appl_db.keys(appl_db.APPL_DB, "NEIGH_TABLE:*")
    nbrs_data = {}
    for nbr in nbrs if nbrs else []:
        tbl, intf, ip = nbr.split(":", 2)
        mac = appl_db.get(appl_db.APPL_DB, nbr, 'neigh')
        if intf in nbrs_data:
            nbrs_data[intf].append((ip, mac))
        else:
            nbrs_data[intf] = [(ip, mac)]

    table = []
    for k, v in vnet_intfs.items():
        v = natsorted(v)
        header[0] = k
        table = []
        for intf in v:
            if intf in nbrs_data:
                for ip, mac in nbrs_data[intf]:
                    r = ["", ip, mac, intf]
                    table.append(r)
        click.echo(tabulate(table, header))
        click.echo()

    if not bool(vnet_intfs):
        click.echo(tabulate(table, header))


@vnet.group()
def routes():
    """Show vnet routes related information"""
    pass


@routes.command()
def all():
    """Show all vnet routes"""
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    header = ['vnet name', 'prefix', 'nexthop', 'interface']

    # Fetching data from appl_db for VNET ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TABLE:*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('nexthop'))
        r.append(val.get('ifname'))
        table.append(r)

    click.echo(tabulate(table, header))

    click.echo()

    header = ['vnet name', 'prefix', 'endpoint', 'mac address', 'vni']

    # Fetching data from appl_db for VNET TUNNEL ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TUNNEL_TABLE:*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('endpoint'))
        r.append(val.get('mac_address'))
        r.append(val.get('vni'))
        table.append(r)

    click.echo(tabulate(table, header))


@routes.command()
def tunnel():
    """Show vnet tunnel routes"""
    appl_db = SonicV2Connector()
    appl_db.connect(appl_db.APPL_DB)

    header = ['vnet name', 'prefix', 'endpoint', 'mac address', 'vni']

    # Fetching data from appl_db for VNET TUNNEL ROUTES
    vnet_rt_keys = appl_db.keys(appl_db.APPL_DB, "VNET_ROUTE_TUNNEL_TABLE:*")
    vnet_rt_keys = natsorted(vnet_rt_keys) if vnet_rt_keys else []

    table = []
    for k in vnet_rt_keys:
        r = []
        r.extend(k.split(":", 2)[1:])
        val = appl_db.get_all(appl_db.APPL_DB, k)
        r.append(val.get('endpoint'))
        r.append(val.get('mac_address'))
        r.append(val.get('vni'))
        table.append(r)

    click.echo(tabulate(table, header))
