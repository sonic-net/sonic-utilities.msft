import click
from show.main import *


###############################################################################
#
# 'show ipv6 bgp' cli stanza
#
###############################################################################


@ipv6.group(cls=AliasedGroup, default_if_no_args=False)
def bgp():
    """Show IPv6 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ipv6 bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv6 BGP state"""
    run_command('sudo vtysh -c "show bgp ipv6 summary"')


# 'neighbors' subcommand ("show ipv6 bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=False)
@click.argument('info_type', type=click.Choice(['routes', 'advertised-routes', 'received-routes']), required=False)
def neighbors(ipaddress, info_type):
    """Show IPv6 BGP neighbors"""
    ipaddress = "" if ipaddress is None else ipaddress
    info_type = "" if info_type is None else info_type
    command = 'sudo vtysh -c "show bgp ipv6 neighbor {} {}"'.format(ipaddress, info_type)
    run_command(command)
