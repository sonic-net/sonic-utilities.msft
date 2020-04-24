import click
from show.main import ipv6, run_command, get_bgp_summary_extended


###############################################################################
#
# 'show ipv6 bgp' cli stanza
#
###############################################################################


@ipv6.group()
def bgp():
    """Show IPv6 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ipv6 bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv6 BGP state"""
    try:
        device_output = run_command('sudo vtysh -c "show bgp ipv6 summary"', return_cmd=True)
        get_bgp_summary_extended(device_output)
    except Exception:
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

# 'network' subcommand ("show ipv6 bgp network")
@bgp.command()
@click.argument('ipaddress', metavar='[<ipv6-address>|<ipv6-prefix>]', required=False)
@click.argument('info_type', metavar='[bestpath|json|longer-prefixes|multipath]',
                type=click.Choice(['bestpath', 'json', 'longer-prefixes', 'multipath']), required=False)
def network(ipaddress, info_type):
    """Show BGP ipv6 network"""

    command = 'sudo vtysh -c "show bgp ipv6'

    if ipaddress is not None:
        if '/' in ipaddress:
        # For network prefixes then this all info_type(s) are available
            pass
        else:
            # For an ipaddress then check info_type, exit if specified option doesn't work.
            if info_type in ['longer-prefixes']:
                click.echo('The parameter option: "{}" only available if passing a network prefix'.format(info_type))
                click.echo("EX: 'show ipv6 bgp network fc00:1::/64 longer-prefixes'")
                raise click.Abort()

        command += ' {}'.format(ipaddress)

        # info_type is only valid if prefix/ipaddress is specified
        if info_type is not None:
            command += ' {}'.format(info_type)

    command += '"'

    run_command(command)
