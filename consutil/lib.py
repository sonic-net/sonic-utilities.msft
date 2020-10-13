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
    import os
    from swsssdk import ConfigDBConnector
    from sonic_py_common import device_info
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

DEVICE_PREFIX = "/dev/ttyUSB"

ERR_CMD = 1
ERR_DEV = 2
ERR_CFG = 3

CONSOLE_PORT_TABLE = "CONSOLE_PORT"
LINE_KEY = "LINE"
BAUD_KEY = "baud_rate"
DEVICE_KEY = "remote_device"
FLOW_KEY = "flow_control"
DEFAULT_BAUD = "9600"

FILENAME = "udevprefix.conf"

# QUIET == True => picocom will not output any messages, and pexpect will wait for console
#                  switch login or command line to let user interact with shell
#        Downside: if console switch output ever does not match DEV_READY_MSG, program will think connection failed
# QUIET == False => picocom will output messages - welcome message is caught by pexpect, so successful
#                   connection will always lead to user interacting with shell
#         Downside: at end of session, picocom will print exit message, exposing picocom to user
QUIET = False
DEV_READY_MSG = r"([Ll]ogin:|[Pp]assword:|[$>#])" # login prompt or command line prompt
TIMEOUT_SEC = 0.2

platform_path, _ = device_info.get_paths_to_platform_and_hwsku_dirs()
PLUGIN_PATH = "/".join([platform_path, "plugins", FILENAME])

if os.path.exists(PLUGIN_PATH):
    fp = open(PLUGIN_PATH, 'r')
    line = fp.readlines()
    DEVICE_PREFIX = "/dev/" + line[0]


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

# returns a list of all lines
def getAllLines():
    config_db = ConfigDBConnector()
    config_db.connect()

    # Querying CONFIG_DB to get configured console ports
    keys = config_db.get_keys(CONSOLE_PORT_TABLE)
    lines = []
    for k in keys:
        line = config_db.get_entry(CONSOLE_PORT_TABLE, k)
        line[LINE_KEY] = k
        lines.append(line)

    # Querying device directory to get all available console ports 
    cmd = "ls " + DEVICE_PREFIX + "*"
    output = run_command(cmd)
    availableTtys = output.split('\n')
    availableTtys = list(filter(lambda dev: re.match(DEVICE_PREFIX + r"\d+", dev) != None, availableTtys))
    for tty in availableTtys:
        k = tty[len(DEVICE_PREFIX):]
        if k not in keys:
            line = { LINE_KEY: k }
            lines.append(line)
    return lines

# returns a dictionary of busy lines and their info
#     maps line number to (pid, process start time)
def getBusyLines():
    cmd = 'ps -eo pid,lstart,cmd | grep -E "(mini|pico)com"'
    output = run_command(cmd)
    processes = output.split('\n')

    # matches any number of spaces then any number of digits
    regexPid = r" *(\d+)"
    # matches anything of form: Xxx Xxx ( 0)or(00) 00:00:00 0000
    regexDate = r"([A-Z][a-z]{2} [A-Z][a-z]{2} [\d ]\d \d{2}:\d{2}:\d{2} \d{4})"
    # matches any non-whitespace characters ending in minicom or picocom,
    # then a space and any chars followed by /dev/ttyUSB<any digits>,
    # then a space and any chars
    regexCmd = r"\S*(?:(?:mini)|(?:pico))com .*" + DEVICE_PREFIX + r"(\d+)(?: .*)?"
    regexProcess = re.compile(r"^"+regexPid+r" "+regexDate+r" "+regexCmd+r"$")

    busyLines = {}
    for process in processes:
        match = regexProcess.match(process)
        if match != None:
            pid = match.group(1)
            date = match.group(2)
            linenum_key = match.group(3)
            busyLines[linenum_key] = (pid, date)
    return busyLines

# returns the target device corresponding to target, or None if line number connot be found
# if deviceBool, interprets target as device name
# otherwise interprets target as line number
# input: target (str), deviceBool (bool), output: device (dict)
def getLine(target, deviceBool=False):
    lines = getAllLines()

    # figure out the search key
    searchKey = LINE_KEY
    if deviceBool:
        searchKey = DEVICE_KEY

    # identify the line number by searching configuration
    lineNumber = None
    for line in lines:
        if searchKey in line and line[searchKey] == target:
            lineNumber = line[LINE_KEY]
            targetLine = line

    return targetLine if lineNumber else None
