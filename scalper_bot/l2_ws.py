from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .models import OrderbookState, OrderbookUpdate


@dataclass
class L2ApplyResult:
    state: OrderbookState
    is_reset: bool
    reason: str


class L2SequencedBook:
    """Applies Bybit-like snapshot/delta with strict sequence guardrails."""

    def __init__(self, symbol: str, depth: int) -> None:
        self.state = OrderbookState(symbol=symbol, depth=depth)

    def apply(self, update: OrderbookUpdate) -> L2ApplyResult:
        if update.msg_type == "snapshot" or update.u == 1:
            self._reset_from_snapshot(update)
            return L2ApplyResult(state=self.state, is_reset=True, reason="snapshot")

        if self.state.last_u is None:
            self._reset_from_snapshot(update)
            return L2ApplyResult(state=self.state, is_reset=True, reason="delta_without_baseline")

        if update.u <= self.state.last_u:
            return L2ApplyResult(state=self.state, is_reset=False, reason="stale_delta_ignored")

        if update.seq <= (self.state.last_seq or 0):
            return L2ApplyResult(state=self.state, is_reset=False, reason="non_monotonic_seq_ignored")

        self._apply_side(self.state.bids, update.bids)
        self._apply_side(self.state.asks, update.asks)
        self.state.last_u = update.u
        self.state.last_seq = update.seq
        return L2ApplyResult(state=self.state, is_reset=False, reason="delta_applied")

    def _reset_from_snapshot(self, update: OrderbookUpdate) -> None:
        self.state.bids = {p: s for p, s in update.bids if s > 0}
        self.state.asks = {p: s for p, s in update.asks if s > 0}
        self.state.last_u = update.u
        self.state.last_seq = update.seq

    @staticmethod
    def _apply_side(side: dict[float, float], levels: List[Tuple[float, float]]) -> None:
        for price, size in levels:
            if size <= 0:
                side.pop(price, None)
            else:
                side[price] = size
