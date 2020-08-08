import click
from natsort import natsorted
from tabulate import tabulate

from utilities_common.cli import AbbreviationGroup, pass_db

#
# 'feature' group (show feature ...)
#
@click.group(cls=AbbreviationGroup, name='feature', invoke_without_command=False)
def feature():
    """Show feature status"""
    pass

#
# 'status' subcommand (show feature status)
#
@feature.command('status', short_help="Show feature state")
@click.argument('feature_name', required=False)
@pass_db
def feature_status(db, feature_name):
    header = ['Feature', 'State', 'AutoRestart']
    body = []
    feature_table = db.cfgdb.get_table('FEATURE')
    if feature_name:
        if feature_table and feature_table.has_key(feature_name):
            body.append([feature_name, feature_table[feature_name]['state'], \
                         feature_table[feature_name]['auto_restart']])
        else:
            click.echo("Can not find feature {}".format(feature_name))
            sys.exit(1)
    else:
        for key in natsorted(feature_table.keys()):
            body.append([key, feature_table[key]['state'], feature_table[key]['auto_restart']])
    click.echo(tabulate(body, header))

#
# 'autorestart' subcommand (show feature autorestart)
#
@feature.command('autorestart', short_help="Show auto-restart state for a feature")
@click.argument('feature_name', required=False)
@pass_db
def feature_autorestart(db, feature_name):
    header = ['Feature', 'AutoRestart']
    body = []
    feature_table = db.cfgdb.get_table('FEATURE')
    if feature_name:
        if feature_table and feature_table.has_key(feature_name):
            body.append([feature_name, feature_table[feature_name]['auto_restart']])
        else:
            click.echo("Can not find feature {}".format(feature_name))
            sys.exit(1)
    else:
        for name in natsorted(feature_table.keys()):
            body.append([name, feature_table[name]['auto_restart']])
    click.echo(tabulate(body, header))
