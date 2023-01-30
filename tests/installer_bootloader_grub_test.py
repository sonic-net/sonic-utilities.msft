import os
import shutil
from unittest.mock import Mock, patch

# Import test module
import sonic_installer.bootloader.grub as grub


@patch("sonic_installer.bootloader.grub.subprocess.call", Mock())
@patch("sonic_installer.bootloader.grub.open")
@patch("sonic_installer.bootloader.grub.run_command")
@patch("sonic_installer.bootloader.grub.re.search")
def test_remove_image(open_patch, run_command_patch, re_search_patch):
    # Constants
    image_path_prefix = os.path.join(grub.HOST_PATH, grub.IMAGE_DIR_PREFIX)
    exp_image_path = f'{image_path_prefix}expeliarmus-{grub.IMAGE_PREFIX}abcde'
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'

    bootloader = grub.GrubBootloader()

    # Verify rm command was executed with image path
    bootloader.remove_image(image)
    args_list = grub.subprocess.call.call_args_list
    assert len(args_list) > 0

    args, _ = args_list[0]
    assert exp_image_path in args[0]

@patch("sonic_installer.bootloader.grub.HOST_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), 'installer_bootloader_input/_tmp_host'))
def test_set_fips_grub():
    # Prepare the grub.cfg in the _tmp_host folder
    current_path = os.path.dirname(os.path.abspath(__file__))
    grub_config = os.path.join(current_path, 'installer_bootloader_input/host/grub/grub.cfg')
    tmp_host_path = os.path.join(current_path, 'installer_bootloader_input/_tmp_host')
    tmp_grub_path = os.path.join(tmp_host_path, 'grub')
    tmp_grub_config = os.path.join(tmp_grub_path, 'grub.cfg')
    os.makedirs(tmp_grub_path, exist_ok=True)
    shutil.copy(grub_config, tmp_grub_path)

    image = 'SONiC-OS-internal-202205.57377412-84a9a7f11b'
    bootloader = grub.GrubBootloader()

    # The the default setting
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)

    # Cleanup the _tmp_host folder
    shutil.rmtree(tmp_host_path)

def test_verify_image():

    bootloader = grub.GrubBootloader()
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'

    # command should fail
    assert not bootloader.verify_image_sign(image)
