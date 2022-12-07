import click

import tabulate
from natsort import natsorted

import utilities_common.cli as clicommon
from syslog_util import common as syslog_common


SYSLOG_TABLE = "SYSLOG_SERVER"

SYSLOG_SOURCE = "source"
SYSLOG_PORT = "port"
SYSLOG_VRF = "vrf"

#
# Syslog helpers ------------------------------------------------------------------------------------------------------
#

def format(header, body):
    return tabulate.tabulate(body, header, tablefmt="simple", numalign="left", stralign="left")

#
# Syslog CLI ----------------------------------------------------------------------------------------------------------
#

@click.group(
    name='syslog',
    cls=clicommon.AliasedGroup,
    invoke_without_command=True
)
@click.pass_context
@clicommon.pass_db
def syslog(db, ctx):
    """ Show syslog server configuration """

    if ctx.invoked_subcommand is not None:
        return

    header = [
        "SERVER IP",
        "SOURCE IP",
        "PORT",
        "VRF",
    ]
    body = []

    table = db.cfgdb.get_table(SYSLOG_TABLE)
    for key in natsorted(table):
        entry = table[key]
        row = [key] + [
            entry.get(SYSLOG_SOURCE, "N/A"),
            entry.get(SYSLOG_PORT, "N/A"),
            entry.get(SYSLOG_VRF, "N/A"),
        ]
        body.append(row)

    click.echo(format(header, body))

@syslog.command(
    name='rate-limit-host'
)
@clicommon.pass_db
def rate_limit_host(db):
    """ Show syslog rate limit configuration for host """

    header = [
        "INTERVAL",
        "BURST",
    ]
    body = []
    entry = db.cfgdb.get_entry(syslog_common.SYSLOG_CONFIG_TABLE, syslog_common.SYSLOG_CONFIG_GLOBAL_KEY)
    if entry:
        body.append([entry.get(syslog_common.SYSLOG_RATE_LIMIT_INTERVAL, 'N/A'),
                    entry.get(syslog_common.SYSLOG_RATE_LIMIT_BURST, 'N/A')])
    else:
        body.append('N/A', 'N/A')

    click.echo(format(header, body))


@syslog.command(
    name='rate-limit-container'
)
@click.argument('service_name', metavar='<service_name>', required=False)
@clicommon.pass_db
def rate_limit_container(db, service_name):
    """ Show syslog rate limit configuration for containers """

    header = [
        "SERVICE",
        "INTERVAL",
        "BURST",
    ]
    body = []
    features = db.cfgdb.get_table(syslog_common.FEATURE_TABLE)

    if service_name:
        syslog_common.service_validator(features, service_name)
        service_list = [service_name]
    else:
        service_list = [name for name, service_config in features.items() if service_config.get(syslog_common.SUPPORT_RATE_LIMIT, '').lower() == 'true']

    syslog_configs = db.cfgdb.get_table(syslog_common.SYSLOG_CONFIG_FEATURE_TABLE)
    for service in natsorted(service_list):
        if service in syslog_configs:
            entry = syslog_configs[service]
            body.append([service,
                        entry.get(syslog_common.SYSLOG_RATE_LIMIT_INTERVAL, 'N/A'),
                        entry.get(syslog_common.SYSLOG_RATE_LIMIT_BURST, 'N/A')])
        else:
            body.append([service, 'N/A', 'N/A'])

    click.echo(format(header, body))
