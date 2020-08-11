#!/usr/bin/env python

import click
import swsssdk
from tabulate import tabulate

class Crm:
    def __init__(self):
        self.cli_mode = None
        self.addr_family = None
        self.res_type = None

    def config(self, attr, val):
        """
        CRM handler for 'config' CLI commands.
        """
        configdb = swsssdk.ConfigDBConnector()
        configdb.connect()

        configdb.mod_entry("CRM", 'Config', {attr: val})

    def show_summary(self):
        """
        CRM Handler to display general information.
        """
        configdb = swsssdk.ConfigDBConnector()
        configdb.connect()

        crm_info = configdb.get_entry('CRM', 'Config')

        if crm_info:
            click.echo('\nPolling Interval: ' + crm_info['polling_interval'] + ' second(s)\n')
        else:
            click.echo('\nError! Could not get CRM configuration.\n')

    def show_thresholds(self, resource):
        """
        CRM Handler to display thresholds information.
        """
        configdb = swsssdk.ConfigDBConnector()
        configdb.connect()

        crm_info = configdb.get_entry('CRM', 'Config')

        header = ("Resource Name", "Threshold Type", "Low Threshold", "High Threshold")
        data = []

        if crm_info:
            if resource == 'all':
                for res in ["ipv4_route", "ipv6_route", "ipv4_nexthop", "ipv6_nexthop", "ipv4_neighbor", "ipv6_neighbor",
                            "nexthop_group_member", "nexthop_group", "acl_table", "acl_group", "acl_entry",
                            "acl_counter", "fdb_entry"]:
                    data.append([res, crm_info[res + "_threshold_type"], crm_info[res + "_low_threshold"], crm_info[res + "_high_threshold"]])
            else:
                data.append([resource, crm_info[resource + "_threshold_type"], crm_info[resource + "_low_threshold"], crm_info[resource + "_high_threshold"]])
        else:
            click.echo('\nError! Could not get CRM configuration.')

        click.echo()
        click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
        click.echo()

    def show_resources(self, resource):
        """
        CRM Handler to display resources information.
        """
        countersdb = swsssdk.SonicV2Connector(host='127.0.0.1')
        countersdb.connect(countersdb.COUNTERS_DB)

        crm_stats = countersdb.get_all(countersdb.COUNTERS_DB, 'CRM:STATS')

        header = ("Resource Name", "Used Count", "Available Count")
        data = []

        if crm_stats:
            if resource == 'all':
                for res in ["ipv4_route", "ipv6_route", "ipv4_nexthop", "ipv6_nexthop", "ipv4_neighbor", "ipv6_neighbor",
                            "nexthop_group_member", "nexthop_group", "fdb_entry"]:
                    data.append([res, crm_stats['crm_stats_' + res + "_used"], crm_stats['crm_stats_' + res + "_available"]])
            else:
                data.append([resource, crm_stats['crm_stats_' + resource + "_used"], crm_stats['crm_stats_' + resource + "_available"]])
        else:
            click.echo('\nCRM counters are not ready. They would be populated after the polling interval.')

        click.echo()
        click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
        click.echo()

    def show_acl_resources(self):
        """
        CRM Handler to display ACL recources information.
        """
        countersdb = swsssdk.SonicV2Connector(host='127.0.0.1')
        countersdb.connect(countersdb.COUNTERS_DB)

        header = ("Stage", "Bind Point", "Resource Name", "Used Count", "Available Count")
        data = []

        for stage in ["INGRESS", "EGRESS"]:
            for bind_point in ["PORT", "LAG", "VLAN", "RIF", "SWITCH"]:
                crm_stats = countersdb.get_all(countersdb.COUNTERS_DB, 'CRM:ACL_STATS:{0}:{1}'.format(stage, bind_point))

                if crm_stats:
                    for res in ["acl_group", "acl_table"]:
                        data.append([
                                        stage, bind_point, res,
                                        crm_stats['crm_stats_' + res + "_used"],
                                        crm_stats['crm_stats_' + res + "_available"]
                                    ])

        click.echo()
        click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
        click.echo()

    def show_acl_table_resources(self):
        """
        CRM Handler to display ACL table information.
        """
        countersdb = swsssdk.SonicV2Connector(host='127.0.0.1')
        countersdb.connect(countersdb.COUNTERS_DB)

        header = ("Table ID", "Resource Name", "Used Count", "Available Count")

        # Retrieve all ACL table keys from CRM:ACL_TABLE_STATS
        crm_acl_keys = countersdb.keys(countersdb.COUNTERS_DB, 'CRM:ACL_TABLE_STATS*')

        for key in crm_acl_keys or [None]:
            data = []

            if key:
                id = key.replace('CRM:ACL_TABLE_STATS:', '')

                crm_stats = countersdb.get_all(countersdb.COUNTERS_DB, key)

                for res in ['acl_entry', 'acl_counter']:
                    if ('crm_stats_' + res + '_used' in crm_stats) and ('crm_stats_' + res + '_available' in crm_stats):
                        data.append([id, res, crm_stats['crm_stats_' + res + '_used'], crm_stats['crm_stats_' + res + '_available']])

            click.echo()
            click.echo(tabulate(data, headers=header, tablefmt="simple", missingval=""))
            click.echo()


