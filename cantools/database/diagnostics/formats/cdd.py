# Load and dump a diagnostics database in CDD format.
import logging
from typing import Dict

from xml.etree import ElementTree

from ..data import Data
from ..did import Did
from ..dtc import Dtc
from ..internal_database import InternalDatabase
from ...errors import ParseError
from ...utils import cdd_offset_to_dbc_start_bit

LOGGER = logging.getLogger(__name__)


class DataType(object):

    def __init__(self,
                 name,
                 id_,
                 bit_length,
                 encoding,
                 minimum,
                 maximum,
                 choices,
                 byte_order,
                 unit,
                 factor,
                 offset,
                 divisor,
                 data_format,
                 qty):
        self.name = name
        self.id_ = id_
        self.bit_length = bit_length
        self.encoding = encoding
        self.minimum = minimum
        self.maximum = maximum
        self.choices = choices
        self.byte_order = byte_order
        self.unit = unit
        self.factor = factor
        self.offset = offset
        self.divisor = divisor
        self.data_format = data_format
        self.qty = qty


def _load_choices(data_type):
    choices = {}

    for choice in data_type.findall('TEXTMAP'):
        start = int(choice.attrib['s'].strip('()'))
        end = int(choice.attrib['e'].strip('()'))

        if start == end:
            choices[start] = choice.find('TEXT/TUV[1]').text

    if not choices:
        choices = None

    return choices


def _load_data_types(ecu_doc):
    """Load all data types found in given ECU doc element.

    """

    data_types = {}

    types = ecu_doc.findall('DATATYPES/IDENT')
    types += ecu_doc.findall('DATATYPES/LINCOMP')
    types += ecu_doc.findall('DATATYPES/TEXTTBL')
    
    # todo implement full support of datatypes below
    types += ecu_doc.findall('DATATYPES/STRUCTDT')
    types += ecu_doc.findall('DATATYPES/EOSITERDT')
    types += ecu_doc.findall('DATATYPES/COMPTBL')
    types += ecu_doc.findall('DATATYPES/NUMITERDT')
    types += ecu_doc.findall('DATATYPES/MUXDT')

    for data_type in types:
        # Default values.
        byte_order = None
        unit = None
        factor = None
        offset = None
        divisor = None
        bit_length = None
        data_format = None
        encoding = None
        minimum = None
        maximum = None
        qty = None

        # Name and id.
        type_names = data_type.findall('NAME/TUV')
        if len(type_names) == 1:
            type_name = type_names[0].text
        elif len(type_names) > 1:
            # todo handle STRUCTDT e.g. id='_000002353BFC0FC0'
            None
        else:
            type_name = 'unknown'
            raise ParseError("'NAME/TUV' of data_type not found for ID: %s" % data_type.attrib['id'])

        type_id = data_type.attrib['id']

        # Load from C-type element.
        ctype = data_type.find('CVALUETYPE')

        for key, value in ctype.attrib.items():
            if key == 'bl':
                bit_length = int(value)
            elif key == 'df':
                data_format = value
            elif key == 'enc':
                encoding = value
            elif key == 'minsz':
                minimum = int(value)
            elif key == 'maxsz':
                maximum = int(value)
            elif key == 'qty':
                qty = value
            else:
                LOGGER.debug("Ignoring unsupported attribute '%s'.", key)

        if ctype.attrib['bo'] == '21':
            byte_order = 'big_endian'
        elif ctype.attrib['bo'] == '12':
            byte_order = 'little_endian'
        else:
            raise ParseError("Unknown byte order code: %s" % ctype.attrib['bo'])

        # Load from P-type element.
        ptype_unit = data_type.find('PVALUETYPE/UNIT')

        if ptype_unit is not None:
            unit = ptype_unit.text

        # Choices, scale and offset.
        choices = _load_choices(data_type)

        # Slope and offset.
        comp = data_type.find('COMP')

        comps = data_type.findall('COMP')

        if len(comps) == 1:
            factor = float(comps[0].attrib.get('f', 1))
            offset = float(comps[0].attrib.get('o', 0))
            divisor = float(comps[0].attrib.get('div', 1))
        elif len(comps) > 1:
            # todo COMPTBL handle multiple comp objects e.g. '_00000257F6DDE1E0'
            for comp in comps:
                factor = float(comp.attrib.get('f', 1))
                offset = float(comp.attrib.get('o', 0))
                divisor = float(comp.attrib.get('div', 1))
        else:
            # no comp tag found - use default values
            factor = 1.0
            offset = 0.0
            divisor = 1.0

        data_types[type_id] = DataType(type_name,
                                       type_id,
                                       bit_length,
                                       encoding,
                                       minimum,
                                       maximum,
                                       choices,
                                       byte_order,
                                       unit,
                                       factor,
                                       offset,
                                       divisor,
                                       data_format,
                                       qty)

    return data_types


