from unittest.mock import Mock, patch

# Import test module
import sonic_installer.bootloader.aboot as aboot
import tempfile
import shutil

# Constants
image_dir = f'{aboot.IMAGE_DIR_PREFIX}expeliarmus-{aboot.IMAGE_DIR_PREFIX}abcde'
exp_image = f'{aboot.IMAGE_PREFIX}expeliarmus-{aboot.IMAGE_DIR_PREFIX}abcde'
image_dirs = [image_dir]

def test_set_fips_aboot():
    image = 'test-image'
    dirpath = tempfile.mkdtemp()
    bootloader = aboot.AbootBootloader()
    bootloader.get_image_path = Mock(return_value=dirpath)

    # The the default setting
    bootloader._set_image_cmdline(image, 'test=1')
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)

    # Cleanup
    shutil.rmtree(dirpath)