@click.group()
@click.pass_context
def cli(ctx):
    """
    Utility entry point.
    """
    context = {
        "crm": Crm()
    }

    ctx.obj = context

@cli.group()
@click.pass_context
def config(ctx):
    """CRM related configuration"""
    pass

@config.group()
@click.pass_context
def polling(ctx):
    """CRM polling configuration"""
    pass

@polling.command()
@click.pass_context
@click.argument('interval', type=click.INT)
def interval(ctx, interval):
    """CRM polling interval configuration"""
    ctx.obj["crm"].config('polling_interval', interval)

@config.group()
@click.pass_context
def thresholds(ctx):
    """CRM thresholds configuration"""
    pass

@thresholds.group()
@click.pass_context
def ipv4(ctx):
    """CRM resource IPv4 address-family"""
    ctx.obj["crm"].addr_family = 'ipv4'

@thresholds.group()
@click.pass_context
def ipv6(ctx):
    """CRM resource IPv6 address-family"""
    ctx.obj["crm"].addr_family = 'ipv6'

@ipv4.group()
@click.pass_context
def route(ctx):
    """CRM configuration for route resource"""
    ctx.obj["crm"].res_type = 'route'

@ipv4.group()
@click.pass_context
def neighbor(ctx):
    """CRM configuration for neigbor resource"""
    ctx.obj["crm"].res_type = 'neighbor'

@ipv4.group()
@click.pass_context
def nexthop(ctx):
    """CRM configuration for nexthop resource"""
    ctx.obj["crm"].res_type = 'nexthop'

@route.command()
@click.argument('value', type=click.Choice(['percentage', 'used', 'free']))
@click.pass_context
def type(ctx, value):
    """CRM threshod type configuration"""
    attr = ''

    if ctx.obj["crm"].addr_family != None:
        attr += ctx.obj["crm"].addr_family + '_'

    attr += ctx.obj["crm"].res_type + '_' + 'threshold_type'

    ctx.obj["crm"].config(attr, value)

@route.command()
@click.argument('value', type=click.INT)
@click.pass_context
def low(ctx, value):
    """CRM low threshod configuration"""
    attr = ''

    if ctx.obj["crm"].addr_family != None:
        attr += ctx.obj["crm"].addr_family + '_'

    attr += ctx.obj["crm"].res_type + '_' + 'low_threshold'

    ctx.obj["crm"].config(attr, value)

@route.command()
@click.argument('value', type=click.INT)
@click.pass_context
def high(ctx, value):
    """CRM high threshod configuration"""
    attr = ''

    if ctx.obj["crm"].addr_family != None:
        attr += ctx.obj["crm"].addr_family + '_'

    attr += ctx.obj["crm"].res_type + '_' + 'high_threshold'

    ctx.obj["crm"].config(attr, value)

neighbor.add_command(type)
neighbor.add_command(low)
neighbor.add_command(high)
nexthop.add_command(type)
nexthop.add_command(low)
nexthop.add_command(high)
ipv6.add_command(route)
ipv6.add_command(neighbor)
ipv6.add_command(nexthop)

@thresholds.group()
@click.pass_context
def nexthop(ctx):
    """CRM configuration for nexthop resource"""
    pass
@nexthop.group()
@click.pass_context
def group(ctx):
    """CRM configuration for nexthop group resource"""
    pass
@group.group()
@click.pass_context
def member(ctx):
    """CRM configuration for nexthop group member resource"""
    ctx.obj["crm"].res_type = 'nexthop_group_member'
@group.group()
@click.pass_context
def object(ctx):
    """CRM configuration for nexthop group resource"""
    ctx.obj["crm"].res_type = 'nexthop_group'

member.add_command(type)
member.add_command(low)
member.add_command(high)
object.add_command(type)
object.add_command(low)
object.add_command(high)

