import click
from show.main import AliasedGroup, ipv6, run_command, get_bgp_summary_extended


###############################################################################
#
# 'show ipv6 bgp' cli stanza
#
###############################################################################


@ipv6.group(cls=AliasedGroup)
def bgp():
    """Show IPv6 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ipv6 bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv6 BGP state"""
    try:
        device_output = run_command('sudo vtysh -c "show ipv6 bgp summary"', return_cmd=True)
        get_bgp_summary_extended(device_output)
    except Exception:
        run_command('sudo vtysh -c "show ipv6 bgp summary"')


# 'neighbors' subcommand ("show ipv6 bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=True)
@click.argument('info_type', type=click.Choice(['routes', 'advertised-routes', 'received-routes']), required=True)
def neighbors(ipaddress, info_type):
    """Show IPv6 BGP neighbors"""
    command = 'sudo vtysh -c "show ipv6 bgp neighbor {} {}"'.format(ipaddress, info_type)
    run_command(command)
