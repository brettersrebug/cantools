import logging

from .formats import cdd
from ...compat import fopen


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
                 dids=None,
                 dtcs=None):
        self._name_to_did = {}
        self._identifier_to_did = {}
		self._protocol_services = protocol_services if protocol_services else []
        self._dids = dids if dids else []
        self.refresh()

    @property
    def dids(self):
        """A list of DIDs in the database.

        """
        return self._dids

    @property
    def dtcs(self):
        """A list of DTCs in the database.

        """

        return self._dtcs

    @property
    def protcol_services(self):
        """A list of Protocol services in the database.

        """
        return self._protocol_services

    def get_dids_of_services(self, service_ids:list = [])->dict:
        """A list of DIDs of a given list of service identifiers.

        """
        dids_filtered = {}

        if service_ids:
            for service_id in service_ids:
                dids_filtered.update({service_id: []})
                for ps in self._protocol_services:
                    if ps.sid == service_id:
                        dids_filtered[service_id] += ps.dids
        else:
            for ps in self._protocol_services:
                dids_filtered.update({ps.sid:[]})
                dids_filtered[ps.sid] += ps.dids

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
        self._protocol_services = database.protocol_services
        self._dids = database.dids
        self._dtcs = database.dtcs
        self.refresh()

    def _add_did(self, did):
        """Add given DID to the database.

        """

        if did.name in self._name_to_did:
            LOGGER.warning("Overwriting DID with name '%s' in the "
                           "name to DID dictionary.",
                           did.name)

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

        This method must be called after modifying any DIDs in the
        database to refresh the internal lookup tables used when
        encoding and decoding DIDs.

        """

        self._name_to_did = {}
        self._identifier_to_did = {}

        for did in self._dids:
            did.refresh()
            self._add_did(did)

    def __repr__(self):
        lines = []

        for did in self._dids:
            lines.append(repr(did))

            for data in did.datas:
                lines.append('  ' + repr(data))

            lines.append('')

        return '\n'.join(lines)
