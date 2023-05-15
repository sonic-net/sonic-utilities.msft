import os
import pytest
from unittest.mock import call, patch, MagicMock
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

dropconfig_path = os.path.join(scripts_path, 'dropconfig')
dropconfig = load_module_from_source('dropconfig', dropconfig_path)

class TestDropConfig(object):
    def setup(self):
        print('SETUP')

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'install'])
    def test_install_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to install counter: Counter name not provided')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'uninstall'])
    def test_delete_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to uninstall counter: No counter name provided')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'add'])
    def test_add_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to add reasons: No counter name provided')
        assert e.value.code == 1

    @patch('builtins.print')
    @patch('sys.argv', ['dropconfig', '-c', 'remove'])
    def test_remove_error(self, mock_print):
        with pytest.raises(SystemExit) as e:
            dropconfig.main()
        mock_print.assert_called_once_with('Encountered error trying to remove reasons: No counter name provided')
        assert e.value.code == 1

    def teardown(self):
        print('TEARDOWN')

