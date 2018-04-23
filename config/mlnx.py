#!/usr/bin/env python
#
# main.py
#
# Specific command-line utility for Mellanox platform
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
    import time
    from tabulate import tabulate
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SNIFFER_SYSLOG_IDENTIFIER = "sniffer"

# Mellanox platform name
MLNX_PLATFORM_NAME = 'mellanox'

# sonic-cfggen -y /etc/sonic/sonic_version.yml -v asic_type
PLATFORM_ROOT_PATH = '/usr/share/sonic/device'
SONIC_CFGGEN_PATH = '/usr/local/bin/sonic-cfggen'
SONIC_VERSION_PATH = '/etc/sonic/sonic_version.yml'
ASIC_TYPE_KEY = 'asic_type'

# SDK sniffer env variable
ENV_VARIABLE_SX_SNIFFER = 'SX_SNIFFER_ENABLE'
ENV_VARIABLE_SX_SNIFFER_TARGET = 'SX_SNIFFER_TARGET'

# SDK sniffer file path and name
SDK_SNIFFER_TARGET_PATH = '/var/log/mellanox/sniffer/'
SDK_SNIFFER_FILENAME_PREFIX = 'sx_sdk_sniffer_'
SDK_SNIFFER_FILENAME_EXT = '.pcap'

# Supervisor config file path
TMP_SNIFFER_CONF_FILE = '/tmp/tmp.conf'
SNIFFER_CONF_FILE = '/etc/supervisor/conf.d/mlnx_sniffer.conf'

# Command to restart swss service
COMMAND_RESTART_SWSS = 'service swss restart'

# global variable SDK_SNIFFER_TARGET_FILE_NAME
SDK_SNIFFER_TARGET_FILE_NAME = ''


# ========================== Syslog wrappers ==========================
def log_info(msg, syslog_identifier, also_print_to_console=False):
    syslog.openlog(syslog_identifier)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()

    if also_print_to_console:
        print msg


def log_warning(msg, syslog_identifier, also_print_to_console=False):
    syslog.openlog(syslog_identifier)
    syslog.syslog(syslog.LOG_WARNING, msg)
    syslog.closelog()

    if also_print_to_console:
        print msg


def log_error(msg, syslog_identifier, also_print_to_console=False):
    syslog.openlog(syslog_identifier)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()

    if also_print_to_console:
        print msg


# run command
def run_command(command, pager=False):
    if pager is True:
        # click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        click.echo_via_pager(p.stdout.read())
    else:
        # click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        click.echo(p.stdout.read())


