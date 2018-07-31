#!/usr/bin/env python
#
# lib.py
#
# Helper code for CLI for interacting with switches via console device
#

try:
    import click
    import re
    import subprocess
    import sys
except ImportError as e: 
    raise ImportError("%s - required module not found" % str(e))

DEVICE_PREFIX = "/dev/ttyUSB"

ERR_CMD = 1
ERR_DEV = 2

# runs command, exit if stderr is written to, returns stdout otherwise
# input: cmd (str), output: output of cmd (str)
def run_command(cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output = proc.stdout.read()
    error = proc.stderr.read()
    if error != "":
        click.echo("Command resulted in error: {}".format(error))
        sys.exit(ERR_CMD)
    return output

# exits if inputted line number does not correspond to a device
# input: linenum
def checkDevice(linenum):
    devices = getAllDevices()
    if DEVICE_PREFIX + str(linenum) not in devices:
        click.echo("Line number {} does not exist".format(linenum))
        sys.exit(ERR_DEV)

# returns a sorted list of all devices (whose name matches DEVICE_PREFIX)
def getAllDevices():
    cmd = "ls " + DEVICE_PREFIX + "*"
    output = run_command(cmd)
    
    devices = output.split('\n')
    devices = list(filter(lambda dev: re.match(DEVICE_PREFIX + r"\d+", dev) != None, devices))
    devices.sort(key=lambda dev: int(dev[len(DEVICE_PREFIX):]))
    
    return devices

# returns a dictionary of busy devices and their info
#     maps line number to (pid, process start time)
def getBusyDevices():
    cmd = 'ps -eo pid,lstart,cmd | grep -E "(mini|pico)com"'
    output = run_command(cmd)
    processes = output.split('\n')
    
    # matches any number of spaces then any number of digits
    regexPid = r" *(\d+)"
    # matches anything of form: Xxx Xxx 00 00:00:00 0000
    regexDate = r"([A-Z][a-z]{2} [A-Z][a-z]{2} \d{2} \d{2}:\d{2}:\d{2} \d{4})"
    # matches any non-whitespace characters ending in minicom or picocom, 
    # then a space and any chars followed by /dev/ttyUSB<any digits>, 
    # then a space and any chars
    regexCmd = r"\S*(?:(?:mini)|(?:pico))com .*" + DEVICE_PREFIX + r"(\d+)(?: .*)?"
    regexProcess = re.compile(r"^"+regexPid+r" "+regexDate+r" "+regexCmd+r"$")
    
    busyDevices = {}
    for process in processes:
        match = regexProcess.match(process)
        if match != None:
            pid = match.group(1)
            date = match.group(2)
            linenum_key = match.group(3)
            busyDevices[linenum_key] = (pid, date)
    return busyDevices

# returns baud rate of device corresponding to line number
# input: linenum (str)
def getBaud(linenum):
    checkDevice(linenum)
    cmd = "sudo stty -F " + DEVICE_PREFIX + str(linenum)
    output = run_command(cmd)
    
    match = re.match(r"^speed (\d+) baud;", output)
    if match != None:
        return match.group(1)
    else:
        click.echo("Unable to determine baud rate")
        return ""
