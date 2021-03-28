import json
import os
import sys

import click
from tabulate import tabulate
from swsscommon.swsscommon import SonicV2Connector
import utilities_common.cli as clicommon


PREVIOUS_REBOOT_CAUSE_FILE_PATH = "/host/reboot-cause/previous-reboot-cause.json"


def read_reboot_cause_file():
    reboot_cause_dict = {}

    if os.path.exists(PREVIOUS_REBOOT_CAUSE_FILE_PATH):
        with open(PREVIOUS_REBOOT_CAUSE_FILE_PATH) as prev_reboot_cause_file:
            try:
                reboot_cause_dict = json.load(prev_reboot_cause_file)
            except json.JSONDecodeError as err:
                click.echo("Failed to load JSON file '{}'!".format(PREVIOUS_REBOOT_CAUSE_FILE_PATH), err=True)

    return reboot_cause_dict


#
# 'reboot-cause' group ("show reboot-cause")
#
@click.group(cls=clicommon.AliasedGroup, invoke_without_command=True)
@click.pass_context
def reboot_cause(ctx):
    """Show cause of most recent reboot"""
    if ctx.invoked_subcommand is None:
        reboot_cause_str = ""

        # Read the previous reboot cause
        reboot_cause_dict = read_reboot_cause_file()

        reboot_cause = reboot_cause_dict.get("cause", "Unknown")
        reboot_user = reboot_cause_dict.get("user", "N/A")
        reboot_time = reboot_cause_dict.get("time", "N/A")

        if reboot_user != "N/A":
            reboot_cause_str = "User issued '{}' command".format(reboot_cause)
        else:
            reboot_cause_str = reboot_cause

        if reboot_user != "N/A" or reboot_time != "N/A":
            reboot_cause_str += " ["

            if reboot_user != "N/A":
                reboot_cause_str += "User: {}".format(reboot_user)
                if reboot_time != "N/A":
                    reboot_cause_str += ", "

            if reboot_time != "N/A":
                reboot_cause_str += "Time: {}".format(reboot_time)

            reboot_cause_str += "]"

        click.echo(reboot_cause_str)


# 'history' subcommand ("show reboot-cause history")
@reboot_cause.command()
def history():
    """Show history of reboot-cause"""
    REBOOT_CAUSE_TABLE_NAME = "REBOOT_CAUSE"
    TABLE_NAME_SEPARATOR = '|'
    db = SonicV2Connector(host='127.0.0.1')
    db.connect(db.STATE_DB, False)   # Make one attempt only
    prefix = REBOOT_CAUSE_TABLE_NAME + TABLE_NAME_SEPARATOR
    _hash = '{}{}'.format(prefix, '*')
    table_keys = db.keys(db.STATE_DB, _hash)
    if table_keys is not None:
        table_keys.sort(reverse=True)

        table = []
        for tk in table_keys:
            entry = db.get_all(db.STATE_DB, tk)
            r = []
            r.append(tk.replace(prefix, ""))
            r.append(entry['cause'] if 'cause' in entry else "")
            r.append(entry['time'] if 'time' in entry else "")
            r.append(entry['user'] if 'user' in entry else "")
            r.append(entry['comment'] if 'comment' in entry else "")
            table.append(r)

        header = ['Name', 'Cause', 'Time', 'User', 'Comment']
        click.echo(tabulate(table, header, numalign="left"))
    else:
        click.echo("Reboot-cause history is not yet available in StateDB")
        sys.exit(1)
