# River launchd templates

| File | Purpose |
|------|---------|
| `local.river-streamer.plist.template` | launchd unit for `scripts/start_river_streamer.py` |

**Install:** copy to `~/Library/LaunchAgents/`, replace `__HOME__` with machine home path, lint with `plutil -lint`, then `launchctl load`.

Full activation protocol (parallel cutover gates): [`../RIVER_OPERATIONS.md`](../RIVER_OPERATIONS.md).
