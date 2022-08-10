import os
from unittest.mock import Mock, patch

# Import test module
import sonic_installer.bootloader.uboot as uboot

class MockProc():
    commandline = "linuxargs="
    def communicate():
        return commandline, None

def mock_run_command(cmd):
    MockProc.commandline = cmd

@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_set_fips_uboot(run_command_patch, popen_patch):
    class MockProc():
        commandline = "linuxargs"
        def communicate(self):
            return MockProc.commandline, None

    def mock_run_command(cmd):
        # Remove leading string "/usr/bin/fw_setenv linuxargs " -- the 29 characters
        MockProc.commandline = 'linuxargs=' + cmd[29:]

    run_command_patch.side_effect = mock_run_command
    popen_patch.return_value = MockProc()

    image = 'test-image'
    bootloader = uboot.UbootBootloader()

    # The the default setting
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)
