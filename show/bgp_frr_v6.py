import click

import utilities_common.cli as clicommon
from show.main import ipv6, run_command
import utilities_common.multi_asic as multi_asic_util
import utilities_common.bgp_util as bgp_util
import utilities_common.constants as constants

###############################################################################
#
# 'show ipv6 bgp' cli stanza
#
###############################################################################


@ipv6.group(cls=clicommon.AliasedGroup)
def bgp():
    """Show IPv6 BGP (Border Gateway Protocol) information"""
    pass


# 'summary' subcommand ("show ipv6 bgp summary")
@bgp.command()
@multi_asic_util.multi_asic_click_options
def summary(namespace, display):
    """Show summarized information of IPv6 BGP state"""
    bgp_summary = bgp_util.get_bgp_summary_from_all_bgp_instances(constants.IPV6, namespace,display)
    bgp_util.display_bgp_summary(bgp_summary=bgp_summary, af=constants.IPV6)


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
