import click

import tabulate
from natsort import natsorted

import utilities_common.cli as clicommon


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
@clicommon.pass_db
def syslog(db):
    """ Show syslog server configuration """

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
