from unittest.mock import Mock, patch

# Import test module
import sonic_installer.bootloader.onie as onie


@patch("sonic_installer.bootloader.onie.re.search")
def test_get_current_image(re_search):
    # Constants
    image = f'{onie.IMAGE_DIR_PREFIX}expeliarmus-{onie.IMAGE_DIR_PREFIX}abcde'
    exp_image = f'{onie.IMAGE_PREFIX}expeliarmus-{onie.IMAGE_DIR_PREFIX}abcde'

    bootloader = onie.OnieInstallerBootloader()

    # Test image dir conversion
    onie.re.search().group = Mock(return_value=image)
    assert bootloader.get_current_image() == exp_image
