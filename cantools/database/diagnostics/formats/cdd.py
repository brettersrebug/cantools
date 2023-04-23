# Load and dump a diagnostics database in CDD format.
import logging
import copy
from typing import Dict

from xml.etree import ElementTree

from ..data import Data
from ..did import Did
from ..dtc import Dtc
from ..internal_database import InternalDatabase
from ...errors import ParseError
from ...utils import cdd_offset_to_dbc_start_bit

LOGGER = logging.getLogger(__name__)


class DCL_ServiceTemplate(object):
    def __init__(self,
                 id: int,
                 name: str,
                 qualifier: str):
        self.id = id
        self.name = name
        self.qualifier = qualifier


class ProtocolService(object):
    def __init__(self,
                 id: int,
                 name: str,
                 sid: int,
                 qualifier: str):
        self.id = id
        self.name = name
        self.sid = sid
        self.qualifier = qualifier
        self.dcl_srv_tmpl = {}
        self.dids = []

    def update_dcl_srv_templates(self, template: dict):
        """

        Parameters
        ----------
        template:dict
            format {id: DCL_ServiceTemplate}

        Returns
        -------
            None

        """
        self.dcl_srv_tmpl.update(template)


class DataType(object):

    def __init__(self,
                 name,
                 id_,
                 bit_length,
                 encoding,
                 minimum,
                 maximum,
                 min_num_of_items,
                 max_num_of_items,
                 choices,
                 byte_order,
                 unit,
                 factor,
                 offset,
                 divisor,
                 data_format,
                 qty,
                 sub_elements):
        self.name = name
        self.id_ = id_
        self.bit_length = bit_length
        self.encoding = encoding
        self.minimum = minimum
        self.maximum = maximum
        self.min_num_of_items = min_num_of_items
        self.max_num_of_items = max_num_of_items
        self.choices = choices
        self.byte_order = byte_order
        self.unit = unit
        self.factor = factor
        self.offset = offset
        self.divisor = divisor
        self.data_format = data_format
        self.qty = qty
        self.sub_elements = sub_elements


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


def _load_protocol_services(ecu_doc):
    protocol_services_elements = ecu_doc.findall('PROTOCOLSERVICES/PROTOCOLSERVICE')

    protocol_services = []
    ps_dict = {}
    for ps_elem in protocol_services_elements:
        ps_id = ps_elem.attrib['id']
        constcomp = ps_elem.find("REQ/CONSTCOMP")
        ps_name = ps_elem.find("NAME/TUV").text
        ps_qual = ps_elem.find("QUAL").text
        if constcomp:
            ps_sid = int(constcomp.attrib.get('v', -1))
            ps = ProtocolService(id=ps_id, name=ps_name, sid=ps_sid, qualifier=ps_qual)
            ps_dict.update({ps_id: ps})
            protocol_services.append(ps)

    dcl_srv_tmpl_elements = ecu_doc.findall('DCLTMPLS/DCLTMPL/DCLSRVTMPL')
    for dcl_srv_tmpl_element in dcl_srv_tmpl_elements:
        tmplref = dcl_srv_tmpl_element.attrib.get('tmplref', None)
        ps = ps_dict.get(tmplref, None)
        if ps is not None:
            id = dcl_srv_tmpl_element.attrib.get('id', -1)
            dcl_srv_tmpl = DCL_ServiceTemplate(id=id,
                                               name=dcl_srv_tmpl_element.find('NAME/TUV').text,
                                               qualifier=dcl_srv_tmpl_element.find('QUAL').text,
                                               )
            ps.update_dcl_srv_templates({id: dcl_srv_tmpl})

    return protocol_services


