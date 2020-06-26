"""
Abstract Bootloader class
"""

class Bootloader(object):

    NAME = None
    DEFAULT_IMAGE_PATH = None

    def get_current_image(self):
        """returns name of the current image"""
        raise NotImplementedError

    def get_next_image(self):
        """returns name of the next image"""
        raise NotImplementedError

    def get_installed_images(self):
        """returns list of installed images"""
        raise NotImplementedError

    def set_default_image(self, image):
        """set default image to boot from"""
        raise NotImplementedError

    def set_next_image(self, image):
        """set next image to boot from"""
        raise NotImplementedError

    def install_image(self, image_path):
        """install new image"""
        raise NotImplementedError

    def remove_image(self, image):
        """remove existing image"""
        raise NotImplementedError

    def get_binary_image_version(self, image_path):
        """returns the version of the image"""
        raise NotImplementedError

    def verify_binary_image(self, image_path):
        """verify that the image is supported by the bootloader"""
        raise NotImplementedError

    @classmethod
    def detect(cls):
        """returns True if the bootloader is in use"""
        return False

