# A DID.

import binascii

from ..utils import encode_data
from ..utils import decode_data
from ..utils import create_encode_decode_formats


class Dtc(object):
    """A DTC containing name and 3-byte-code.

    """

    def __init__(self,
                 identifier,
                 name):
        self._identifier = identifier
        self._name = name
        self._data = {}  # dtc specific data

    @property
    def identifier(self):
        """The did identifier as an integer.

        """

        return self._identifier

    @identifier.setter
    def identifier(self, value):
        self._identifier = value

    @property
    def name(self):
        """The did name as a string.

        """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def data(self):
        """The DTC data
        """
        return self._data

    @data.setter
    def data(self, value):
        self._data = value

    def data_udate(self, data:dict):
        self._data.update(data)

    def refresh(self):
        """Refresh the internal DTC state.

        """
        pass  # nothing to refresh so far

    def __repr__(self):
        return "dtc('{}', 0x{:04x})".format(
            self._name,
            self._identifier)
