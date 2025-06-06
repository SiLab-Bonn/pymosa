from constellation.core.configuration import Configuration
from constellation.core.satellite import Satellite
import time
from constellation.core.commandmanager import cscp_requestable
from constellation.core.cscp import CSCPMessage
from constellation.core.cmdp import MetricsType
from bdaq53.scans.scan_ext_trigger import ExtTriggerScan
import threading

class Pymosa(Satellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_initializing(self, config: Configuration) -> None:
        return "init done"

    def do_launching(self):
        return "launching done"

    def do_run(self, payload=None) -> None:
        return "running done"
