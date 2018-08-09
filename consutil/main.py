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
    import re
    import subprocess
    from tabulate import tabulate
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

@click.group()
def consutil():
    """consutil - Command-line utility for interacting with switches via console device"""

    if os.geteuid() != 0:
        print "Root privileges are required for this operation"
        sys.exit(1)

# 'show' subcommand
@consutil.command()
def show():
    """Show all /dev/ttyUSB lines and their info"""
    devices = getAllDevices()
    busyDevices = getBusyDevices()

    header = ["Line", "Actual/Configured Baud", "PID", "Start Time"]
    body = []
    for device in devices:
        lineNum = device[11:]
        busy = " "
        pid = ""
        date = ""
        if lineNum in busyDevices:
            pid, date = busyDevices[lineNum]
            busy = "*"
        actBaud, confBaud, _ = getConnectionInfo(lineNum)
        # repeated "~" will be replaced by spaces - hacky way to align the "/"s
        baud = "{}/{}{}".format(actBaud, confBaud, "~"*(15-len(confBaud)))
        body.append([busy+lineNum, baud, pid, date])
        
    # replace repeated "~" with spaces - hacky way to align the "/"s
    click.echo(tabulate(body, header, stralign="right").replace('~', ' ')) 

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
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True, help="connect by name - if flag is set, interpret linenum as device name instead")
def connect(target, devicename):
    """Connect to switch via console device - TARGET is line number or device name of switch"""
    lineNumber = getLineNumber(target, devicename)
    checkDevice(lineNumber)
    lineNumber = str(lineNumber)

    # build and start picocom command
    actBaud, _, flowBool = getConnectionInfo(lineNumber)
    flowCmd = "h" if flowBool else "n"
    quietCmd = "-q" if QUIET else ""
    cmd = "sudo picocom -b {} -f {} {} {}{}".format(actBaud, flowCmd, quietCmd, DEVICE_PREFIX, lineNumber)
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
