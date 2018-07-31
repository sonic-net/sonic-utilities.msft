#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with switches over serial via console device
#

try:
    import click
    import re
    import subprocess
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

@click.group()
def consutil():
    """consutil - Command-line utility for interacting with switchs via console device"""

    if os.geteuid() != 0:
        print "Root privileges are required for this operation"
        sys.exit(1)

# 'show' subcommand
@consutil.command()
def line():
    """Show all /dev/ttyUSB lines"""
    click.echo("show line")

# 'clear' subcommand
@consutil.command()
@click.argument('linenum')
def clear(linenum):
    """Clear preexisting connection to line"""
    checkDevice(linenum)
    linenum = str(linenum)

    busyDevices = getBusyDevices()
    if linenum in busyDevices:
        pid, _ = busyDevices[linenum]
        cmd = "sudo kill -SIGTERM " + pid
        click.echo("Sending SIGTERM to process " + pid)
        run_command(cmd)
    else:
        click.echo("No process is connected to line " + linenum)

# 'connect' subcommand
@consutil.command()
@click.argument('linenum')
def connect(linenum):
    """Connect to switch via console device"""
    click.echo("connect linenum")

if __name__ == '__main__':
    consutil()
