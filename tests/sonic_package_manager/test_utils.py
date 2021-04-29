#!/usr/bin/env python

from sonic_package_manager import utils


def test_make_python_identifier():
    assert utils.make_python_identifier('-some-package name').isidentifier()
    assert utils.make_python_identifier('01 leading digit').isidentifier()
