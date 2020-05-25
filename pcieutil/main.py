#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with PCIE in SONiC
#

try:
    import sys
    import os
    import subprocess
    import click
    import imp
    import syslog
    import types
    import traceback
    from tabulate import tabulate
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SYSLOG_IDENTIFIER = "pcieutil"
PLATFORM_SPECIFIC_MODULE_NAME = "pcieutil"

PLATFORM_ROOT_PATH = '/usr/share/sonic/device'
PLATFORM_ROOT_PATH_DOCKER = '/usr/share/sonic/platform'
SONIC_CFGGEN_PATH = '/usr/local/bin/sonic-cfggen'
HWSKU_KEY = 'DEVICE_METADATA.localhost.hwsku'
PLATFORM_KEY = 'DEVICE_METADATA.localhost.platform'

#from pcieutil import PcieUtil 

# Global platform-specific psuutil class instance
platform_pcieutil = None
hwsku_path = None

# ========================== Syslog wrappers ==========================


def log_info(msg, also_print_to_console=False):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()

    if also_print_to_console:
        click.echo(msg)


def log_warning(msg, also_print_to_console=False):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_WARNING, msg)
    syslog.closelog()

    if also_print_to_console:
        click.echo(msg)


def log_error(msg, also_print_to_console=False):
    syslog.openlog(SYSLOG_IDENTIFIER)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()

    if also_print_to_console:
        click.echo(msg)

def log_out(name, result):            
    string = "PCI Device:  {} ".format(name)
    length = 105-len(string)
    sys.stdout.write(string)        
    for i in xrange(int(length)):
        sys.stdout.write("-")
    print ' [%s]' % result
    
# ==================== Methods for initialization ====================

# Returns platform and HW SKU
def get_platform_and_hwsku():
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


# Loads platform specific psuutil module from source
def load_platform_pcieutil():
    global platform_pcieutil
    global hwsku_plugins_path
    # Get platform and hwsku
    (platform, hwsku) = get_platform_and_hwsku()

    # Load platform module from source
    try:
        hwsku_plugins_path = "/".join([PLATFORM_ROOT_PATH, platform, "plugins"])
        sys.path.append(os.path.abspath(hwsku_plugins_path))
        from pcieutil import PcieUtil
    except ImportError as e:
        log_warning("Fail to load specific PcieUtil moudle. Falling down to the common implementation")
        try:
            from sonic_platform_base.sonic_pcie.pcie_common import PcieUtil
            platform_pcieutil = PcieUtil(hwsku_plugins_path)
        except ImportError as e:
            log_error("Fail to load default PcieUtil moudle. Error :{}".format(str(e)), True)
            raise e


# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'psuutil' command
@click.group()
def cli():
    """pcieutil - Command line utility for checking pci device"""
    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load platform-specific psuutil class
    load_platform_pcieutil()

# 'version' subcommand
@cli.command()
def version():
    """Display version info"""
    click.echo("pcieutil version {0}".format(VERSION))

#show the platform PCIE info


def print_test_title(testname):
    click.echo("{name:=^80s}".format(name=testname))

#  Show PCIE lnkSpeed
@cli.command()
def pcie_show():
    '''Display PCIe Device '''
    testname = "Display PCIe Device"
    print_test_title(testname)
    resultInfo = platform_pcieutil.get_pcie_device()
    for item in resultInfo:
        Bus = item["bus"]
        Dev = item["dev"]
        Fn = item["fn"]
        Name = item["name"]
        Id = item["id"]
        print "bus:dev.fn %s:%s.%s - dev_id=0x%s,  %s" % (Bus,Dev,Fn,Id,Name) 
        
    



#  Show PCIE Vender ID and Device ID
@cli.command()
def pcie_check():
    '''Check PCIe Device '''
    testname = "PCIe Device Check"
    err = 0
    print_test_title(testname)
    resultInfo = platform_pcieutil.get_pcie_check()
    for item in resultInfo:
        if item["result"] == "Passed":
            log_out(item["name"], "Passed")
        else:
            log_out(item["name"], "Failed")
            log_warning("PCIe Device: " +  item["name"] + " Not Found")
            err+=1
    if err:
        print "PCIe Device Checking All Test ----------->>> FAILED"
    else:
        print "PCIe Device Checking All Test ----------->>> PASSED"
        



@cli.command()
@click.confirmation_option(prompt="Are you sure to overwrite config file pcie.yaml with current pcie device info?")
def pcie_generate():
    '''Generate config file with current pci device'''
    platform_pcieutil.dump_conf_yaml()
    print "Generate config file pcie.yaml under path %s" %hwsku_plugins_path

if __name__ == '__main__':
    cli()
