"""
Module holding common functions and constants used by sonic-installer and its
subpackages.
"""

import subprocess
import sys

import click

HOST_PATH = '/host'
IMAGE_PREFIX = 'SONiC-OS-'
IMAGE_DIR_PREFIX = 'image-'

# Run bash command and print output to stdout
def run_command(command):
    click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    (out, _) = proc.communicate()

    click.echo(out)

    if proc.returncode != 0:
        sys.exit(proc.returncode)
