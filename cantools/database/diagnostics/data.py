# DID data.
from typing import Optional

from ...typechecking import ByteOrder, Choices


class Data(object):
    """A data data with position, size, unit and other information. A data
    is part of a DID.

    """

    def __init__(self,
                 name: str,
                 start: int,
                 length: int,
                 byte_order: ByteOrder = 'little_endian',
                 scale: float = 1,
                 offset: float = 0,
                 minimum: Optional[float] = None,
                 maximum: Optional[float] = None,
                 min_num_of_items: Optional[int] = None,
                 max_num_of_items: Optional[int] = None,
                 unit: Optional[str] = None,
                 choices: Optional[Choices] = None,
                 encoding: str = "",
                 data_format: str = "",
                 qty: str = "",
                 sub_elements: list = [],
                 ) -> None:
        #: The data name as a string.
        self.name: str = name

        #: The scale factor of the data value.
        self.scale: float = scale

        #: The offset of the data value.
        self.offset: float = offset

        #: The start bit position of the data within its DID.
        self.start: int = start

        #: The length of the data in bits.
        if qty == 'field' and maximum:
            self.length = maximum * 8
        else:
            self.length = length

        #: Data byte order as ``'little_endian'`` or ``'big_endian'``.
        self.byte_order: ByteOrder = byte_order

        #: The minimum bytes of the data, or ``None`` if unavailable.
        self.minimum: Optional[float] = minimum

        #: The maximum bytes of the data, or ``None`` if unavailable.
        self.maximum: Optional[float] = maximum

        #: The minimum number of items (iterations) or ``None`` if unavailable.
        self.min_num_of_items : Optional[float] = min_num_of_items

        #: The maximum number of items (iterations) or ``None`` if unavailable.
        self.max_num_of_items: Optional[float] = max_num_of_items

        #: The unit of the data as a string, or ``None`` if unavailable.
        self.unit = unit

        #: The data_format of the data as a string 'hex', 'text', 'flt', 'dec'
        self.data_format = data_format

        #: The encoding of the data as a string 'asc', 'uns', 'dbl', 'flt,
        self.encoding = encoding

        #: The quantity of the data as a string 'atom', 'field', or ``None`` if unavailable.
        self.qty = qty

        #: A dictionary mapping data values to enumerated choices, or ``None``
        #: if unavailable.
        self.choices: Optional[Choices] = choices

        # ToDo: Remove once types are handled properly.
        self.is_float: bool = False

        if self.encoding == 'flt' or self.data_format == 'flt':
            self.is_float: bool = True

        self.is_signed: bool = False

        self.sub_elements = sub_elements
        self._codec = None

    def choice_string_to_number(self, string: str) -> int:
        if self.choices is None:
            raise ValueError(f"Data {self.name} has no choices.")

        for choice_number, choice_string in self.choices.items():
            if choice_string == string:
                return choice_number

        raise KeyError(f"Choice {string} not found in Data {self.name}.")

    def __repr__(self) -> str:
        if self.choices is None:
            choices = None
        else:
            choices = '{{{}}}'.format(', '.join(
                ["{}: '{}'".format(value, text)
                 for value, text in self.choices.items()]))

        return "data('{}', {}, {}, '{}', {}, {}, {}, {}, '{}', {}, '{}', '{}', '{}')".format(
            self.name,
            self.start,
            self.length,
            self.byte_order,
            self.scale,
            self.offset,
            self.minimum,
            self.maximum,
            self.unit,
            choices,
            self.data_format,
            self.encoding,
            self.qty)
