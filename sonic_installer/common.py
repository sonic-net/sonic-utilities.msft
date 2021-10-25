"""
Module holding common functions and constants used by sonic-installer and its
subpackages.
"""

import subprocess
import sys
import signal

import click

from .exception import SonicRuntimeException

HOST_PATH = '/host'
IMAGE_PREFIX = 'SONiC-OS-'
IMAGE_DIR_PREFIX = 'image-'
ROOTFS_NAME = 'fs.squashfs'
UPPERDIR_NAME = 'rw'
WORKDIR_NAME = 'work'
DOCKERDIR_NAME = 'docker'

# Run bash command and print output to stdout
def run_command(command):
    click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))

    proc = subprocess.Popen(command, shell=True, text=True, stdout=subprocess.PIPE)
    (out, _) = proc.communicate()

    click.echo(out)

    if proc.returncode != 0:
        sys.exit(proc.returncode)

# Run bash command and return output, raise if it fails
def run_command_or_raise(argv, raise_exception=True):
    click.echo(click.style("Command: ", fg='cyan') + click.style(' '.join(argv), fg='green'))

    proc = subprocess.Popen(argv, text=True, stdout=subprocess.PIPE)
    out, _ = proc.communicate()

    if proc.returncode != 0 and raise_exception:
        raise SonicRuntimeException("Failed to run command '{0}'".format(argv))

    return out.rstrip("\n")

# Needed to prevent "broken pipe" error messages when piping
# output of multiple commands using subprocess.Popen()
def default_sigpipe():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

