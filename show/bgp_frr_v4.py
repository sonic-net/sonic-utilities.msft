import click
from show.main import *


###############################################################################
#
# 'show bgp' cli stanza
#
###############################################################################


@cli.group(cls=AliasedGroup, default_if_no_args=False)
def bgp():
    """Show IPv4 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv4 BGP state"""
    run_command('sudo vtysh -c "show bgp summary"')


# 'neighbors' subgroup ("show bgp neighbors ...")
@bgp.group(cls=AliasedGroup, default_if_no_args=True)
def neighbors():
    """Show BGP neighbors"""
    pass


# 'neighbors' subcommand ("show bgp neighbors")
@neighbors.command(default=True)
@click.argument('ipaddress', required=False)
def default(ipaddress):
    """Show BGP neighbors"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "show bgp neighbor {} "'.format(ipaddress)
        run_command(command)
    else:
        run_command('sudo vtysh -c "show bgp neighbor"')


# 'advertised-routes' subcommand ("show bgp neighbors advertised-routes <nbr>")
@neighbors.command('advertised-routes')
@click.argument('ipaddress')
def advertised_routes(ipaddress):
    """Display routes advertised to a BGP peer"""

    command = 'sudo vtysh -c "show bgp ipv4 neighbor {} advertised-routes"'. \
        format(ipaddress)
    run_command(command)


# 'routes' subcommand ("show bgp neighbors routes <nbr>")
@neighbors.command('routes')
@click.argument('ipaddress')
def routes(ipaddress):
    """Display routes learned from neighbor"""

    command = 'sudo vtysh -c "show bgp ipv4 neighbor {} routes"'. \
        format(ipaddress)
    run_command(command)


###############################################################################
#
# 'show bgp ipv4' cli stanza
#
###############################################################################


@bgp.group(cls=AliasedGroup, default_if_no_args=False)
def ipv4():
    """Show BGP ipv4 commands"""
    pass


# 'summary' subcommand ("show bgp ipv4 summary")
@ipv4.command()
def summary():
    """Show summarized information of IPv4 BGP state"""
    run_command('sudo vtysh -c "show bgp ipv4 summary"')


# 'neighbors' subgroup ("show bgp ipv4 neighbors ...")
@ipv4.group(cls=AliasedGroup, default_if_no_args=True)
def neighbors():
    """Show BGP IPv4 neighbors"""
    pass


# 'neighbors' subcommand ("show bgp ipv4 neighbors")
@neighbors.command(default=True)
@click.argument('ipaddress', required=False)
def default(ipaddress):
    """Show BGP IPv4 neighbors"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "show bgp ipv4 neighbor {} "'. \
            format(ipaddress)
        run_command(command)
    else:
        run_command('sudo vtysh -c "show bgp ipv4 neighbor"')


# 'advertised-routes' subcommand ("show bgp ipv4 neighbors advertised-routes <nbr>")
@neighbors.command('advertised-routes')
@click.argument('ipaddress')
def advertised_routes(ipaddress):
    """Display routes advertised to a BGP peer"""

    command = 'sudo vtysh -c "show bgp ipv4 neighbor {} advertised-routes"'. \
        format(ipaddress)
    run_command(command)


# 'routes' subcommand ("show bgp ipv4 neighbors routes <nbr>")
@neighbors.command('routes')
@click.argument('ipaddress')
def routes(ipaddress):
    """Display routes learned from neighbor"""

    command = 'sudo vtysh -c "show bgp ipv4 neighbor {} routes"'. \
        format(ipaddress)
    run_command(command)
