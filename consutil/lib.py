#!/usr/bin/env python
#
# lib.py
#
# Helper code for CLI for interacting with switches via console device
#

try:
    import click
    import re
    import swsssdk
    import subprocess
    import sys
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

DEVICE_PREFIX = "/dev/ttyUSB"

ERR_CMD = 1
ERR_DEV = 2

CONSOLE_PORT_TABLE = "CONSOLE_PORT"
BAUD_KEY = "baud_rate"
DEVICE_KEY = "remote_device"
FLOW_KEY = "flow_control"
DEFAULT_BAUD = "9600"

# QUIET == True => picocom will not output any messages, and pexpect will wait for console
#                  switch login or command line to let user interact with shell
#        Downside: if console switch output ever does not match DEV_READY_MSG, program will think connection failed
# QUIET == False => picocom will output messages - welcome message is caught by pexpect, so successful
#                   connection will always lead to user interacting with shell
#         Downside: at end of session, picocom will print exit message, exposing picocom to user
QUIET = False
DEV_READY_MSG = r"([Ll]ogin:|[Pp]assword:|[$>#])" # login prompt or command line prompt
TIMEOUT_SEC = 0.2

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

# returns a sorted list of all devices (whose name matches DEVICE_PREFIX)
def getAllDevices():
    cmd = "ls " + DEVICE_PREFIX + "*"
    output = run_command(cmd)

    devices = output.split('\n')
    devices = list(filter(lambda dev: re.match(DEVICE_PREFIX + r"\d+", dev) != None, devices))
    devices.sort(key=lambda dev: int(dev[len(DEVICE_PREFIX):]))

    return devices

# exits if inputted line number does not correspond to a device
# input: linenum
def checkDevice(linenum):
    devices = getAllDevices()
    if DEVICE_PREFIX + str(linenum) not in devices:
        click.echo("Line number {} does not exist".format(linenum))
        sys.exit(ERR_DEV)

# returns a dictionary of busy devices and their info
#     maps line number to (pid, process start time)
def getBusyDevices():
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

    busyDevices = {}
    for process in processes:
        match = regexProcess.match(process)
        if match != None:
            pid = match.group(1)
            date = match.group(2)
            linenum_key = match.group(3)
            busyDevices[linenum_key] = (pid, date)
    return busyDevices

# returns actual baud rate, configured baud rate,
# and flow control settings of device corresponding to line number
# input: linenum (str), output: (actual baud (str), configured baud (str), flow control (bool))
def getConnectionInfo(linenum):
    config_db = ConfigDBConnector()
    config_db.connect()
    entry = config_db.get_entry(CONSOLE_PORT_TABLE, str(linenum))

    conf_baud = "-" if BAUD_KEY not in entry else entry[BAUD_KEY]
    act_baud = DEFAULT_BAUD if conf_baud == "-" else conf_baud
    flow_control = False
    if FLOW_KEY in entry and entry[FLOW_KEY] == "1":
        flow_control = True

    return (act_baud, conf_baud, flow_control)

# returns the line number corresponding to target, or exits if line number cannot be found
# if deviceBool, interprets target as device name
# otherwise interprets target as line number
# input: target (str), deviceBool (bool), output: linenum (str)
def getLineNumber(target, deviceBool):
    if not deviceBool:
        return target

    config_db = ConfigDBConnector()
    config_db.connect()

    devices = getAllDevices()
    linenums = list(map(lambda dev: dev[len(DEVICE_PREFIX):], devices))

    for linenum in linenums:
        entry = config_db.get_entry(CONSOLE_PORT_TABLE, linenum)
        if DEVICE_KEY in entry and entry[DEVICE_KEY] == target:
            return linenum

    click.echo("Device {} does not exist".format(target))
    sys.exit(ERR_DEV)
    return ""
