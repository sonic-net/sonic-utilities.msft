import click
import utilities_common.cli as clicommon
from swsscommon.swsscommon import ConfigDBConnector

#
# 'kdump command ("show kdump ...")
#
@click.group(cls=clicommon.AliasedGroup, name="kdump")
def kdump():
    """Show kdump configuration, status and information """
    pass

@kdump.command('enabled')
def enabled():
    """Show if kdump is enabled or disabled"""
    kdump_is_enabled = False
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        table_data = config_db.get_table('KDUMP')
        if table_data is not None:
            config_data = table_data.get('config')
            if config_data is not None:
                if config_data.get('enabled').lower() == 'true':
                    kdump_is_enabled = True
    if kdump_is_enabled:
        click.echo("kdump is enabled")
    else:
        click.echo("kdump is disabled")

@kdump.command('status')
def status():
    """Show kdump status"""
    clicommon.run_command("sonic-kdump-config --status")
    clicommon.run_command("sonic-kdump-config --memory")
    clicommon.run_command("sonic-kdump-config --num_dumps")
    clicommon.run_command("sonic-kdump-config --files")

@kdump.command('memory')
def memory():
    """Show kdump memory information"""
    kdump_memory = "0M-2G:256M,2G-4G:320M,4G-8G:384M,8G-:448M"
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        table_data = config_db.get_table('KDUMP')
        if table_data is not None:
            config_data = table_data.get('config')
            if config_data is not None:
                kdump_memory_from_db = config_data.get('memory')
                if kdump_memory_from_db is not None:
                    kdump_memory = kdump_memory_from_db
    click.echo("Memory Reserved: {}".format(kdump_memory))

@kdump.command('num_dumps')
def num_dumps():
    """Show kdump max number of dump files"""
    kdump_num_dumps = "3"
    config_db = ConfigDBConnector()
    if config_db is not None:
        config_db.connect()
        table_data = config_db.get_table('KDUMP')
        if table_data is not None:
            config_data = table_data.get('config')
            if config_data is not None:
                kdump_num_dumps_from_db = config_data.get('num_dumps')
                if kdump_num_dumps_from_db is not None:
                    kdump_num_dumps = kdump_num_dumps_from_db
    click.echo("Maximum number of Kernel Core files Stored: {}".format(kdump_num_dumps))

@kdump.command('files')
def files():
    """Show kdump kernel core dump files"""
    clicommon.run_command("sonic-kdump-config --files")

@kdump.command()
@click.argument('record', required=True)
@click.argument('lines', metavar='<lines>', required=False)
def log(record, lines):
    """Show kdump kernel core dump file kernel log"""
    cmd = "sonic-kdump-config --file {}".format(record)
    if lines is not None:
        cmd += " --lines {}".format(lines)

    clicommon.run_command(cmd)
