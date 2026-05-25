# IB Gateway Operations — Gateway + Supervisor Resilience

## Layer model

| Layer | Owner | Problem solved |
|-------|-------|----------------|
| **1 — IBC + launchd** | `~/ibc/` | Gateway dead, not logged in, daily IB restart |
| **2 — IBKRSupervisor** | `execution_rail/ib/` | Gateway up but broker API connection silent |
| **2b — RiverSupervisor** | `execution_rail/river/` | Gateway up but bar stream silent (market-hours gated) |
| **3 — launchd KeepAlive** | river streamer plist | Streamer process crash restart |

Layers 1 + 2 are required for broker. River adds 2b + 3. See `INV-IB-TWO-LAYER-RESILIENCE` (extended to River in Brief 4).

## clientId allocation

| Role | ID | Consumer |
|------|-----|----------|
| RIVER | 1 | `river/streamer.py` — live bars |
| BROKER | 2 | `ib/paper_adapter.py` — orders |
| COO | 3 | Constellation MCP inspect |
| DRILL | 99 | `river/writer.py`, manual drills |

## Layer 1 — IBC activation (manual)

1. Backup: `cp -r ~/ibc ~/ibc.bak.$(date +%Y-%m-%d)`
2. Store password in keychain (never in config.ini):
   ```bash
   security add-generic-password -a "$USER" -s ibkr_paper -w '<password>'
   ```
3. Apply templates from `docs/runbooks/ibc/` — set `$HOME` paths for your machine
4. Validate plist: `plutil -lint ~/ibc/local.ibc-gateway.plist`
5. Stop manual Gateway: `bash ~/ibc/stop.sh`
6. Load plist: `launchctl load ~/ibc/local.ibc-gateway.plist`
7. Start: `launchctl start com.a8ra.ibkr-gateway` (or your chosen label — must match `check_gateway.sh`)
8. Verify: `bash ~/ibc/check_gateway.sh`

**Known defects fixed by templates:**
- Plaintext `IbPassword` → blank + keychain wrapper
- `/Users/user/` placeholder paths → `$HOME`
- Label mismatch between plist and `check_gateway.sh`
- Missing `Hour` in schedule → `Hour=6` NY-local

## Layer 2 — Supervisor (code)

```python
from execution_rail.halt_types import LocalHaltSignal
from execution_rail.ib.session import supervised_paper_session

halt = LocalHaltSignal()
with supervised_paper_session(halt, on_alert=print) as (adapter, sup, wd):
    ...
```

**Policy:** heartbeat recovery does **not** auto-clear halt. Operator inspects state and clears manually.

## Phase 1.5 — Grant PAPER mode (required before broker build)

```bash
cd ~/execution
python run.py --grant-mode PAPER --reason "initial paper cutover" --grantor "<your name>"
python run.py --list-grants --mode PAPER     # confirm written
```

Without this grant, `build_broker(PAPER, ...)` raises `ModePromotionError`. Factory enforces regardless of caller — no bypass (`INV-MODE-PROMOTION-REQUIRED`).

## Drills

```bash
cd ~/execution
python drills/ib_paper_validation.py
python drills/ib_paper_roundtrip.py
```

## River streamer (Brief 4)

River shares this Gateway on clientId=1. Activation and parallel cutover: [`RIVER_OPERATIONS.md`](./RIVER_OPERATIONS.md).

## Rollback

- **Code:** revert Brief 3 commit — supervisor dormant, adapter works without pulses
- **IBC:** restore from backup; `launchctl unload ~/ibc/local.ibc-gateway.plist`
- **River:** `launchctl unload` streamer plist; restart phoenix streamer manually
