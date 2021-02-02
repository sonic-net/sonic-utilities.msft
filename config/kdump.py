import os
import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import ConfigDBConnector

@click.group(cls=clicommon.AbbreviationGroup, name="kdump")
def kdump():
    """ Configure kdump """
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

@kdump.command()
def disable():
    """Disable kdump operation"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"enabled": "false"})

@kdump.command()
def enable():
    """Enable kdump operation"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"enabled": "true"})

@kdump.command()
@click.argument('kdump_memory', metavar='<kdump_memory>', required=True)
def memory(kdump_memory):
    """Set memory allocated for kdump capture kernel"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"memory": kdump_memory})

@kdump.command('num-dumps')
@click.argument('kdump_num_dumps', metavar='<kdump_num_dumps>', required=True, type=int)
def num_dumps(kdump_num_dumps):
    """Set max number of dump files for kdump"""
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        config_db.mod_entry("KDUMP", "config", {"num_dumps": kdump_num_dumps})
