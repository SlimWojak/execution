# Brief 4 prep — MODULE.RIVER_IBKR_STREAMER (draft)

**Status:** PREP ONLY — execute after Brief 3 shipped + Gateway stable.

## Mission

Lift `phoenix/river/streamer.py` `reqHistoricalData` bar streaming into `execution_rail/river/`. Uses `allocate_client_id(ClientIdRole.RIVER)` — consumes Brief 3 allocator.

## Why next (COO recommendation)

- Direct continuation of pipeline framing (River stops depending on phoenix-river upstream)
- Broker chain becomes self-contained with RIVER=1 + BROKER=2 multiplex
- Unblocks ATOM bar ingest without Dukascopy-only path for live tail

## Target shape (lean)

```
execution_rail/river/
├── streamer.py      # ib_insync reqHistoricalData (second ib importer OR shared session — TBD)
├── config.py        # stream symbols, bar size, pacing
└── health.py        # stream lag / last bar timestamp
```

## Open decisions for Brief 4 YAML

1. **Second ib_insync importer?** Brief 2 invariant says sole importer in `real_client.py`. Streamer likely shares connection factory or extends `real_client` with read-only historical methods — do not duplicate import.
2. **Dukascopy vs IB:** RiverWriter stays construction substrate; IB streamer is live tail complement — document boundary.
3. **MCP inspect:** extend `inspect(runtime, domain=river)` or new sub-view `scope.view=stream`?

## Prerequisites

- [x] Brief 3 clientId allocator (RIVER=1)
- [ ] IBC Layer 1 activated on prod machine
- [ ] Brief 3 supervisor stable on first PAPER session

## Source lift

- `phoenix/river/streamer.py`
- Phoenix-river upstream service (identify exact entrypoint during brief authoring)
