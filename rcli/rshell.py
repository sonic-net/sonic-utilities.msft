import os
import click
import paramiko
import sys

from .linecard import Linecard
from sonic_py_common import device_info
from rcli import utils as rcli_utils


@click.command()
@click.argument('linecard_name', type=str, autocompletion=rcli_utils.get_all_linecards)
def cli(linecard_name):
    """
    Open interactive shell for one linecard
    
    :param linecard_name: The name of the linecard to connect to
    """
    if not device_info.is_chassis():
        click.echo("This commmand is only supported Chassis")
        sys.exit(1)

    username = os.getlogin()
    password = rcli_utils.get_password(username)
    
    try:
        lc =Linecard(linecard_name, username, password)
        if lc.connection:
            click.echo("Connecting to {}".format(lc.linecard_name))
            # If connection was created, connection exists. Otherwise, user will see an error message.
            lc.start_shell()
            click.echo("Connection Closed")
    except paramiko.ssh_exception.AuthenticationException:
        click.echo("Login failed on '{}' with username '{}'".format(linecard_name, lc.username))


if __name__=="__main__":
    cli(prog_name='rshell')
