import logging
import os
import sys
import unittest
from unittest.mock import patch, mock_open

from utilities_common.general import load_module_from_source

TESTS_DIR_PATH = os.path.dirname(os.path.abspath(__file__))
UTILITY_DIR_PATH = os.path.dirname(TESTS_DIR_PATH)
SCRIPTS_DIR_PATH = os.path.join(UTILITY_DIR_PATH, "scripts")
sys.path.append(SCRIPTS_DIR_PATH)

ABOOT_MACHINE_CFG_PLATFORM = "aboot_platform=x86_64-arista_7050cx3_32s"
ABOOT_MACHINE_CFG_ARCH = "aboot_arch=x86_64"
KERNEL_BOOTING_CFG_KDUMP_DISABLED = "loop=image-20201231.63/fs.squashfs loopfstype=squashfs"
KERNEL_BOOTING_CFG_KDUMP_ENABLED = "loop=image-20201231.63/fs.squashfs loopfstype=squashfs crashkernel=0M-2G:256MB"

logger = logging.getLogger(__name__)
# Load `sonic-kdump-config` module from source since `sonic-kdump-config` does not have .py extension.
sonic_kdump_config_path = os.path.join(SCRIPTS_DIR_PATH, "sonic-kdump-config")
sonic_kdump_config = load_module_from_source("sonic_kdump_config", sonic_kdump_config_path)


class TestSonicKdumpConfig(unittest.TestCase):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @patch("sonic_kdump_config.run_command")
    def test_read_num_kdumps(self, mock_run_cmd):
        """Tests the function `read_num_kdumps(...)` in script `sonic-kdump-config`.
        """
        mock_run_cmd.return_value = (0, ["0"], None)
        num_dumps = sonic_kdump_config.read_num_dumps()
        assert num_dumps == 0

        logger.info("Value of 'num_dumps' is: '{}'.".format(num_dumps))
        logger.info("Expected value of 'num_dumps' is: '0'.")

        mock_run_cmd.return_value = (0, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["3"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.run_command")
    def test_read_use_kdump(self, mock_run_cmd):
        """Tests the function `read_use_kdump(...)` in script `sonic-kdump-config`.
        """
        mock_run_cmd.return_value = (0, ["0"], None)
        is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        assert is_kdump_enabled == 0

        mock_run_cmd.return_value = (0, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["0"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.read_use_kdump")
    @patch("sonic_kdump_config.run_command")
    def test_write_num_kdump(self, mock_run_cmd, mock_read_kdump):
        """Tests the function `write_use_kdump(...)` in script `sonic-kdump-config`.
        """
        mock_run_cmd.side_effect = [(0, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        sonic_kdump_config.write_use_kdump(0)

        mock_run_cmd.side_effect = [(0, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 1
        sonic_kdump_config.write_use_kdump(1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (0, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (0, [""], None)]
        mock_read_kdump.return_value = 1
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 1
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.kdump_disable")
    @patch("sonic_kdump_config.get_current_image")
    @patch("sonic_kdump_config.get_kdump_administrative_mode")
    @patch("sonic_kdump_config.get_kdump_memory")
    @patch("sonic_kdump_config.get_kdump_num_dumps")
    @patch("os.path.exists")
    def test_cmd_kdump_disable(self, mock_path_exist, mock_num_dumps, mock_memory,
                               mock_administrative_mode, mock_image, mock_kdump_disable):
        """Tests the function `cmd_kdump_disable(...)` in script `sonic-kdump-config.py`.
        """
        mock_path_exist.return_value = True
        mock_num_dumps.return_value = 3
        mock_memory.return_value = "0M-2G:256MB"
        mock_administrative_mode = "True"
        mock_image.return_value = "20201230.63"
        mock_kdump_disable.return_value = True

        return_result = sonic_kdump_config.cmd_kdump_disable(True)
        assert return_result == True

        mock_path_exist.return_value = False
        with patch("sonic_kdump_config.open", mock_open(read_data=ABOOT_MACHINE_CFG_PLATFORM)):
            return_result = sonic_kdump_config.cmd_kdump_disable(True)
            assert return_result == True

        mock_path_exist.return_value = False
        with patch("sonic_kdump_config.open", mock_open(read_data=ABOOT_MACHINE_CFG_ARCH)):
            return_result = sonic_kdump_config.cmd_kdump_disable(True)
            assert return_result == False

    @patch("sonic_kdump_config.write_use_kdump")
    @patch("os.path.exists")
    def test_kdump_disable(self, mock_path_exist, mock_write_kdump):
        """Tests the function `kdump_disable(...)` in script `sonic-kdump-config.py`.
        """
        mock_path_exist.return_value = True
        mock_write_kdump.return_value = 0

        return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/image-20201231.64/kernel-cmdline")
        assert return_result == False

        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_ENABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == True
            handle = mock_open_func()
            handle.writelines.assert_called_once()

        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_DISABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == False

        mock_path_exist.return_value = False
        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_ENABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == False
            handle = mock_open_func()
            handle.writelines.assert_called_once()

        mock_path_exist.return_value = False
        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_DISABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == False

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
