"""
IBKR configuration — paper guards and mode management.

Lifted from: phoenix/brokers/ibkr/config.py (ReconnectTracker deferred)

INVARIANTS:
  INV-IBKR-PAPER-GUARD-1
  INV-IBKR-ACCOUNT-CHECK-1
  INV-IBKR-CONFIG-1
  INV-IBKR-PAPER-PORT-CONTRACT
  INV-IBKR-CLIENT-ID-ALLOCATION (default clientId=2 for broker)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IBKRMode(str, Enum):
    MOCK = "MOCK"
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass
class ReconnectConfig:
    """Reconnect policy — config only; runtime tracker deferred to supervisor brief."""

    max_attempts: int = 3
    backoff_delays: tuple[float, ...] = (5.0, 15.0, 45.0)
    max_time_sec: float = 65.0


@dataclass
class IBKRConfig:
    host: str = "127.0.0.1"
    client_id: int = 2
    timeout: float = 30.0
    readonly: bool = False
    mode: IBKRMode = IBKRMode.MOCK
    port: int = 4002
    expected_account_prefix: str = "DU"
    allow_live: bool = False
    fill_timeout_sec: float = 30.0
    reconnect: ReconnectConfig = field(default_factory=ReconnectConfig)

    PAPER_PORT: int = field(default=4002, init=False)
    LIVE_PORT: int = field(default=4001, init=False)

    @classmethod
    def from_env(cls) -> IBKRConfig:
        mode_str = os.getenv("IBKR_MODE", "mock").upper()
        mode = IBKRMode(mode_str) if mode_str in {m.value for m in IBKRMode} else IBKRMode.MOCK

        config = cls(
            host=os.getenv("IBKR_HOST", "127.0.0.1"),
            port=int(os.getenv("IBKR_PORT", "4002")),
            client_id=int(os.getenv("IBKR_CLIENT_ID", "2")),
            mode=mode,
            allow_live=os.getenv("IBKR_ALLOW_LIVE", "false").lower() == "true",
            fill_timeout_sec=float(os.getenv("IBKR_FILL_TIMEOUT_SEC", "30")),
        )
        config._set_mode_defaults()
        return config

    def _set_mode_defaults(self) -> None:
        if self.mode == IBKRMode.MOCK:
            self.expected_account_prefix = "DU"
        elif self.mode == IBKRMode.PAPER:
            self.port = self.PAPER_PORT
            self.expected_account_prefix = "DU"
        elif self.mode == IBKRMode.LIVE:
            self.port = self.LIVE_PORT
            self.expected_account_prefix = "U"

    def validate_startup(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if self.mode == IBKRMode.LIVE and not self.allow_live:
            errors.append(
                "INV-IBKR-PAPER-GUARD-1: Live mode requires IBKR_ALLOW_LIVE=true"
            )
        if self.mode == IBKRMode.PAPER and self.port != self.PAPER_PORT:
            errors.append(
                f"Port mismatch: PAPER mode expects port {self.PAPER_PORT}, got {self.port}"
            )
        if self.mode == IBKRMode.LIVE and self.port != self.LIVE_PORT:
            errors.append(
                f"Port mismatch: LIVE mode expects port {self.LIVE_PORT}, got {self.port}"
            )
        return (len(errors) == 0, errors)

    def validate_account(self, account_id: str) -> tuple[bool, str | None]:
        if self.mode == IBKRMode.MOCK:
            return (True, None)
        if not account_id.startswith(self.expected_account_prefix):
            return (
                False,
                f"INV-IBKR-ACCOUNT-CHECK-1: Account {account_id} doesn't match "
                f"expected prefix {self.expected_account_prefix} for {self.mode.value} mode",
            )
        return (True, None)

    def validate_order_context(
        self, account_id: str, current_port: int
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        account_valid, account_error = self.validate_account(account_id)
        if not account_valid and account_error:
            errors.append(account_error)
        expected_port = self.PAPER_PORT if self.mode == IBKRMode.PAPER else self.LIVE_PORT
        if self.mode != IBKRMode.MOCK and current_port != expected_port:
            errors.append(
                f"INV-IBKR-ACCOUNT-CHECK-1: Port {current_port} doesn't match "
                f"expected {expected_port} for {self.mode.value} mode"
            )
        return (len(errors) == 0, errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "mode": self.mode.value,
            "allow_live": self.allow_live,
            "expected_account_prefix": self.expected_account_prefix,
            "fill_timeout_sec": self.fill_timeout_sec,
        }
