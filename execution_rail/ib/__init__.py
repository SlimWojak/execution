"""IB Gateway integration — config, client, paper adapter."""

from execution_rail.ib.config import IBKRConfig, IBKRMode
from execution_rail.ib.paper_adapter import IBPaperAdapter

__all__ = ["IBKRConfig", "IBKRMode", "IBPaperAdapter"]
