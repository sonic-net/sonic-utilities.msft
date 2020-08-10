import click

import utilities_common.cli as clicommon

from show.main import ip, run_command, get_bgp_summary_extended


###############################################################################
#
# 'show ip bgp' cli stanza
#
###############################################################################


@ip.group(cls=clicommon.AliasedGroup)
def bgp():
    """Show IPv4 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ip bgp summary")
@bgp.command()
def summary():
    """Show summarized information of IPv4 BGP state"""
    try:
        device_output = run_command('sudo vtysh -c "show ip bgp summary"', return_cmd=True)
        get_bgp_summary_extended(device_output)
    except Exception:
        run_command('sudo vtysh -c "show ip bgp summary"')


# 'neighbors' subcommand ("show ip bgp neighbors")
@bgp.command()
@click.argument('ipaddress', required=False)
@click.argument('info_type', type=click.Choice(['routes', 'advertised-routes', 'received-routes']), required=False)
def neighbors(ipaddress, info_type):
    """Show IP (IPv4) BGP neighbors"""

    command = 'sudo vtysh -c "show ip bgp neighbor'

    if ipaddress is not None:
        command += ' {}'.format(ipaddress)

        # info_type is only valid if ipaddress is specified
        if info_type is not None:
            command += ' {}'.format(info_type)

    command += '"'

    run_command(command)

# 'network' subcommand ("show ip bgp network")
@bgp.command()
@click.argument('ipaddress', metavar='[<ipv4-address>|<ipv4-prefix>]', required=False)
@click.argument('info_type', metavar='[bestpath|json|longer-prefixes|multipath]',
                type=click.Choice(['bestpath', 'json', 'longer-prefixes', 'multipath']), required=False)
def network(ipaddress, info_type):
    """Show IP (IPv4) BGP network"""

    command = 'sudo vtysh -c "show ip bgp'

    if ipaddress is not None:
        if '/' in ipaddress:
        # For network prefixes then this all info_type(s) are available
            pass
        else:
            # For an ipaddress then check info_type, exit if specified option doesn't work.
            if info_type in ['longer-prefixes']:
                click.echo('The parameter option: "{}" only available if passing a network prefix'.format(info_type))
                click.echo("EX: 'show ip bgp network 10.0.0.0/24 longer-prefixes'")
                raise click.Abort()

        command += ' {}'.format(ipaddress)

        # info_type is only valid if prefix/ipaddress is specified
        if info_type is not None:
            command += ' {}'.format(info_type)

    command += '"'

    run_command(command)
