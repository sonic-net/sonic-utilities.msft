import click
from show.main import *


###############################################################################
#
# 'show bgp ipv6' cli stanza
#
###############################################################################


@bgp.group(cls=AliasedGroup, default_if_no_args=False)
def ipv6():
    """Show BGP ipv6 commands"""
    pass


# 'summary' subcommand ("show bgp ipv6 summary")
@ipv6.command()
def summary():
    """Show summarized information of IPv6 BGP state"""
    run_command('sudo vtysh -c "show bgp ipv6 summary"')


# 'neighbors' subgroup ("show bgp ipv6 neighbors ...")
@ipv6.group(cls=AliasedGroup, default_if_no_args=True)
def neighbors():
    """Show BGP IPv6 neighbors"""
    pass


# 'neighbors' subcommand ("show bgp ipv6 neighbors")
@neighbors.command(default=True)
@click.argument('ipaddress', required=False)
def default(ipaddress):
    """Show BGP IPv6 neighbors"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "show bgp ipv6 neighbor {} "'. \
            format(ipaddress)
        run_command(command)
    else:
        run_command('sudo vtysh -c "show bgp ipv6 neighbor"')


# 'advertised-routes' subcommand ("show bgp ipv6 neighbors advertised-routes <nbr>")
@neighbors.command('advertised-routes')
@click.argument('ipaddress')
def advertised_routes(ipaddress):
    """Display routes advertised to a BGP peer"""

    command = 'sudo vtysh -c "show bgp ipv6 neighbor {} advertised-routes"'. \
        format(ipaddress)
    run_command(command)


# 'routes' subcommand ("show bgp ipv6 neighbors routes <nbr>")
@neighbors.command('routes')
@click.argument('ipaddress')
def routes(ipaddress):
    """Display routes learned from neighbor"""

    command = 'sudo vtysh -c "show bgp ipv6 neighbor {} routes"'. \
        format(ipaddress)
    run_command(command)
