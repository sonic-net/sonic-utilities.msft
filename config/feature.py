import click

from utilities_common.cli import AbbreviationGroup, pass_db

#
# 'feature' group ('config feature ...')
#
@click.group(cls=AbbreviationGroup, name='feature', invoke_without_command=False)
def feature():
    """Configure features"""
    pass

#
# 'state' command ('config feature state ...')
#
@feature.command('state', short_help="Enable/disable a feature")
@click.argument('name', metavar='<feature-name>', required=True)
@click.argument('state', metavar='<state>', required=True, type=click.Choice(["enabled", "disabled"]))
@pass_db
def feature_state(db, name, state):
    """Enable/disable a feature"""
    state_data = db.cfgdb.get_entry('FEATURE', name)

    if not state_data:
        click.echo("Feature '{}' doesn't exist".format(name))
        sys.exit(1)

    db.cfgdb.mod_entry('FEATURE', name, {'state': state})

#
# 'autorestart' command ('config feature autorestart ...')
#
@feature.command(name='autorestart', short_help="Enable/disable autosrestart of a feature")
@click.argument('name', metavar='<feature-name>', required=True)
@click.argument('autorestart', metavar='<autorestart>', required=True, type=click.Choice(["enabled", "disabled"]))
@pass_db
def feature_autorestart(db, name, autorestart):
    """Enable/disable autorestart of a feature"""
    feature_table = db.cfgdb.get_table('FEATURE')
    if not feature_table:
        click.echo("Unable to retrieve feature table from Config DB.")
        sys.exit(1)

    if not feature_table.has_key(name):
        click.echo("Unable to retrieve feature '{}'".format(name))
        sys.exit(1)

    db.cfgdb.mod_entry('FEATURE', name, {'auto_restart': autorestart})
