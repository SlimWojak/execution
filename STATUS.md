# Execution Rail — STATUS

| Field | Value |
|---|---|
| Version | 0.2.0 |
| Brief 1 | BROKER_ADAPTER — Protocol + factory ✓ |
| Brief 2 | IB_PAPER_ADAPTER — IBPaperAdapter + ib/ package ✓ |
| Broker | PaperBroker (TEST/SHADOW), IBPaperAdapter (PAPER) |
| IB wired | Yes — port 4002 paper via ib_insync |
| Tests | 23 unit/contract (+ 2 integration env-gated) |

## Layout

```
execution_rail/
├── broker_protocol.py / broker_factory.py / broker_adapter.py
├── position.py / halt_types.py / mode.py / gateway.py
└── ib/
    ├── config.py          IBKRConfig + guards
    ├── orders.py          IBOrder types
    ├── positions.py       IBPosition types
    ├── account.py         AccountState
    ├── real_client.py     sole ib_insync importer
    └── paper_adapter.py   IBPaperAdapter
```

## Activation

PAPER mode requires IB Gateway on `127.0.0.1:4002` and `.env` per `.env.example`.

Drills (manual, against live Gateway):
```bash
python drills/ib_paper_validation.py
python drills/ib_paper_roundtrip.py
```

Integration tests (env-gated):
```bash
IBKR_INTEGRATION_TEST=1 pytest tests/integration/ -m integration
```

## en1gma integration

Not wired yet. Import from `execution_rail` when orchestrator brief lands.
