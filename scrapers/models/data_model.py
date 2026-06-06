from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class ProviderResult:
    """Single provider's rate data for one corridor — matches Platform Exchange Metrics UML.

    Both fees and transfer_time are keyed by payment method so callers can compare
    like-for-like across providers (e.g. bank vs. debit card).

    Standard method keys: "bank", "debit_card", "credit_card", "cash_pickup", "mobile_money"
    """

    provider: str
    corridor: str                    # "USD-BDT"
    send_amount: Decimal
    exchange_rate: Decimal           # FX rate — same for all payment methods
    fees: dict[str, Decimal]         # {"bank": Decimal("0.00"), "debit_card": Decimal("2.99")}
    transfer_time: dict[str, str]    # {"bank": "2 days", "debit_card": "instantly"}
    receive_amount: Optional[Decimal]  # for the primary/cheapest method; None if unknown
    scraped_at: str                  # ISO 8601 UTC

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "corridor": self.corridor,
            "send_amount": str(self.send_amount),
            "exchange_rate": str(self.exchange_rate),
            "fees": {k: str(v) for k, v in self.fees.items()},
            "transfer_time": self.transfer_time,
            "receive_amount": str(self.receive_amount) if self.receive_amount is not None else None,
            "scraped_at": self.scraped_at,
        }


@dataclass
class ScrapeRun:
    """One full scrape run for a corridor — wraps all ProviderResults and errors."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    corridor: str = ""
    send_amount: Decimal = Decimal("0")
    started_at: str = ""
    completed_at: str = ""
    results: list[ProviderResult] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "corridor": self.corridor,
            "send_amount": str(self.send_amount),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "results": [r.to_dict() for r in self.results],
            "errors": self.errors,
        }
