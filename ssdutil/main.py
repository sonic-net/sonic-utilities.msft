#!/usr/bin/env python
#
# main.py
#
# Command-line utility to check SSD health and parameters
#

try:
    import sys
    import os
    import subprocess
    import argparse
    import syslog
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

DEFAULT_DEVICE="/dev/sda"
SYSLOG_IDENTIFIER = "ssdutil"

PLATFORM_ROOT_PATH = '/usr/share/sonic/device'
SONIC_CFGGEN_PATH = '/usr/local/bin/sonic-cfggen'
HWSKU_KEY = 'DEVICE_METADATA.localhost.hwsku'
PLATFORM_KEY = 'DEVICE_METADATA.localhost.platform'

def syslog_msg(severity, msg, stdout=False):
    """
    Prints to syslog (and stdout if needed) message with specified severity

    Args:
        severity : message severity
        msg      : message
        stdout   : also primt message to stdout

    """
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(severity, msg)
    syslog.closelog()

    if stdout:
        print msg

def get_platform_and_hwsku():
    """
    Retrieves current platform name and hwsku
    Raises an OSError exception when failed to fetch

    Returns:
        tuple of strings platform and hwsku
        e.g. ("x86_64-mlnx_msn2700-r0", "ACS-MSN2700")
    """
    try:
        proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-H', '-v', PLATFORM_KEY],
                                stdout=subprocess.PIPE,
                                shell=False,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        platform = stdout.rstrip('\n')

        proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-d', '-v', HWSKU_KEY],
                                stdout=subprocess.PIPE,
                                shell=False,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        hwsku = stdout.rstrip('\n')
    except OSError, e:
        raise OSError("Cannot detect platform")

    return (platform, hwsku)

def import_ssd_api(diskdev):
    """
    Loads platform specific or generic ssd_util module from source
    Raises an ImportError exception if none of above available

    Returns:
        Instance of the class with SSD API implementation (vendor or generic)
    """

    # Get platform and hwsku
    (platform, hwsku) = get_platform_and_hwsku()

    # try to load platform specific module
    try:
        hwsku_plugins_path = "/".join([PLATFORM_ROOT_PATH, platform, "plugins"])
        sys.path.append(os.path.abspath(hwsku_plugins_path))
        from ssd_util import SsdUtil
    except ImportError as e:
        syslog_msg(syslog.LOG_WARNING, "Platform specific SsdUtil module not found. Falling down to the generic implementation")
        try:
            from sonic_platform_base.sonic_ssd.ssd_generic import SsdUtil
        except ImportError as e:
            syslog_msg(syslog.LOG_ERR, "Failed to import default SsdUtil. Error: {}".format(str(e)), True)
            raise e

    return SsdUtil(diskdev)

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

# ==================== Entry point ====================
def ssdutil():
    if os.geteuid() != 0:
        print "Root privileges are required for this operation"
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", help="Device name to show health info", default=DEFAULT_DEVICE)
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="Show verbose output (some additional parameters)")
    parser.add_argument("-e", "--vendor", action="store_true", default=False, help="Show vendor output (extended output if provided by platform vendor)")
    args = parser.parse_args()

    ssd = import_ssd_api(args.device)

    print "Device Model : {}".format(ssd.get_model())
    if args.verbose:
        print "Firmware     : {}".format(ssd.get_firmware())
        print "Serial       : {}".format(ssd.get_serial())
    print "Health       : {}{}".format(ssd.get_health(),      "%" if is_number(ssd.get_health()) else "")
    print "Temperature  : {}{}".format(ssd.get_temperature(), "C" if is_number(ssd.get_temperature()) else "")
    if args.vendor:
        print ssd.get_vendor_output()

if __name__ == '__main__':
    ssdutil()
