#! /usr/bin/python -u

import click
import errno
import os
import subprocess
import sys
from click_default_group import DefaultGroup

try:
    # noinspection PyPep8Naming
    import ConfigParser as configparser
except ImportError:
    # noinspection PyUnresolvedReferences
    import configparser


# This is from the aliases example:
# https://github.com/pallets/click/blob/57c6f09611fc47ca80db0bd010f05998b3c0aa95/examples/aliases/aliases.py
class Config(object):
    """Object to hold CLI config"""

    def __init__(self):
        self.path = os.getcwd()
        self.aliases = {}

    def read_config(self, filename):
        parser = configparser.RawConfigParser()
        parser.read([filename])
        try:
            self.aliases.update(parser.items('aliases'))
        except configparser.NoSectionError:
            pass


# Global Config object
_config = None


# This aliased group has been modified from click examples to inherit from DefaultGroup instead of click.Group.
# DefaultGroup is a superclass of click.Group which calls a default subcommand instead of showing
# a help message if no subcommand is passed
class AliasedGroup(DefaultGroup):
    """This subclass of a DefaultGroup supports looking up aliases in a config
    file and with a bit of magic.
    """

    def get_command(self, ctx, cmd_name):
        global _config

        # If we haven't instantiated our global config, do it now and load current config
        if _config is None:
            _config = Config()

            # Load our config file
            cfg_file = os.path.join(os.path.dirname(__file__), 'aliases.ini')
            _config.read_config(cfg_file)

        # Try to get builtin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # No builtin found. Look up an explicit command alias in the config
        if cmd_name in _config.aliases:
            actual_cmd = _config.aliases[cmd_name]
            return click.Group.get_command(self, ctx, actual_cmd)

        # Alternative option: if we did not find an explicit alias we
        # allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        matches = [x for x in self.list_commands(ctx)
                   if x.lower().startswith(cmd_name.lower())]
        if not matches:
            # No command name matched. Issue Default command.
            ctx.arg0 = cmd_name
            cmd_name = self.default_cmd_name
            return DefaultGroup.get_command(self, ctx, cmd_name)
        elif len(matches) == 1:
            return DefaultGroup.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))

def run_command(command, display_cmd=False):
    if display_cmd:
        click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

    while True:
        output = proc.stdout.readline()
        if output == "" and proc.poll() is not None:
            break
        if output:
            try:
                click.echo(output.rstrip('\n'))
            except IOError as e:
                # In our version of Click (v6.6), click.echo() and click.echo_via_pager() do not properly handle
                # SIGPIPE, and if a pipe is broken before all output is processed (e.g., pipe output to 'head'),
                # it will result in a stack trace. This is apparently fixed upstream, but for now, we silently
                # ignore SIGPIPE here.
                if e.errno == errno.EPIPE:
                    sys.exit(0)
                else:
                    raise

    rc = proc.poll()
    if rc != 0:
        sys.exit(rc)

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

#
# 'connect' group (root group)
#

# This is our entrypoint - the main "connect" command
@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
def connect():
    """SONiC command line - 'connect' command"""
    pass

#
# 'line' command ("connect line")
#
@connect.command('line')
@click.argument('linenum')
def line(linenum):
    """Connect to line via serial connection"""
    # TODO: Stub
    return

if __name__ == '__main__':
    connect()
