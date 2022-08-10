import os
from contextlib import contextmanager
from sonic_installer.main import sonic_installer
from click.testing import CliRunner
from unittest.mock import patch, Mock, call

@patch("sonic_installer.main.get_bootloader")
def test_set_fips(get_bootloader):
    """ This test covers the execution of "sonic-installer set-fips/get-fips" command. """

    image = "image_1"
    next_image = "image_2"

    # Setup bootloader mock
    mock_bootloader = Mock()
    mock_bootloader.get_next_image = Mock(return_value=next_image)
    mock_bootloader.get_installed_images = Mock(return_value=[image, next_image])
    mock_bootloader.set_fips = Mock()
    mock_bootloader.get_fips = Mock(return_value=False)
    get_bootloader.return_value=mock_bootloader

    runner = CliRunner()

    # Test set-fips command options: --enable-fips/--disable-fips
    result = runner.invoke(sonic_installer.commands["set-fips"], [next_image, '--enable-fips'])
    assert 'Set FIPS' in result.output
    result = runner.invoke(sonic_installer.commands["set-fips"], ['--disable-fips'])
    assert 'Set FIPS' in result.output

    # Test command get-fips options
    result = runner.invoke(sonic_installer.commands["get-fips"])
    assert "FIPS is disabled" in result.output
    mock_bootloader.get_fips = Mock(return_value=True)
    result = runner.invoke(sonic_installer.commands["get-fips"], [next_image])
    assert "FIPS is enabled" in result.output
