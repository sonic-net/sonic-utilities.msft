import sys
import os
from unittest import mock

import pytest
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

sys.modules['sonic_platform'] = mock.MagicMock()
import psuutil.main as psuutil


class TestPsuutil(object):

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(psuutil.cli.commands['version'], [])
        assert result.output.rstrip() == 'psuutil version {}'.format(psuutil.VERSION)