def _load_data_element(data, offset, data_types):
    """Load given signal element and return a signal object.

    """

    data_type = data_types.get(data.attrib['dtref'], None)

    if data_type is None:
        return None

    # Map CDD/c-style field offset to the DBC/can.Signal.start bit numbering
    # convention for compatability with can.Signal objects and the shared codec
    # infrastructure.
    #
    dbc_start_bitnum = cdd_offset_to_dbc_start_bit(offset, data_type.bit_length, data_type.byte_order)

    return Data(name=data.find('QUAL').text,
                start=dbc_start_bitnum,
                length=data_type.bit_length,
                byte_order=data_type.byte_order,
                scale=data_type.factor / data_type.divisor,
                offset=data_type.offset,
                minimum=data_type.minimum,
                maximum=data_type.maximum,
                unit=data_type.unit,
                choices=data_type.choices,
                encoding=data_type.encoding,
                data_format=data_type.data_format,
                qty=data_type.qty)


def _load_did_element(did, data_types, did_data_lib):
    """Load given DID element and return a did object.

    """

    offset = 0
    datas = []
    data_objs = did.findall('SIMPLECOMPCONT/DATAOBJ')
    data_objs += did.findall('SIMPLECOMPCONT/UNION/STRUCT/DATAOBJ')
    did_data_refs = did.findall('SIMPLECOMPCONT/DIDDATAREF')

    for data_ref in did_data_refs:
        try:
            data_objs += did_data_lib[data_ref.attrib['didRef']].findall('STRUCTURE/DATAOBJ')
        except KeyError:
            pass

    for data_obj in data_objs:
        data = _load_data_element(data_obj,
                                  offset,
                                  data_types)

        if data:
            datas.append(data)
            offset += data.length

    identifier = int(did.find('STATICVALUE').attrib['v'])
    name = did.find('QUAL').text
    length = (offset + 7) // 8

    return Did(identifier=identifier,
               name=name,
               length=length,
               datas=datas)


def _load_did_data_refs(ecu_doc: ElementTree.Element) -> Dict[str, ElementTree.Element]:
    """Load DID data references from given ECU doc element.

    """
    dids = ecu_doc.find('DIDS')

    if dids is None:
        return {}
    else:
        return {did.attrib['id']: did for did in dids.findall('DID')}


def load_string(string, diagnostics_variant: str = ''):
    """Parse given CDD format string.

    """

    root = ElementTree.fromstring(string)
    ecu_doc = root.find('ECUDOC')
    data_types = _load_data_types(ecu_doc)
    did_data_lib = _load_did_data_refs(ecu_doc)
    var = ecu_doc.findall('ECU')[0].find('VAR')
    dids = []

    for diag_class in var.findall('DIAGCLASS'):
        for diag_inst in diag_class.findall('DIAGINST'):
            did = _load_did_element(diag_inst,
                                    data_types,
                                    did_data_lib)
            dids.append(did)

    root = ElementTree.fromstring(string)
    ecu_doc = root.find('ECUDOC')
    dtcs = _load_dtc_elements(ecu_doc, diagnostics_variant)

    return InternalDatabase(dids=dids, dtcs=dtcs)


def _load_dtc_elements(ecu_doc, diagnostics_variant: str = ''):
    """Load all dtcs found in given ECU doc element.

    """

    dtcs = []
    variants = ecu_doc.findall('ECU/VAR')

    parse_all_variants = False
    if not diagnostics_variant:  # load all variants if no variant was selected
        parse_all_variants = True

    for var in variants:
        variant_text_id = var.find('QUAL').text
        if (parse_all_variants == False and
            (diagnostics_variant.lower() != variant_text_id.lower())):
            continue

        recorddts = var.findall('DIAGINST/SIMPLECOMPCONT/RECORDDATAOBJ/RECORDDT')

        for recorddts in recorddts:
            records = recorddts.findall('RECORD')
            for record in records:
                if 'v' not in record.attrib:
                    continue

                if record.attrib['v'].isnumeric():
                    dtc_3byte_code = int(record.attrib['v'])
                else:
                    # numeric 3 byte code expected
                    dtc_3byte_code = None
                    LOGGER.debug("3Byte code unknown for {}".format(id(record)))

                dtc_elem = record.findall('TEXT/TUV')
                dtc_name = dtc_elem[0].text
                dtc = Dtc(identifier=dtc_3byte_code,
                                name=dtc_name)
                dtc.data_udate({'variant':variant_text_id})
                dtcs.append(dtc)

    return dtcs