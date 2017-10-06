#!/usr/bin/env python
#
# psu_base.py
#
# Abstract base class for implementing platform-specific
#  PSU control functionality for SONiC
#

try:
    import abc
except ImportError, e:
    raise ImportError (str(e) + " - required module not found")

class PsuBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_psu_status(self, index):
        """
        Retrieves the oprational status of power supply unit (PSU) defined
                by index <index>

        :param index: An integer, index of the PSU of which to query status
        :return: Boolean, True if PSU is operating properly, False if PSU is faulty
        """
        return False
