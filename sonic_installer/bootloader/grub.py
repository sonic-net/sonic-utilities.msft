"""
Bootloader implementation for grub based platforms
"""

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
from .onie import OnieInstallerBootloader

class GrubBootloader(OnieInstallerBootloader):

    NAME = 'grub'

    def get_installed_images(self):
        images = []
        config = open(HOST_PATH + '/grub/grub.cfg', 'r')
        for line in config:
            if line.startswith('menuentry'):
                image = line.split()[1].strip("'")
                if IMAGE_PREFIX in image:
                    images.append(image)
        config.close()
        return images

    def get_next_image(self):
        images = self.get_installed_images()
        grubenv = subprocess.check_output(["/usr/bin/grub-editenv", HOST_PATH + "/grub/grubenv", "list"], text=True)
        m = re.search(r"next_entry=(\d+)", grubenv)
        if m:
            next_image_index = int(m.group(1))
        else:
            m = re.search(r"saved_entry=(\d+)", grubenv)
            if m:
                next_image_index = int(m.group(1))
            else:
                next_image_index = 0
        return images[next_image_index]

    def set_default_image(self, image):
        images = self.get_installed_images()
        command = 'grub-set-default --boot-directory=' + HOST_PATH + ' ' + str(images.index(image))
        run_command(command)
        return True

    def set_next_image(self, image):
        images = self.get_installed_images()
        command = 'grub-reboot --boot-directory=' + HOST_PATH + ' ' + str(images.index(image))
        run_command(command)
        return True

    def install_image(self, image_path):
        run_command("bash " + image_path)
        run_command('grub-set-default --boot-directory=' + HOST_PATH + ' 0')

    def remove_image(self, image):
        click.echo('Updating GRUB...')
        config = open(HOST_PATH + '/grub/grub.cfg', 'r')
        old_config = config.read()
        menuentry = re.search("menuentry '" + image + "[^}]*}", old_config).group()
        config.close()
        config = open(HOST_PATH + '/grub/grub.cfg', 'w')
        # remove menuentry of the image in grub.cfg
        config.write(old_config.replace(menuentry, ""))
        config.close()
        click.echo('Done')

        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX)
        click.echo('Removing image root filesystem...')
        subprocess.call(['rm','-rf', HOST_PATH + '/' + image_dir])
        click.echo('Done')

        run_command('grub-set-default --boot-directory=' + HOST_PATH + ' 0')
        click.echo('Image removed')

    @classmethod
    def detect(cls):
        return os.path.isfile(os.path.join(HOST_PATH, 'grub/grub.cfg'))