def _load_data_types(ecu_doc):
    """Load all data types found in given ECU doc element.

    """

    data_types = {}

    types = ecu_doc.findall('DATATYPES/IDENT')
    types += ecu_doc.findall('DATATYPES/LINCOMP')
    types += ecu_doc.findall('DATATYPES/TEXTTBL')

    # todo implement full support of datatypes below
    types += ecu_doc.findall('DATATYPES/COMPTBL')
    types += ecu_doc.findall('DATATYPES/MUXDT')
    types += ecu_doc.findall('DATATYPES/NUMITERDT')

    types += ecu_doc.findall('DATATYPES/STRUCTDT')
    types += ecu_doc.findall('DATATYPES/EOSITERDT')


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
        min_num_of_items = None  # used for type EOSITERDT
        max_num_of_items = None  # used for type EOSITERDT
        qty = None

        # Name and id.
        type_names = data_type.findall('QUAL')
        if len(type_names) > 1:
            raise ParseError("Multiple 'QUAL' entries found for: %s" % data_type.attrib['id'])

        type_name = type_names[0].text

        type_id = data_type.attrib.get('id', None)  # for struct objects no id is available
        min_num_of_items = int(data_type.attrib.get('minNumOfItems', 1))
        max_num_of_items = int(data_type.attrib.get('maxNumOfItems', 1))

        # Load from C-type element.
        ctype = data_type.find('CVALUETYPE') # PVALUETYPE Display Format not handled so far

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
            elif key == 'bo':
                if value == '21':
                    byte_order = 'big_endian'
                elif value == '12':
                    byte_order = 'little_endian'
                else:
                    raise ParseError("Unknown byte order code: %s" % ctype.attrib['bo'])
            else:
                # key == 'sig''sig' ...decimal places - are not supported yet
                # key == 'sz' ... 'no'/'yes' meaning unclear
                # e.g. for <PVALUETYPE bl='64' bo='21' enc='dbl' sig='4' df='flt' qty='atom' sz='no' minsz='0' maxsz='255'>
                # LOGGER.debug("Ignoring unsupported attribute '%s'.", key)
                pass

        # Load from P-type element.
        ptype_unit = data_type.find('PVALUETYPE/UNIT')

        if ptype_unit is not None:
            unit = ptype_unit.text

        # Choices, scale and offset.
        choices = _load_choices(data_type)

        # Slope and offset.
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

        sub_elements = []
        if data_type.tag in ['STRUCTDT', 'EOSITERDT']:
            struct_refs = data_type.findall('STRUCT')
            for struct_ref in struct_refs:
                idref = struct_ref.attrib['dtref']
                if idref in data_types:
                    struct_dt = copy.deepcopy(data_types[idref])
                    struct_dt.name = struct_ref.find('QUAL').text
                    struct_dt.id_ = struct_ref.attrib['oid']

                    #dataobj_refs = struct_ref.findall(".")
                    for child in struct_ref:
                        if child.tag == 'DATAOBJ':
                            child_idref = child.attrib['dtref']
                            if child_idref in data_types:
                                # struct_dt.sub_elements.append((dataobj_ref.find('NAME/TUV').text, data_types[idref]))
                                struct_dt.sub_elements.append((child.find('QUAL').text, data_types[child_idref]))
                            else:
                                raise ParseError("Unknown STRUCTDT data_object: {}".format(child_idref))
                        elif child.tag == 'GAPDATAOBJ':
                            gapobj = DataType(child.find('QUAL').text,
                                              child.attrib['oid'],
                                              int(child.attrib['bl']),
                                              'uns',
                                              0,
                                              (1 << int(child.attrib['bl'])) - 1,
                                              1,
                                              1,
                                              None,
                                              'big_endian',
                                              None,
                                              1,
                                              0,
                                              1,
                                              'dec',
                                              1,
                                              [])
                            struct_dt.sub_elements.append((child.find('QUAL').text, gapobj))
                            # data_types[child.attrib['oid']] = gapobj
                        else:
                            pass # nothing to do

                    # sub_elements.append((dataobj_ref.find('NAME/TUV').text, data_types[idref]))
                    sub_elements.append((struct_ref.find('QUAL').text, struct_dt))
                else:
                    raise ParseError("Unknown STRUCTDT/EOSITERDT data_object: {}".format(idref))

            for child in data_type:
                if child.tag == 'DATAOBJ':
                    child_idref = child.attrib['dtref']
                    if child_idref in data_types:
                        # sub_elements.append((dataobj_ref.find('NAME/TUV').text, data_types[idref]))
                        sub_elements.append((child.find('QUAL').text, data_types[child_idref]))
                    else:
                        raise ParseError("Unknown DATAOBJ data_object: {}".format(child_idref))
                elif child.tag == 'GAPDATAOBJ':
                    gapobj = DataType(child.find('QUAL').text,
                                      child.attrib['oid'],
                                      int(child.attrib['bl']),
                                      'uns',
                                      0,
                                      (1 << int(child.attrib['bl'])) - 1,
                                      1,
                                      1,
                                      None,
                                      'big_endian',
                                      None,
                                      1,
                                      0,
                                      1,
                                      'dec',
                                      1,
                                      [])
                    sub_elements.append((child.find('QUAL').text, gapobj))
                else:
                    pass # nothing to do

            # dataobj_refs = data_type.findall('DATAOBJ')
            # for dataobj_ref in dataobj_refs:
            #     idref = dataobj_ref.attrib['dtref']
            #     if idref in data_types:
            #         # sub_elements.append((dataobj_ref.find('NAME/TUV').text, data_types[idref]))
            #         sub_elements.append((dataobj_ref.find('QUAL').text, data_types[idref]))
            #     else:
            #         raise ParseError("Unknown STRUCTDT data_object: {}".format(idref))

        data_types[type_id] = DataType(type_name,
                                       type_id,
                                       bit_length,
                                       encoding,
                                       minimum,
                                       maximum,
                                       min_num_of_items,
                                       max_num_of_items,
                                       choices,
                                       byte_order,
                                       unit,
                                       factor,
                                       offset,
                                       divisor,
                                       data_format,
                                       qty,
                                       sub_elements)

    return data_types


