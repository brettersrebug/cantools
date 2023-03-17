# Internal diagnostics database.

class InternalDatabase(object):
    """Internal diagnostics database.

    """

    def __init__(self, protocol_services, dids, dtcs):
        self.protocol_services = protocol_services
        self.dids = dids
        self.dtcs = dtcs
