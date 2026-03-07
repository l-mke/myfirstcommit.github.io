from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class OrderIntent:
    symbol: str
    side: Literal["Buy", "Sell"]
    qty: float
    price: float
    order_type: Literal["Limit", "Market"] = "Limit"
    time_in_force: str = "PostOnly"


@dataclass
class FillReport:
    symbol: str
    requested_qty: float
    filled_qty: float
    avg_fill_price: float
    fee_paid: float
    latency_ms: int
    status: Literal["filled", "partial", "rejected"]


@dataclass
class PaperExecutor:
    """Simple execution stub used for dry-runs and tests."""

    def submit(self, order: OrderIntent) -> dict:
        return {
            "retCode": 0,
            "retMsg": "OK",
            "order": order,
        }


@dataclass
class ExecutionSimulator:
    """Expanded execution model: partial fills, fees, and synthetic latency."""

    fee_bps_maker: float = 2.0
    fee_bps_taker: float = 5.5
    min_latency_ms: int = 20
    max_latency_ms: int = 120
    partial_fill_probability: float = 0.3
    reject_probability: float = 0.02
    rng_seed: Optional[int] = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.rng_seed)

    def simulate(self, order: OrderIntent, best_bid: float, best_ask: float) -> FillReport:
        latency_ms = self._rng.randint(self.min_latency_ms, self.max_latency_ms)
        time.sleep(latency_ms / 1000.0)

        if self._rng.random() < self.reject_probability:
            return FillReport(
                symbol=order.symbol,
                requested_qty=order.qty,
                filled_qty=0.0,
                avg_fill_price=0.0,
                fee_paid=0.0,
                latency_ms=latency_ms,
                status="rejected",
            )

        fill_ratio = 1.0
        status: Literal["filled", "partial", "rejected"] = "filled"
        if self._rng.random() < self.partial_fill_probability:
            fill_ratio = self._rng.uniform(0.2, 0.95)
            status = "partial"

        filled_qty = order.qty * fill_ratio

        if order.order_type == "Market":
            base_price = best_ask if order.side == "Buy" else best_bid
            slippage_bps = self._rng.uniform(0.0, 3.5)
            if order.side == "Buy":
                avg_fill = base_price * (1 + slippage_bps / 10_000)
            else:
                avg_fill = base_price * (1 - slippage_bps / 10_000)
            fee_bps = self.fee_bps_taker
        else:
            avg_fill = order.price
            fee_bps = self.fee_bps_maker

        notional = filled_qty * avg_fill
        fee_paid = notional * fee_bps / 10_000

        return FillReport(
            symbol=order.symbol,
            requested_qty=order.qty,
            filled_qty=filled_qty,
            avg_fill_price=avg_fill,
            fee_paid=fee_paid,
            latency_ms=latency_ms,
            status=status,
        )
