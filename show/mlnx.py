#!/usr/bin/env python
#
# main.py
#
# Specific command-line utility for Mellanox platform
#

try:
    import sys
    import subprocess
    import click
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

ENV_VARIABLE_SX_SNIFFER = 'SX_SNIFFER_ENABLE'
CONTAINER_NAME = 'syncd'
SNIFFER_CONF_FILE = '/etc/supervisor/conf.d/mlnx_sniffer.conf'
SNIFFER_CONF_FILE_IN_CONTAINER = CONTAINER_NAME + ':' + SNIFFER_CONF_FILE
TMP_SNIFFER_CONF_FILE = '/tmp/tmp.conf'


# run command
def run_command(command, display_cmd=False, ignore_error=False):
    """Run bash command and print output to stdout
    """
    if display_cmd == True:
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    (out, err) = proc.communicate()

    if len(out) > 0:
        click.echo(out)

    if proc.returncode != 0 and not ignore_error:
        sys.exit(proc.returncode)


# 'mlnx' group
@click.group()
def mlnx():
    """ Show Mellanox platform information """
    pass


# get current status of sniffer from conf file
def sniffer_status_get(env_variable_name):
    enabled = False
    command = "docker exec {} bash -c 'touch {}'".format(CONTAINER_NAME, SNIFFER_CONF_FILE)
    run_command(command)
    command = 'docker cp {} {}'.format(SNIFFER_CONF_FILE_IN_CONTAINER, TMP_SNIFFER_CONF_FILE)
    run_command(command)
    conf_file = open(TMP_SNIFFER_CONF_FILE, 'r')
    for env_variable_string in conf_file:
        if env_variable_string.find(env_variable_name) >= 0:
            enabled = True
            break
    conf_file.close()
    command = 'rm -rf {}'.format(TMP_SNIFFER_CONF_FILE)
    run_command(command)
    return enabled


@mlnx.command()
def sniffer():
    """ Show sniffer status """
    components = ['sdk']
    env_variable_strings = [ENV_VARIABLE_SX_SNIFFER]
    for index in range(len(components)):
        enabled = sniffer_status_get(env_variable_strings[index])
        if enabled is True:
            print components[index] + " sniffer is enabled"
        else:
            print components[index] + " sniffer is disabled"
