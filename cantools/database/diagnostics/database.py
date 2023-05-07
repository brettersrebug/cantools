import logging

from typing import List, Dict

from .formats import cdd
from ...compat import fopen
from .internal_database import Variant, DiagnosticGroup
from .dtc import Dtc
from .did import Did


LOGGER = logging.getLogger(__name__)


class Database(object):
    """This class contains all DIDs.

    The factory functions :func:`load()<cantools.database.load()>`,
    :func:`load_file()<cantools.database.load_file()>` and
    :func:`load_string()<cantools.database.load_string()>` returns
    instances of this class.

    """

    def __init__(self,
                 protocol_services=None,
                 variants=None):
        self._name_to_did = {}
        self._identifier_to_did = {}
        self._name_to_dtc = {}
        self._identifier_to_dtc = {}
        self._protocol_services = protocol_services if protocol_services else []
        self._variants:List[Variant] = variants if variants else []
        self._selected_variant:Variant = None
        self.refresh()

    @property
    def dtcs(self) -> List[Dtc]:
        """A list of DTCs in the database.

        """
        return self._selected_variant.dtcs if self._selected_variant else None

    @property
    def protocol_services(self):
        """A list of Protocol services in the database.

        """
        return self._protocol_services

    @property
    def variants(self) -> List[Variant]:
        """A list of available diagnostics variants.

        """
        return self._variants

    def get_available_variant_names(self) -> List[str]:
        variant_names = []
        for var in self.variants:
            variant_names.append(var.name)

        return variant_names

    def get_diagnostics_group_names(self) -> List[str]:
        diag_group_names = []
        for (diag_grp_name, diag_grp) in self._selected_variant.diag_groups.items():
            diag_group_names.append(diag_grp_name)
        return diag_group_names

    def select_variant(self, variant_name:str) -> None:
        i=0
        while (i < len(self.variants)) and (self.variants[i].name != variant_name):
            i+=1

        if i < len(self.variants):
            self._selected_variant = self.variants[i]
        else:
            raise ValueError("Unknown variant name - see variants")

        self.refresh()

    def get_selected_variant_name(self) -> str:
        return self._selected_variant.name

    def get_dids_of_services(self,
                             service_ids:List[int] = [],
                             diagnostics_groups:List[str] = [],
                             did_dict_repr:bool = False) -> Dict[int, list]:
        """A list of DIDs of a given list of service identifiers and diagnostics groups.

        Parameters
        ----------
        service_ids:List[int]
            the protocol service ids to be filtered. If [] or None - all service ids are returned.
        diagnostics_groups:List[str]
            the diagnostics groups to be filtered. If [] or None - no filtering on groups will be performed.

        Returns
        -------
            dict
        """
        dids_filtered = {}

        if service_ids:
            for service_id in service_ids:
                dids_filtered.update({service_id: []})

            for (diag_grp_name, diag_grp) in self._selected_variant.diag_groups.items():
                if not diagnostics_groups or diag_grp_name in diagnostics_groups:
                    for did in diag_grp:
                        for ps in did.protocol_services:
                            if ps.sid in service_ids:
                                if did_dict_repr:
                                    dids_filtered[ps.sid].append({
                                        'name': did.name,
                                        'id': '{}'.format(did.identifier),
                                        'id_hex': '0x{:04X}'.format(did.identifier)})
                                else:
                                    dids_filtered[ps.sid].append(did)
        else:
            for (diag_grp_name, diag_grp)  in self._selected_variant.diag_groups.items():
                if not diagnostics_groups or diag_grp_name in diagnostics_groups:
                    for did in diag_grp:
                        for ps in did.protocol_services:
                            if ps.sid not in dids_filtered:
                                dids_filtered.update({ps.sid: []})
                            if did_dict_repr:
                                dids_filtered[ps.sid].append({
                                    'name': did.name,
                                    'id': '{}'.format(did.identifier),
                                    'id_hex': '0x{:04X}'.format(did.identifier)})
                            else:
                                dids_filtered[ps.sid].append(did)

        return dids_filtered

    def add_cdd(self, fp):
        """Read and parse CDD data from given file-like object and add the
        parsed data to the database.

        """

        self.add_cdd_string(fp.read())

    def add_cdd_file(self, filename, encoding='utf-8'):
        """Open, read and parse CDD data from given file and add the parsed
        data to the database.

        `encoding` specifies the file encoding.

        """

        with fopen(filename, 'r', encoding=encoding) as fin:
            self.add_cdd(fin)

    def add_cdd_string(self, string, diagnostics_variant:str = ''):
        """Parse given CDD data string and add the parsed data to the
        database.

        """
        database = cdd.load_string(string, diagnostics_variant)
        self._protocol_services += database.protocol_services
        self._variants += database.variants
        if len(database.variants) <= 0:
            LOGGER.warning("No diagnostics variant detected in database: %s" % string)

        if diagnostics_variant:
            self.select_variant(variant_name=diagnostics_variant)
        else:
            self.select_variant(variant_name=self._variants[0].name)


    def _add_did(self, did):
        """Add given DID to the database.

        """

        if did.name in self._name_to_did:
            LOGGER.warning("Overwriting DID with name '%s' in the name to DID dictionary.", did.name)

        if did.identifier in self._identifier_to_did:
            LOGGER.warning(
                "Overwriting DID '%s' with '%s' in the identifier to DID "
                "dictionary because they have identical identifiers 0x%x.",
                self._identifier_to_did[did.identifier].name,
                did.name,
                did.identifier)

        self._name_to_did[did.name] = did
        self._identifier_to_did[did.identifier] = did

    def get_did_by_name(self, name):
        """Find the DID object for given name `name`.

        """

        return self._name_to_did.get(name, None)

    def get_did_by_identifier(self, identifier):
        """Find the DID object for given identifier `identifier`.

        """

        return self._identifier_to_did.get(identifier, None)

    def _add_dtc(self, dtc):
        """Add given DTC to the database.

        """

        if dtc.name in self._name_to_dtc:
            LOGGER.warning("Overwriting DTC with name '%s' in the "
                           "name to DTC dictionary.",
                           dtc.name)

        if dtc.identifier in self._identifier_to_dtc:
            LOGGER.warning(
                "Overwriting DTC '%s' with '%s' in the identifier to DTC "
                "dictionary because they have identical identifiers 0x%x.",
                self._identifier_to_dtc[dtc.identifier].name,
                dtc.name,
                dtc.identifier)

        self._name_to_dtc[dtc.name] = dtc
        self._identifier_to_dtc[dtc.identifier] = dtc

    def get_dtc_by_name(self, name):
        """Find the DTC object for given name `name`.

        """

        return self._name_to_dtc.get(name, None)

    def get_dtc_by_identifier(self, identifier):
        """Find the DTC object for given identifier `identifier`.

        """

        return self._identifier_to_dtc.get(identifier, None)

    def refresh(self):
        """Refresh the internal database state.

        This method must be called after modifying any DIDs/DTCs in the
        database to refresh the internal lookup tables used when
        encoding and decoding DIDs.

        """

        self._name_to_did = {}
        self._identifier_to_did = {}

        self._name_to_dtc = {}
        self._identifier_to_dtc = {}

        if self._selected_variant:

            for (diag_grp_name, diag_grp)  in self._selected_variant.diag_groups.items():
                for did in diag_grp:
                    did.refresh()
                    self._add_did(did)

            for dtc in self._selected_variant.dtcs:
                dtc.refresh()
                self._add_dtc(dtc)

    def __repr__(self):
        lines = []

        for did in self._dids:
            lines.append(repr(did))

            for data in did.datas:
                lines.append('  ' + repr(data))

            lines.append('')

        for dtc in self._dtcs:
            lines.append(repr(dtc))

            lines.append('')

        return '\n'.join(lines)
