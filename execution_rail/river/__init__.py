"""River ingest — IBKR live streamer, historical writer, schema, seam.

Only schema helpers are re-exported here so importing execution_rail.river stays
free of IB runtime side effects. Import streamer/writer/supervisor directly.
"""

from .schema import (
    CANONICAL_PAIRS,
    NEX_SOURCE_BOUNDARY,
    RAW_BAR_SCHEMA,
    RAW_COLUMNS,
    VALID_SOURCES,
    compute_bar_hashes,
    get_river_root,
    validate_raw_bars,
)

__all__ = [
    "CANONICAL_PAIRS",
    "NEX_SOURCE_BOUNDARY",
    "RAW_BAR_SCHEMA",
    "RAW_COLUMNS",
    "VALID_SOURCES",
    "compute_bar_hashes",
    "get_river_root",
    "validate_raw_bars",
]
