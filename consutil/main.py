#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with switches over serial via console device
#

try:
    import click
    import os
    import pexpect
    import sys
    from tabulate import tabulate
    from lib import *
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

@click.group()
def consutil():
    """consutil - Command-line utility for interacting with switches via console device"""

    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(ERR_CMD)

# 'show' subcommand
@consutil.command()
def show():
    """Show all lines and their info"""
    lines = getAllLines()
    busyLines = getBusyLines()

    # sort lines for table rendering
    lines.sort(key=lambda dev: int(dev[LINE_KEY]))

    # set table header style
    header = ["Line",  "Baud",   "PID",   "Start Time", "Device"]
    body = []
    for line in lines:
        # configured information
        lineNum = line[LINE_KEY]
        baud = '-' if BAUD_KEY not in line else line[BAUD_KEY]
        remoteDevice = '-' if DEVICE_KEY not in line else line[DEVICE_KEY]

        # runtime information
        busy = " "
        pid = ""
        date = ""
        if lineNum in busyLines:
            pid, date = busyLines[lineNum]
            busy = "*"
        body.append([busy+lineNum, baud, pid, date, remoteDevice])
    click.echo(tabulate(body, header, stralign='right')) 

# 'clear' subcommand
@consutil.command()
@click.argument('target')
def clear(target):
    """Clear preexisting connection to line"""
    targetLine = getLine(target)
    if not targetLine:
        click.echo("Target [{}] does not exist".format(linenum))
        sys.exit(ERR_DEV)
    lineNumber = targetLine[LINE_KEY]

    busyLines = getBusyLines()
    if lineNumber in busyLines:
        pid, _ = busyLines[lineNumber]
        cmd = "sudo kill -SIGTERM " + pid
        click.echo("Sending SIGTERM to process " + pid)
        run_command(cmd)
    else:
        click.echo("No process is connected to line " + lineNumber)

# 'connect' subcommand
@consutil.command()
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True, help="connect by name - if flag is set, interpret linenum as device name instead")
def connect(target, devicename):
    """Connect to switch via console device - TARGET is line number or device name of switch"""
    # identify the target line
    targetLine = getLine(target, devicename)
    if not targetLine:
        click.echo("Cannot connect: target [{}] does not exist".format(target))
        sys.exit(ERR_DEV)
    lineNumber = targetLine[LINE_KEY]

    # build and start picocom command
    if BAUD_KEY in targetLine:
        baud = targetLine[BAUD_KEY]
    else:
        click.echo("Cannot connect: line [{}] has no baud rate".format(lineNumber))
        sys.exit(ERR_CFG)
    flowBool = True if FLOW_KEY in targetLine and targetLine[FLOW_KEY] == "1" else False
    flowCmd = "h" if flowBool else "n"
    quietCmd = "-q" if QUIET else ""
    cmd = "sudo picocom -b {} -f {} {} {}{}".format(baud, flowCmd, quietCmd, DEVICE_PREFIX, lineNumber)
    proc = pexpect.spawn(cmd)
    proc.send("\n")

    if QUIET:
        readyMsg = DEV_READY_MSG
    else:
        readyMsg = "Terminal ready" # picocom ready message
    busyMsg = "Resource temporarily unavailable" # picocom busy message

    # interact with picocom or print error message, depending on pexpect output
    index = proc.expect([readyMsg, busyMsg, pexpect.EOF, pexpect.TIMEOUT], timeout=TIMEOUT_SEC)
    if index == 0: # terminal ready
        click.echo("Successful connection to line {}\nPress ^A ^X to disconnect".format(lineNumber))
        if QUIET:
            # prints picocom output up to and including readyMsg
            click.echo(proc.before + proc.match.group(0), nl=False) 
        proc.interact()
        if QUIET:
            click.echo("\nTerminating...")
    elif index == 1: # resource is busy
        click.echo("Cannot connect: line {} is busy".format(lineNumber))
    else: # process reached EOF or timed out
        click.echo("Cannot connect: unable to open picocom process")

if __name__ == '__main__':
    consutil()