def _load_data_element(data, name, offset, data_types):
    """Load given signal element and return a signal object.

    """

    if type(data) == DataType:
        data_type = data
    else:
        data_type = data_types.get(data.attrib['dtref'], None)

    if data_type is None:
        return None

    # Map CDD/c-style field offset to the DBC/can.Signal.start bit numbering
    # convention for compatability with can.Signal objects and the shared codec
    # infrastructure.
    #
    dbc_start_bitnum = cdd_offset_to_dbc_start_bit(offset, data_type.bit_length, data_type.byte_order)

    sub_offset = 0  # sub-elements start at offset 0
    sub_datas = []

    for sub_elem in data_type.sub_elements:
        sub_data_type = sub_elem[1]
        # if len(sub_elem.sub_elements) > 0:
        #     None
        sub_dbc_start_bitnum = cdd_offset_to_dbc_start_bit(sub_offset, sub_data_type.bit_length, sub_data_type.byte_order)
        sub_data = Data(name=sub_elem[0],
                        start=sub_dbc_start_bitnum,
                        length=sub_data_type.bit_length,
                        byte_order=sub_data_type.byte_order,
                        scale=sub_data_type.factor / sub_data_type.divisor,
                        offset=sub_data_type.offset,
                        minimum=sub_data_type.minimum,
                        maximum=sub_data_type.maximum,
                        min_num_of_items=data_type.min_num_of_items,
                        max_num_of_items=data_type.max_num_of_items,
                        unit=sub_data_type.unit,
                        choices=sub_data_type.choices,
                        encoding=sub_data_type.encoding,
                        data_format=sub_data_type.data_format,
                        qty=sub_data_type.qty,
                        sub_elements=sub_data_type.sub_elements)
        sub_datas.append(sub_data)
        sub_offset += sub_data_type.bit_length

    return Data(name=name,
                start=dbc_start_bitnum,
                length=data_type.bit_length,
                byte_order=data_type.byte_order,
                scale=data_type.factor / data_type.divisor,
                offset=data_type.offset,
                minimum=data_type.minimum,
                maximum=data_type.maximum,
                min_num_of_items=data_type.min_num_of_items,
                max_num_of_items=data_type.max_num_of_items,
                unit=data_type.unit,
                choices=data_type.choices,
                encoding=data_type.encoding,
                data_format=data_type.data_format,
                qty=data_type.qty,
                sub_elements=sub_datas)


