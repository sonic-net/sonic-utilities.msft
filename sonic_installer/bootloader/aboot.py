"""
Bootloader implementation for Aboot used on Arista devices
"""

import collections
import os
import re
import subprocess

import click

from ..common import (
   HOST_PATH,
   IMAGE_DIR_PREFIX,
   IMAGE_PREFIX,
   run_command,
)
from .bootloader import Bootloader

_secureboot = None
def isSecureboot():
    global _secureboot
    if _secureboot is None:
        with open('/proc/cmdline') as f:
           m  = re.search(r"secure_boot_enable=[y1]", f.read())
        _secureboot = bool(m)
    return _secureboot

class AbootBootloader(Bootloader):

    NAME = 'aboot'
    BOOT_CONFIG_PATH = os.path.join(HOST_PATH, 'boot-config')
    DEFAULT_IMAGE_PATH = '/tmp/sonic_image.swi'

    def _boot_config_read(self, path=BOOT_CONFIG_PATH):
        config = collections.OrderedDict()
        with open(path) as f:
            for line in f.readlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                config[key] = value
        return config

    def _boot_config_write(self, config, path=BOOT_CONFIG_PATH):
        with open(path, 'w') as f:
            f.write(''.join('%s=%s\n' % (k, v) for k, v in config.items()))

    def _boot_config_set(self, **kwargs):
        path = kwargs.pop('path', self.BOOT_CONFIG_PATH)
        config = self._boot_config_read(path=path)
        for key, value in kwargs.items():
            config[key] = value
        self._boot_config_write(config, path=path)

    def _swi_image_path(self, image):
        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX)
        if isSecureboot():
           return 'flash:%s/sonic.swi' % image_dir
        return 'flash:%s/.sonic-boot.swi' % image_dir

    def get_current_image(self):
        with open('/proc/cmdline') as f:
            current = re.search(r"loop=/*(\S+)/", f.read()).group(1)
        return current.replace(IMAGE_DIR_PREFIX, IMAGE_PREFIX)

    def get_installed_images(self):
        images = []
        for filename in os.listdir(HOST_PATH):
            if filename.startswith(IMAGE_DIR_PREFIX):
                images.append(filename.replace(IMAGE_DIR_PREFIX, IMAGE_PREFIX))
        return images

    def get_next_image(self):
        config = self._boot_config_read()
        match = re.search(r"flash:/*(\S+)/", config['SWI'])
        return match.group(1).replace(IMAGE_DIR_PREFIX, IMAGE_PREFIX)

    def set_default_image(self, image):
        image_path = self._swi_image_path(image)
        self._boot_config_set(SWI=image_path, SWI_DEFAULT=image_path)
        return True

    def set_next_image(self, image):
        image_path = self._swi_image_path(image)
        self._boot_config_set(SWI=image_path)
        return True

    def install_image(self, image_path):
        run_command("/usr/bin/unzip -od /tmp %s boot0" % image_path)
        run_command("swipath=%s target_path=/host sonic_upgrade=1 . /tmp/boot0" % image_path)

    def remove_image(self, image):
        nextimage = self.get_next_image()
        current = self.get_current_image()
        if image == nextimage:
            image_path = self._swi_image_path(current)
            self._boot_config_set(SWI=image_path, SWI_DEFAULT=image_path)
            click.echo("Set next and default boot to current image %s" % current)

        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX)
        click.echo('Removing image root filesystem...')
        subprocess.call(['rm','-rf', os.path.join(HOST_PATH, image_dir)])
        click.echo('Image removed')

    def get_binary_image_version(self, image_path):
        try:
            version = subprocess.check_output(['/usr/bin/unzip', '-qop', image_path, '.imagehash'])
        except subprocess.CalledProcessError:
            return None
        return IMAGE_PREFIX + version.strip()

    def verify_binary_image(self, image_path):
        try:
            subprocess.check_call(['/usr/bin/unzip', '-tq', image_path])
            # TODO: secureboot check signature
        except subprocess.CalledProcessError:
            return False
        return True

    @classmethod
    def detect(cls):
        with open('/proc/cmdline') as f:
            return 'Aboot=' in f.read()
