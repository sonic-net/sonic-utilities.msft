import click
from clear.main import *


###############################################################################
#
# 'clear bgp' cli stanza
#
###############################################################################


@cli.group(cls=AliasedGroup, default_if_no_args=True)
def bgp():
    """Clear BGP peers / state"""
    pass


# Default 'bgp' command (called if no subcommands or their aliases were passed)
@bgp.command(default=True)
def default():
    """Clear all BGP peers"""
    command = 'sudo vtysh -c "clear bgp *"'
    run_command(command)


@bgp.group(cls=AliasedGroup, default_if_no_args=True,
           context_settings=CONTEXT_SETTINGS)
def neighbor():
    """Clear specific BGP peers"""
    pass


@neighbor.command(default=True)
@click.argument('ipaddress', required=False)
def default(ipaddress):
    """Clear all BGP peers"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp {} "'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp *"'
    run_command(command)


# 'in' subcommand
@neighbor.command('in')
@click.argument('ipaddress', required=False)
def neigh_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp {} in"'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp * in"'
    run_command(command)


# 'out' subcommand
@neighbor.command('out')
@click.argument('ipaddress', required=False)
def neigh_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp {} out"'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp * out"'
    run_command(command)


@neighbor.group(cls=AliasedGroup, default_if_no_args=True,
                context_settings=CONTEXT_SETTINGS)
def soft():
    """Soft reconfig BGP's inbound/outbound updates"""
    pass


@soft.command(default=True)
@click.argument('ipaddress', required=False)
def default(ipaddress):
    """Clear BGP peers soft configuration"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp {} soft "'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp * soft"'
    run_command(command)


# 'soft in' subcommand
@soft.command('in')
@click.argument('ipaddress', required=False)
def soft_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp {} soft in"'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp * soft in"'
    run_command(command)


# 'soft out' subcommand
@soft.command('out')
@click.argument('ipaddress', required=False)
def soft_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp {} soft out"'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp * soft out"'
    run_command(command)


###############################################################################
#
# 'clear bgp ipv4' cli stanza
#
###############################################################################


@bgp.group(cls=AliasedGroup, default_if_no_args=True,
           context_settings=CONTEXT_SETTINGS)
def ipv4():
    """Clear BGP IPv4 peers / state"""
    pass


# Default 'bgp' command (called if no subcommands or their aliases were passed)
@ipv4.command(default=True)
def default():
    """Clear all IPv4 BGP peers"""
    command = 'sudo vtysh -c "clear bgp ipv4 *"'
    run_command(command)


@ipv4.group(cls=AliasedGroup, default_if_no_args=True,
            context_settings=CONTEXT_SETTINGS)
def neighbor():
    """Clear specific IPv4 BGP peers"""
    pass


@neighbor.command(default=True)
@click.argument('ipaddress', required=False)
def default(ipaddress):
    """Clear all IPv4 BGP peers"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp ipv4 {} "'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp ipv4 *"'
    run_command(command)


# 'in' subcommand
@neighbor.command('in')
@click.argument('ipaddress', required=False)
def neigh_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp ipv4 {} in"'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp ipv4 * in"'
    run_command(command)


# 'out' subcommand
@neighbor.command('out')
@click.argument('ipaddress', required=False)
def neigh_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp ipv4 {} out"'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp ipv4 * out"'
    run_command(command)


@neighbor.group(cls=AliasedGroup, default_if_no_args=True,
                context_settings=CONTEXT_SETTINGS)
def soft():
    """Soft reconfig BGP's inbound/outbound updates"""
    pass


@soft.command(default=True)
@click.argument('ipaddress', required=False)
def default(ipaddress):
    """Clear BGP neighbors soft configuration"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp ipv4 {} soft "'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp ipv4 * soft"'
    run_command(command)


# 'soft in' subcommand
@soft.command('in')
@click.argument('ipaddress', required=False)
def soft_in(ipaddress):
    """Send route-refresh"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp ipv4 {} soft in"'.format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp ipv4 * soft in"'
    run_command(command)


# 'soft out' subcommand
@soft.command('out')
@click.argument('ipaddress', required=False)
def soft_out(ipaddress):
    """Resend all outbound updates"""

    if ipaddress is not None:
        command = 'sudo vtysh -c "clear bgp ipv4 {} soft out"'.\
                  format(ipaddress)
    else:
        command = 'sudo vtysh -c "clear bgp ipv4 * soft out"'
    run_command(command)