def _load_did_element(diaginst, data_types, did_data_lib, protocol_services):
    """Load given DID element and return a did object.

    """

    offset = 0
    datas = []
    data_objs = []
    # data_objs = diaginst.findall('SIMPLECOMPCONT/DATAOBJ')
    # data_objs += diaginst.findall('SIMPLECOMPCONT/UNION/STRUCT/DATAOBJ')
    # did_data_refs = diaginst.findall('SIMPLECOMPCONT/DIDDATAREF')
    service_elements = diaginst.findall('SERVICE')

    for scomp_child in diaginst.find('SIMPLECOMPCONT'):
        if scomp_child.tag == 'DATAOBJ':
            data_objs.append((scomp_child.find('QUAL').text,
                              scomp_child))
        elif scomp_child.tag == 'DIDDATAREF':
            diddata_refs = did_data_lib[scomp_child.attrib['didRef']].findall('STRUCTURE/DATAOBJ')
            try:
                for diddataref in diddata_refs:
                    data_objs.append((diddataref.find('QUAL').text,
                                      diddataref))
            except KeyError:
                pass
        elif scomp_child.tag == 'STRUCT':
            idref = scomp_child.attrib['dtref']
            if idref in data_types:
                struct_dt = copy.deepcopy(data_types[idref])
                struct_dt.name = scomp_child.find('QUAL').text
                struct_dt.id_ = scomp_child.attrib['oid']

                # dataobj_refs = scomp_child.findall(".")
                for child in scomp_child:  # todo for loop is equal to datatypes - merge
                    if child.tag == 'DATAOBJ':
                        child_idref = child.attrib['dtref']
                        if child_idref in data_types:
                            # struct_dt.sub_elements.append((dataobj_ref.find('NAME/TUV').text, data_types[idref]))
                            struct_dt.sub_elements.append((child.find('QUAL').text, data_types[child_idref]))
                        else:
                            raise ParseError("Unknown STRUCTDT data_object: {}".format(child_idref))
                    elif child.tag == 'GAPDATAOBJ':
                        gapobj = DataType(child.find('QUAL').text,
                                          child.attrib['oid'],
                                          int(child.attrib['bl']),
                                          'uns',
                                          0,
                                          (1 << int(child.attrib['bl'])) - 1,
                                          1,
                                          1,
                                          None,
                                          'big_endian',
                                          None,
                                          1,
                                          0,
                                          1,
                                          'dec',
                                          1,
                                          [])
                        struct_dt.sub_elements.append((child.find('QUAL').text, gapobj))
                        # data_types[child.attrib['oid']] = gapobj
                    else:
                        pass  # nothing to do

                # sub_elements.append((dataobj_ref.find('NAME/TUV').text, data_types[idref]))
                # sub_elements.append((scomp_child.find('QUAL').text, struct_dt))
                data_objs.append((struct_dt.name, struct_dt))
            else:
                raise ParseError("Unknown STRUCTDT/EOSITERDT data_object: {}".format(idref))
        elif scomp_child.tag == 'GAPDATAOBJ':
            # todo not used it seems... delete?
            gapobj = DataType(scomp_child.find('QUAL').text,
                              scomp_child.attrib['oid'],
                              int(scomp_child.attrib['bl']),
                              'uns',
                              0,
                              (1 << int(scomp_child.attrib['bl'])) - 1,
                              1,
                              1,
                              None,
                              'big_endian',
                              None,
                              1,
                              0,
                              1,
                              'dec',
                              1,
                              [])
            data_objs.append(gapobj)
        else:
            pass  # nothing to do

    try:
        for data_obj in data_objs:
            data = _load_data_element(data_obj[1],
                                      data_obj[0],
                                      offset,
                                      data_types)

            if data:
                datas.append(data)
                offset += data.length
    except Exception as e:
        print("nix gut")

    did = None
    if len(datas):
        identifier = int(diaginst.find('STATICVALUE').attrib['v'])
        name = diaginst.find('QUAL').text
        length = (offset + 7) // 8

        did = Did(identifier=identifier,
                  name=name,
                  length=length,
                  datas=datas)

        service_refs = []
        for se in service_elements:
            tmplref_id = se.attrib.get('tmplref', None)
            for ps in protocol_services:
                if tmplref_id in ps.dcl_srv_tmpl:
                    ps.dids.append(did)

    # service.attr['tmplref'] == DCLSRVTMPL.attr['id']
    # DCLSRVTMPL.attr['tmplref'] == PROTOCOLSERVICE.attr['id']
    # PROTOCOLSERVICE/CONSTCOMP.attrib['v'] == SID

    return did


def _load_did_data_refs(ecu_doc: ElementTree.Element) -> Dict[str, ElementTree.Element]:
    """Load DID data references from given ECU doc element. These entries will be then used in the variants.

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
    all_variants = ecu_doc.findall('ECU/VAR')

    # Find the relevant variants
    parse_all_variants = False
    if not diagnostics_variant:  # load all variants if no variant was selected
        parse_all_variants = True

    variants = []
    variant_names = []
    for var in all_variants:
        variant_name = var.find('QUAL').text
        variant_names.append(variant_name)
        if (parse_all_variants == False and
                (diagnostics_variant.lower() != variant_name.lower())):
            continue
        variants.append(var)

    data_types = _load_data_types(ecu_doc)
    did_data_lib = _load_did_data_refs(ecu_doc)

    protocol_services = _load_protocol_services(ecu_doc)
    dids = _load_did_elements(variants, data_types, did_data_lib, protocol_services)
    dtcs = _load_dtc_elements(variants)

    return InternalDatabase(protocol_services=protocol_services, variants=variant_names, dids=dids, dtcs=dtcs)


def _load_did_elements(variants: list, data_types, did_data_lib, protocol_services):
    # var = ecu_doc.findall('ECU')[0].find('VAR')
    dids = []

    # todo - think DIDREF without DIAGCLASS - how to handle
    # todo - think using DIAGCLASS (e.g. Stored Data)
    for var in variants:
        for diag_class in var.findall('DIAGCLASS'):
            for diag_inst in diag_class.findall('DIAGINST'):
                did = _load_did_element(diag_inst,
                                        data_types,
                                        did_data_lib,
                                        protocol_services)
                if did:
                    dids.append(did)
    return dids


def _load_dtc_elements(variants: list):
    """Load all dtcs found in given variant elements.

    """
    dtcs = []

    for var in variants:
        variant_text_id = var.find('QUAL').text

        recorddts = var.findall('DIAGINST/SIMPLECOMPCONT/RECORDDATAOBJ/RECORDDT')
        # todo - parsing multiple RecorDDTs causes duplicate entries - clarify differences of recoreddts

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
                dtc.data_udate({'variant': variant_text_id})
                dtcs.append(dtc)

    return dtcs