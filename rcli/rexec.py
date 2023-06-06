import os
import click
import paramiko
import sys

from .linecard import Linecard
from rcli import utils as rcli_utils
from sonic_py_common import device_info

@click.command()
@click.argument('linecard_names', nargs=-1, type=str, required=True)
@click.option('-c', '--command', type=str, required=True)
def cli(linecard_names, command):
    """
    Executes a command on one or many linecards
    
    :param linecard_names: A list of linecard names to execute the command on, 
        use `all` to execute on all linecards.
    :param command: The command to execute on the linecard(s)
    """
    if not device_info.is_chassis():
        click.echo("This commmand is only supported Chassis")
        sys.exit(1)
    
    username = os.getlogin()
    password = rcli_utils.get_password(username)
    
    if list(linecard_names) == ["all"]:
        # Get all linecard names using autocompletion helper
        linecard_names = rcli_utils.get_all_linecards(None, None, "")

    # Iterate through each linecard, execute command, and gather output
    for linecard_name in linecard_names:
        try:
            lc = Linecard(linecard_name, username, password)
            if lc.connection:
                # If connection was created, connection exists. Otherwise, user will see an error message.
                click.echo("======== {} output: ========".format(lc.linecard_name))
                click.echo(lc.execute_cmd(command))
        except paramiko.ssh_exception.AuthenticationException:
            click.echo("Login failed on '{}' with username '{}'".format(linecard_name, lc.username))

if __name__=="__main__":
    cli(prog_name='rexec')
