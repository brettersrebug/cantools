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
        self._protocol_services = []
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
    def protocol_services(self):
        """The protocol_service as ProtocolService.

        """

        return self._protocol_services

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

        # todo - encode for sub_elements of STRUCTDT to be added!
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

        # decode all elements - if there are e.g. structures included they will be replaced later
        decoded_data = decode_data(data,
                                   self.length,
                                   self._codec['datas'],
                                   self._codec['formats'],
                                   decode_choices,
                                   scaling,
                                   allow_truncated)

        # decode sub elements for e.g. datatype STRUCTDT and replace the specifc decoded_data element
        for sub_data_obj in self.datas:
            if sub_data_obj._codec:
                dec_data_list = []
                _byte_offset = 0
                _iter_len = sub_data_obj.minimum // sub_data_obj.min_num_of_items
                for i in range(0, sub_data_obj.max_num_of_items):
                    _sub_data = data[sub_data_obj.start // 8 + _byte_offset:
                                     sub_data_obj.start // 8 + _iter_len + _byte_offset]

                    if len(_sub_data) < _iter_len:
                        if i < sub_data_obj.min_num_of_items and allow_truncated is False:
                            raise BufferError("Data-Buffer to short to read %d items." % sub_data_obj.min_num_of_items)
                        dec_data_list.append(None)
                        break
                    else:
                        dec_data_list.append(decode_data(
                            _sub_data,
                            len(_sub_data),  # sub_data_obj.length // 8,
                            sub_data_obj._codec['datas'],
                            sub_data_obj._codec['formats'],
                            decode_choices,
                            scaling,
                            allow_truncated))

                    _byte_offset += len(_sub_data)

                if sub_data_obj.min_num_of_items == sub_data_obj.max_num_of_items == 1:
                    # if it is per default a field with size of 1 (min/max) do not use a list as type
                    decoded_data[sub_data_obj.name] = dec_data_list[0]
                else:
                    decoded_data[sub_data_obj.name] = dec_data_list

        return decoded_data

    def refresh(self):
        """Refresh the internal DID state.

        """

        for sub_data_obj in self.datas:
            if sub_data_obj.sub_elements:
                if sub_data_obj.qty == 'field' and sub_data_obj.max_num_of_items and sub_data_obj.maximum:
                    sub_data_obj._codec = {
                        'datas': sub_data_obj.sub_elements,
                        'formats': create_encode_decode_formats(sub_data_obj.sub_elements,
                                                                sub_data_obj.maximum // sub_data_obj.max_num_of_items) # minimum can be 0 use maximum therefore
                    }
                else:
                    sub_data_obj._codec = {
                        'datas': sub_data_obj.sub_elements,
                        'formats': create_encode_decode_formats(sub_data_obj.sub_elements,
                                                                sub_data_obj.length // 8)
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
