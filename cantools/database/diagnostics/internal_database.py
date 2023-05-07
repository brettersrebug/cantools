# Internal diagnostics database.


class DiagnosticGroup(object):
    def __init__(self, name: str):
        self.name = name
        self.dids = []


class Variant(object):
    def __init__(self, name: str):
        self.name = name
        self.dtcs = []
        self.diag_groups: Dict[DiagnosticGroup] = {}


class InternalDatabase(object):
    """Internal diagnostics database.

    """

    def __init__(self, protocol_services, variants):
        self.protocol_services = protocol_services
        # self.dids = []  # todo remove or ??
        # self.dtcs = []  # todo remove or ??
        self.variants = variants
