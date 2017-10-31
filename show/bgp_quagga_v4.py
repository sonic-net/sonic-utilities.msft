import click
from show.main import *


###############################################################################
#
# 'show ip bgp' cli stanza
#
###############################################################################


@ip.group(cls=AliasedGroup, default_if_no_args=False)
def bgp():
    """Show IPv4 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ip bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv4 BGP state"""
    run_command('sudo vtysh -c "show ip bgp summary"')


# 'neighbors' subcommand ("show ip bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=False)
def neighbors(ipaddress):
    """Show IP (IPv4) BGP neighbors"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "show ip bgp neighbor {} "'.format(ipaddress)
        run_command(command)
    else:
        run_command('sudo vtysh -c "show ip bgp neighbor"')
