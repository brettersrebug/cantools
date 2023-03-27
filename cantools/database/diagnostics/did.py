# A DID.

import binascii

from ..utils import encode_data
from ..utils import decode_data
from ..utils import create_encode_decode_formats


class Did(object):
    """A DID with identifier and other information.

    """

    def __init__(self,
                 identifier,
                 name,
                 length,
                 datas):
        self._identifier = identifier
        self._name = name
        self._length = length
        self._datas = datas
        self._codec = None
        self.refresh()

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
    def length(self):
        """The did name as a string.

        """

        return self._length

    @length.setter
    def length(self, value):
        self._length = value

    @property
    def datas(self):
        """The did datas as a string.

        """

        return self._datas

    @datas.setter
    def datas(self, value):
        self._datas = value

    def get_data_by_name(self, name):
        for data in self._datas:
            if data.name == name:
                return data

        raise KeyError(name)

    def encode(self, data, scaling=True):
        """Encode given data as a DID of this type.

        If `scaling` is ``False`` no scaling of datas is performed.

        >>> foo = db.get_did_by_name('Foo')
        >>> foo.encode({'Bar': 1, 'Fum': 5.0})
        b'\\x01\\x45\\x23\\x00\\x11'

        """

        # todo - maybe extend here the data
        encoded = encode_data(data,
                              self._codec['datas'],
                              self._codec['formats'],
                              scaling)
        encoded |= (0x80 << (8 * self._length))
        encoded = hex(encoded)[4:].rstrip('L')
        # todo - again remove extended data

        return binascii.unhexlify(encoded)[:self._length]

    def decode(self,
               data,
               decode_choices=True,
               scaling=True,
               allow_truncated=False):
        """Decode given data as a DID of this type.

        If `decode_choices` is ``False`` scaled values are not
        converted to choice strings (if available).

        If `scaling` is ``False`` no scaling of datas is performed.

        >>> foo = db.get_did_by_name('Foo')
        >>> foo.decode(b'\\x01\\x45\\x23\\x00\\x11')
        {'Bar': 1, 'Fum': 5.0}

        """

        decoded_data = {}
        for sub_data in self.datas:
            if sub_data._codec:
                decoded_data[sub_data.name] = decode_data(
                    data[sub_data.start // 8: (sub_data.start + sub_data.length) // 8],
                    sub_data.length // 8,
                    sub_data._codec['datas'],
                    sub_data._codec['formats'],
                    decode_choices,
                    scaling,
                    allow_truncated)

        if not decoded_data:
            decode_data(data,
                        self.length,
                        self._codec['datas'],
                        self._codec['formats'],
                        decode_choices,
                        scaling,
                        allow_truncated)

        return decoded_data

    def refresh(self):
        """Refresh the internal DID state.

        """

        for sub_data in self.datas:
            if sub_data.sub_elements:
                sub_data._codec = {
                    'datas': sub_data.sub_elements,
                    'formats': create_encode_decode_formats(sub_data.sub_elements,
                                                            sub_data.length // 8)
                }

        self._codec = {
            'datas': self._datas,
            'formats': create_encode_decode_formats(self._datas,
                                                    self._length)
        }

    def __repr__(self):
        return "did('{}', 0x{:04x})".format(
            self._name,
            self._identifier)