@thresholds.group()
@click.pass_context
def fdb(ctx):
    """CRM configuration for FDB resource"""
    ctx.obj["crm"].res_type = 'fdb_entry'

fdb.add_command(type)
fdb.add_command(low)
fdb.add_command(high)

@thresholds.group()
@click.pass_context
def acl(ctx):
    """CRM configuration for ACL resource"""
    pass

@acl.group()
@click.pass_context
def table(ctx):
    """CRM configuration for ACL table resource"""
    ctx.obj["crm"].res_type = 'acl_table'

table.add_command(type)
table.add_command(low)
table.add_command(high)

@acl.group()
@click.pass_context
def group(ctx):
    """CRM configuration for ACL group resource"""
    ctx.obj["crm"].res_type = 'acl_group'

group.add_command(type)
group.add_command(low)
group.add_command(high)

@group.group()
@click.pass_context
def entry(ctx):
    """CRM configuration for ACL entry resource"""
    ctx.obj["crm"].res_type = 'acl_entry'

entry.add_command(type)
entry.add_command(low)
entry.add_command(high)

@group.group()
@click.pass_context
def counter(ctx):
    """CRM configuration for ACL counter resource"""
    ctx.obj["crm"].res_type = 'acl_counter'

counter.add_command(type)
counter.add_command(low)
counter.add_command(high)

@cli.group()
@click.pass_context
def show(ctx):
    """Show CRM related information"""
    pass

@show.command()
@click.pass_context
def summary(ctx):
    """Show CRM general information"""
    ctx.obj["crm"].show_summary()

@show.group()
@click.pass_context
def resources(ctx):
    """Show CRM resources information"""
    ctx.obj["crm"].cli_mode = 'resources'

@show.group()
@click.pass_context
def thresholds(ctx):
    """Show CRM thresholds information"""
    ctx.obj["crm"].cli_mode = 'thresholds'

@resources.command()
@click.pass_context
def all(ctx):
    """Show CRM information for all resources"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('all')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('all')
        ctx.obj["crm"].show_acl_resources()
        ctx.obj["crm"].show_acl_table_resources()

@resources.group()
@click.pass_context
def ipv4(ctx):
    """CRM resource IPv4 address family"""
    ctx.obj["crm"].addr_family = 'ipv4'

@resources.group()
@click.pass_context
def ipv6(ctx):
    """CRM resource IPv6 address family"""
    ctx.obj["crm"].addr_family = 'ipv6'

@ipv4.command()
@click.pass_context
def route(ctx):
    """Show CRM information for route resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('{0}_route'.format(ctx.obj["crm"].addr_family))
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('{0}_route'.format(ctx.obj["crm"].addr_family))

@ipv4.command()
@click.pass_context
def neighbor(ctx):
    """Show CRM information for neighbor resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('{0}_neighbor'.format(ctx.obj["crm"].addr_family))
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('{0}_neighbor'.format(ctx.obj["crm"].addr_family))

@ipv4.command()
@click.pass_context
def nexthop(ctx):
    """Show CRM information for nexthop resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('{0}_nexthop'.format(ctx.obj["crm"].addr_family))
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('{0}_nexthop'.format(ctx.obj["crm"].addr_family))

ipv6.add_command(route)
ipv6.add_command(neighbor)
ipv6.add_command(nexthop)

@resources.group()
@click.pass_context
def nexthop(ctx):
    """Show CRM information for nexthop resource"""
    pass

@nexthop.group()
@click.pass_context
def group(ctx):
    """Show CRM information for nexthop group resource"""
    pass

@group.command()
@click.pass_context
def member(ctx):
    """Show CRM information for nexthop group member resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('nexthop_group_member')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('nexthop_group_member')

@group.command()
@click.pass_context
def object(ctx):
    """Show CRM information for nexthop group resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('nexthop_group')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('nexthop_group')

@resources.group()
@click.pass_context
def acl(ctx):
    """Show CRM information for acl resource"""
    pass

@acl.command()
@click.pass_context
def table(ctx):
    """Show CRM information for acl table resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('acl_table')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_acl_table_resources()

@acl.command()
@click.pass_context
def group(ctx):
    """Show CRM information for acl group resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('acl_group')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_acl_resources()

@resources.command()
@click.pass_context
def fdb(ctx):
    """Show CRM information for fdb resource"""
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds('fdb_entry')
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources('fdb_entry')

thresholds.add_command(acl)
thresholds.add_command(all)
thresholds.add_command(fdb)
thresholds.add_command(ipv4)
thresholds.add_command(ipv6)
thresholds.add_command(nexthop)


if __name__ == '__main__':
    cli()
