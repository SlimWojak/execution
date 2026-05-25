# IB Gateway Operations — Two-Layer Resilience

## Layer model

| Layer | Owner | Problem solved |
|-------|-------|----------------|
| **1 — IBC + launchd** | OS process | Gateway dead, not logged in, daily IB restart |
| **2 — IBKRSupervisor** | execution_rail (in-process) | Gateway up but API connection silent |

Neither layer alone is sufficient. See `INV-IB-TWO-LAYER-RESILIENCE`.

## clientId allocation

| Role | ID | Consumer |
|------|-----|----------|
| RIVER | 1 | Brief 4 streamer |
| BROKER | 2 | IBPaperAdapter |
| COO | 3 | Constellation MCP inspect |
| DRILL | 99 | Manual validation scripts |

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

## Drills

```bash
cd ~/execution
python drills/ib_paper_validation.py
python drills/ib_paper_roundtrip.py
```

## Rollback

- **Code:** revert Brief 3 commit — supervisor dormant, adapter works without pulses
- **IBC:** restore from backup; `launchctl unload ~/ibc/local.ibc-gateway.plist`
