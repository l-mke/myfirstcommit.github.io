from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .models import OrderbookState, OrderbookUpdate


@dataclass
class OrderbookAggregator:
    books: Dict[str, OrderbookState] = field(default_factory=dict)

    def apply(self, update: OrderbookUpdate) -> OrderbookState:
        state = self.books.get(update.symbol)
        if state is None:
            state = OrderbookState(symbol=update.symbol, depth=update.depth)
            self.books[update.symbol] = state

        if update.msg_type == "snapshot" or update.u == 1:
            state.bids = {p: s for p, s in update.bids if s > 0}
            state.asks = {p: s for p, s in update.asks if s > 0}
        else:
            self._apply_side(state.bids, update.bids)
            self._apply_side(state.asks, update.asks)

        state.last_u = update.u
        state.last_seq = update.seq
        return state

    @staticmethod
    def _apply_side(side: Dict[float, float], levels: list[tuple[float, float]]) -> None:
        for price, size in levels:
            if size == 0:
                side.pop(price, None)
            else:
                side[price] = size