# Get asic type with command "sonic-cfggen -y /etc/sonic/sonic_version.yml -v asic_type"
def get_asic_type():
    try:
        proc = subprocess.Popen([SONIC_CFGGEN_PATH, '-y', SONIC_VERSION_PATH, '-v', ASIC_TYPE_KEY],
                                stdout=subprocess.PIPE,
                                shell=False,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        asic_type = stdout.rstrip('\n')
    except OSError, e:
        raise OSError("Cannot detect platform asic type, %s" % str(e))

    return asic_type


# verify if the platform is with Mellanox asic.
def verify_asic_type():
    asic_type = get_asic_type()
    return cmp(asic_type, MLNX_PLATFORM_NAME)


# generate sniffer target file name include a time stamp.
def generate_file_name(prm=False, sdk=False):
    time_stamp = time.strftime("%Y%m%d%H%M%S")
    if sdk is True:
        file_name = SDK_SNIFFER_FILENAME_PREFIX + time_stamp + SDK_SNIFFER_FILENAME_EXT
        global SDK_SNIFFER_TARGET_FILE_NAME
        SDK_SNIFFER_TARGET_FILE_NAME = file_name
    elif prm is True:
        # place holders for 'sniff prm enable/disable' and 'sniffer all enable/disable'
        pass
    else:
        file_name = ''

    return file_name


# generate supervisor conf file for sniffer
def generate_conf_file(sdk=False, prm=False, all=False):
    if sdk is True:
        target_filename = generate_file_name(sdk=True)
        tart_fullpath = SDK_SNIFFER_TARGET_PATH + target_filename
        conf_file = open(TMP_SNIFFER_CONF_FILE, 'w')
        conf_file.write('[program:syncd]\n')
        env_str = 'environment=' + ENV_VARIABLE_SX_SNIFFER + '="1",' + ENV_VARIABLE_SX_SNIFFER_TARGET + '="' + tart_fullpath + '"\n'
        conf_file.write(env_str)
        conf_file.close()
    elif prm is True:
        # place holder for prm sniffer
        pass

    elif all is True:
        # place holder for all sniffer
        pass

    else:
        pass

# set supervisor conf file for sniffer enable
def set_conf_for_sniffer_enable(prm=False, sdk=False, all=False):
    if sdk is True:
        generate_conf_file(sdk=True)
        command = 'docker cp ' + TMP_SNIFFER_CONF_FILE + ' ' + 'syncd:' + SNIFFER_CONF_FILE
        run_command(command)

        command = 'rm -rf ' + TMP_SNIFFER_CONF_FILE
        run_command(command)

    elif prm is True:
        # place holder for prm sniffer
        pass

    elif all is True:
        # place holder for all sniffer
        pass

    else:
        pass

# remove the sniffer supervisor conf file from syncd container
def rm_conf_for_sniffer_disable():
    command = 'docker exec syncd rm -rf ' + SNIFFER_CONF_FILE
    run_command(command)


# restart the swss service with command 'service swss restart'
def restart_swss():
    try:
        run_command(COMMAND_RESTART_SWSS)
    except OSError, e:
        log_error("Not able to restart swss service, %s" % str(e), SNIFFER_SYSLOG_IDENTIFIER, True)
        return 1
    return 0


# ==================== CLI commands and groups ====================

# Callback for confirmation prompt. Aborts if user enters "n"
def _abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


# 'mlnx' group
@click.group()
def mlnx():
    """Mellanox platform specific configuration tasks"""
    # check the platform info, this command only work on Mellanox platform
    err = verify_asic_type()
    if err != 0:
        print "This command only supported on Mellanox platform"
        sys.exit(2)


# 'sniffer' group
@mlnx.group()
def sniffer():
    """sniffer - Utility for managing Mellanox SDK/PRM sniffer"""
    pass


# 'sdk' subgroup
@sniffer.group()
def sdk():
    """SDK Sniffer - Command Line to enable/disable SDK sniffer"""
    pass


# 'sniffer sdk enable' command
@sdk.command('enable')
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false, expose_value=False,
              prompt='To enable SDK sniffer swss service will be restarted, continue?')
def enable_sdk_sniffer():
    """Enable SDK Sniffer"""
    print "Enabling SDK sniffer"

    set_conf_for_sniffer_enable(sdk=True)

    err = restart_swss()
    if err is not 0:
        return

    full_file_path = SDK_SNIFFER_TARGET_PATH + SDK_SNIFFER_TARGET_FILE_NAME

    print 'sdk sniffer recording to file %s.' % full_file_path


# 'sniffer sdk disable' command
@sdk.command('disable')
@click.option('-y', '--yes', is_flag=True, callback=_abort_if_false, expose_value=False,
              prompt='To disable SDK sniffer swss service will be restarted, continue?')
def disable_sdk_sniffer():
    """Disable SDK Sniffer"""
    print "Disabling SDK sniffer"

    rm_conf_for_sniffer_disable()

    err = restart_swss()
    if err is not 0:
        return

    print "SDK sniffer disabled"


# place holders for 'sniff prm enable/disable' and 'sniffer all enable/disable'
'''
@cli.group()
def prm():
    """PRM Sniffer - Command Line to enable/disable PRM sniffer"""
    pass


@prm.command('enable')
def enable_prm_sniffer():
    """Enable SDK sniffer"""
    pass


@prm.command('disable')
def disable_prm_sniffer():
    """Disable PRM sniffer"""
    pass


@cli.group()
def all():
    """ALL SNIFFERS - Command line to enable/disable PRM and SDK sniffer"""
    pass


@all.command('enable')
def enable_all_sniffer():
    """Enable PRM and SDK sniffers"""
    pass


@all.command('disable')
def disable_all_sniffer():
    """Disable PRM and SDK sniffers"""
    pass

@cli.group()
def status():
    """Sniffer running status - Command Line to show sniffer running status"""
    pass
    
'''

if __name__ == '__main__':
    mlnx()
