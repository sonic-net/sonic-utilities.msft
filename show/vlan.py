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
    header = ['VLAN ID', 'IP Address', 'Ports', 'Port Tagging', 'DHCP Helper Address', 'Proxy ARP']
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
    vlan_proxy_arp_dict = {}

    # Parsing DHCP Helpers info
    for key in natsorted(list(vlan_dhcp_helper_data.keys())):
        try:
            if vlan_dhcp_helper_data[key]['dhcp_servers']:
                vlan_dhcp_helper_dict[key.strip('Vlan')] = vlan_dhcp_helper_data[key]['dhcp_servers']
        except KeyError:
            vlan_dhcp_helper_dict[key.strip('Vlan')] = " "

    # Parsing VLAN Gateway info
    for key in vlan_ip_data:
        if clicommon.is_ip_prefix_in_key(key):
            interface_key = key[0].strip("Vlan")
            interface_value = key[1]

            if interface_key in vlan_ip_dict:
                vlan_ip_dict[interface_key].append(interface_value)
            else:
                vlan_ip_dict[interface_key] = [interface_value]
        else:
            interface_key = key.strip("Vlan")
            if 'proxy_arp' in vlan_ip_data[key]:
                proxy_arp_status = vlan_ip_data[key]['proxy_arp'] 
            else:
                proxy_arp_status = "disabled"
            
            vlan_proxy_arp_dict[interface_key] = proxy_arp_status
            
            

    iface_alias_converter = clicommon.InterfaceAliasConverter(db)

    # Parsing VLAN Ports info
    for key in natsorted(list(vlan_ports_data.keys())):
        ports_key = key[0].strip("Vlan")
        ports_value = key[1]
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
    for key in natsorted(list(vlan_dhcp_helper_dict.keys())):
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
        vlan_proxy_arp = vlan_proxy_arp_dict.get(key, "disabled")
        body.append([key, ip_address, vlan_ports, vlan_tagging, dhcp_helpers, vlan_proxy_arp])
    click.echo(tabulate(body, header, tablefmt="grid"))

@vlan.command()
@clicommon.pass_db
def config(db):
    data = db.cfgdb.get_table('VLAN')
    keys = list(data.keys())
    member_data = db.cfgdb.get_table('VLAN_MEMBER')
    interface_naming_mode = clicommon.get_interface_naming_mode()
    iface_alias_converter = clicommon.InterfaceAliasConverter(db)
   
    def get_iface_name_for_display(member):
        name_for_display = member
        if interface_naming_mode == "alias" and member:
            name_for_display = iface_alias_converter.name_to_alias(member)
        return name_for_display
    
    def get_tagging_mode(vlan, member):
        if not member:
            return ''
        tagging_mode = db.cfgdb.get_entry('VLAN_MEMBER', (vlan, member)).get('tagging_mode')
        return '?' if tagging_mode is None else tagging_mode
        
    def tablelize(keys, data):
        table = []

        for k in natsorted(keys):
            members = set([(vlan, member) for vlan, member in member_data if vlan == k] + [(k, member) for member in set(data[k].get('members', []))])
            # vlan with no members
            if not members:
                members = [(k, '')]
            
            for vlan, member in natsorted(members):
                r = [vlan, data[vlan]['vlanid'], get_iface_name_for_display(member), get_tagging_mode(vlan, member)]
                table.append(r)

        return table

    header = ['Name', 'VID', 'Member', 'Mode']
    click.echo(tabulate(tablelize(keys, data), header))
