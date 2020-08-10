import click
from natsort import natsorted
from tabulate import tabulate

import utilities_common.cli as clicommon

@click.group(cls=clicommon.AliasedGroup)
def vlan():
    """Show VLAN information"""
    pass

@vlan.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def brief(db, verbose):
    """Show all bridge information"""
    header = ['VLAN ID', 'IP Address', 'Ports', 'Port Tagging', 'DHCP Helper Address']
    body = []

    # Fetching data from config db for VLAN, VLAN_INTERFACE and VLAN_MEMBER
    vlan_dhcp_helper_data = db.cfgdb.get_table('VLAN')
    vlan_ip_data = db.cfgdb.get_table('VLAN_INTERFACE')
    vlan_ports_data = db.cfgdb.get_table('VLAN_MEMBER')

    # Defining dictionaries for DHCP Helper address, Interface Gateway IP,
    # VLAN ports and port tagging
    vlan_dhcp_helper_dict = {}
    vlan_ip_dict = {}
    vlan_ports_dict = {}
    vlan_tagging_dict = {}

    # Parsing DHCP Helpers info
    for key in natsorted(vlan_dhcp_helper_data.keys()):
        try:
            if vlan_dhcp_helper_data[key]['dhcp_servers']:
                vlan_dhcp_helper_dict[str(key.strip('Vlan'))] = vlan_dhcp_helper_data[key]['dhcp_servers']
        except KeyError:
            vlan_dhcp_helper_dict[str(key.strip('Vlan'))] = " "

    # Parsing VLAN Gateway info
    for key in natsorted(vlan_ip_data.keys()):
        if not clicommon.is_ip_prefix_in_key(key):
            continue
        interface_key = str(key[0].strip("Vlan"))
        interface_value = str(key[1])
        if interface_key in vlan_ip_dict:
            vlan_ip_dict[interface_key].append(interface_value)
        else:
            vlan_ip_dict[interface_key] = [interface_value]

    iface_alias_converter = clicommon.InterfaceAliasConverter(db)

    # Parsing VLAN Ports info
    for key in natsorted(vlan_ports_data.keys()):
        ports_key = str(key[0].strip("Vlan"))
        ports_value = str(key[1])
        ports_tagging = vlan_ports_data[key]['tagging_mode']
        if ports_key in vlan_ports_dict:
            if clicommon.get_interface_naming_mode() == "alias":
                ports_value = iface_alias_converter.name_to_alias(ports_value)
            vlan_ports_dict[ports_key].append(ports_value)
        else:
            if clicommon.get_interface_naming_mode() == "alias":
                ports_value = iface_alias_converter.name_to_alias(ports_value)
            vlan_ports_dict[ports_key] = [ports_value]
        if ports_key in vlan_tagging_dict:
            vlan_tagging_dict[ports_key].append(ports_tagging)
        else:
            vlan_tagging_dict[ports_key] = [ports_tagging]

    # Printing the following dictionaries in tablular forms:
    # vlan_dhcp_helper_dict={}, vlan_ip_dict = {}, vlan_ports_dict = {}
    # vlan_tagging_dict = {}
    for key in natsorted(vlan_dhcp_helper_dict.keys()):
        if key not in vlan_ip_dict:
            ip_address = ""
        else:
            ip_address = ','.replace(',', '\n').join(vlan_ip_dict[key])
        if key not in vlan_ports_dict:
            vlan_ports = ""
        else:
            vlan_ports = ','.replace(',', '\n').join((vlan_ports_dict[key]))
        if key not in vlan_dhcp_helper_dict:
            dhcp_helpers = ""
        else:
            dhcp_helpers = ','.replace(',', '\n').join(vlan_dhcp_helper_dict[key])
        if key not in vlan_tagging_dict:
            vlan_tagging = ""
        else:
            vlan_tagging = ','.replace(',', '\n').join((vlan_tagging_dict[key]))
        body.append([key, ip_address, vlan_ports, vlan_tagging, dhcp_helpers])
    click.echo(tabulate(body, header, tablefmt="grid"))

@vlan.command()
@clicommon.pass_db
def config(db):
    data = db.cfgdb.get_table('VLAN')
    keys = data.keys()

    def tablelize(keys, data):
        table = []

        for k in natsorted(keys):
            if 'members' not in data[k] :
                r = []
                r.append(k)
                r.append(data[k]['vlanid'])
                table.append(r)
                continue

            for m in data[k].get('members', []):
                r = []
                r.append(k)
                r.append(data[k]['vlanid'])
                if clicommon.get_interface_naming_mode() == "alias":
                    alias = iface_alias_converter.name_to_alias(m)
                    r.append(alias)
                else:
                    r.append(m)

                entry = db.cfgdb.get_entry('VLAN_MEMBER', (k, m))
                mode = entry.get('tagging_mode')
                if mode is None:
                    r.append('?')
                else:
                    r.append(mode)

                table.append(r)

        return table

    header = ['Name', 'VID', 'Member', 'Mode']
    click.echo(tabulate(tablelize(keys, data), header))
