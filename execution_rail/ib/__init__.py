"""IB Gateway integration — config, client, paper adapter, supervisor."""

from execution_rail.ib.client_id import ClientIdRole, allocate_client_id
from execution_rail.ib.config import IBKRConfig, IBKRMode, ReconnectTracker
from execution_rail.ib.paper_adapter import IBPaperAdapter
from execution_rail.ib.supervisor import IBKRSupervisor, SupervisorWatchdog, create_ibkr_supervisor

__all__ = [
    "IBKRConfig",
    "IBKRMode",
    "IBPaperAdapter",
    "IBKRSupervisor",
    "SupervisorWatchdog",
    "ClientIdRole",
    "allocate_client_id",
    "ReconnectTracker",
    "create_ibkr_supervisor",
]
