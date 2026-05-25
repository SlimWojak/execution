# River Streamer Operations

River live ingest runs in `execution_rail/river/` and writes to `~/phoenix-river/` (historical path name; owned by execution rail).

**Mode grants:** River is observation-only — it does not require a mode promotion grant. Grants apply to the broker rail only (`build_broker`, `supervised_paper_session`).

## Relationship to broker (Brief 3)

Both share IB Gateway on `127.0.0.1:4002` with distinct clientIds:

| Role | clientId | Consumer |
|------|----------|----------|
| RIVER | 1 | `RiverStreamer` |
| BROKER | 2 | `IBPaperAdapter` |
| COO | 3 | MCP inspect |
| DRILL | 99 | `RiverWriter` backfill |

See also [IB_GATEWAY_OPERATIONS.md](./IB_GATEWAY_OPERATIONS.md).

## Three layers of resilience

1. **launchd** `KeepAlive: Crashed=true` — restart streamer on crash
2. **RiverSupervisor** — in-session heartbeat → halt escalation (market-hours gated)
3. **IBC** — Gateway lifecycle (login, daily restart)

## Daily operation

After activation, streamer starts at boot via launchd. Logs: `~/execution/logs/river/streamer.log`.

Heartbeat: `~/phoenix-river/.heartbeat.json` — keys `connected`, `subscribed`, `last_bar_time` consumed by en1gma `LiveRiverReader`.

## Manual operation

```bash
cd ~/execution
source .venv/bin/activate
python scripts/start_river_streamer.py --pair EURUSD --port 4002
# debug without supervisor:
python scripts/start_river_streamer.py --pair EURUSD --no-supervisor
```

## Backfill (historical writer)

```python
from execution_rail.river.writer import RiverWriter
writer = RiverWriter()
writer.capture_all(lookback_days=7)  # uses clientId 99 (DRILL)
```

## Recovery from supervisor halt

Supervisor escalation does **not** auto-clear halt. Inspect heartbeat + Gateway, fix root cause, clear halt manually, restart streamer.

## Forex-day-close seam

At 17:00 NY, staging JSONL consolidates to immutable daily parquet:

```python
from execution_rail.river.seam import consolidate_all_pending
consolidate_all_pending("EURUSD")
```

`INV-RIVER-IMMUTABLE`: existing parquet is never overwritten.

## Activation (launchd)

1. Copy template: `docs/runbooks/river/local.river-streamer.plist.template` → `~/Library/LaunchAgents/com.a8ra.execution-river-streamer.plist`
2. Replace `__HOME__` with your home path (e.g. `/Users/echopeso`)
3. `mkdir -p ~/execution/logs/river`
4. `plutil -lint ~/Library/LaunchAgents/com.a8ra.execution-river-streamer.plist`
5. Validate ≥1h parallel with phoenix streamer before cutover
6. `launchctl load ~/Library/LaunchAgents/com.a8ra.execution-river-streamer.plist`

## Rollback

`launchctl unload` the plist; restart phoenix streamer manually. No data loss — both write same staging dir with dedup.
