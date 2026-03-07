from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple


Side = Literal["Buy", "Sell"]


@dataclass
class Ticker24h:
    symbol: str
    high_price_24h: float
    low_price_24h: float
    turnover_24h: float
    volume_24h: float
    bid1: float
    ask1: float


@dataclass
class Candle:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    symbol: str
    ts_ms: int
    price: float
    size: float
    side: Side


@dataclass
class OrderbookUpdate:
    symbol: str
    depth: int
    msg_type: Literal["snapshot", "delta"]
    u: int
    seq: int
    cts_ms: int
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]


@dataclass
class OrderbookState:
    symbol: str
    depth: int
    bids: Dict[float, float] = field(default_factory=dict)
    asks: Dict[float, float] = field(default_factory=dict)
    last_u: Optional[int] = None
    last_seq: Optional[int] = None

    @property
    def bid1(self) -> Optional[Tuple[float, float]]:
        if not self.bids:
            return None
        p = max(self.bids)
        return p, self.bids[p]

    @property
    def ask1(self) -> Optional[Tuple[float, float]]:
        if not self.asks:
            return None
        p = min(self.asks)
        return p, self.asks[p]

    @property
    def mid(self) -> Optional[float]:
        if self.bid1 is None or self.ask1 is None:
            return None
        return (self.bid1[0] + self.ask1[0]) / 2

    @property
    def spread_bps(self) -> float:
        if self.bid1 is None or self.ask1 is None:
            return 999.0
        mid = self.mid
        if not mid or mid <= 0:
            return 999.0
        return ((self.ask1[0] - self.bid1[0]) / mid) * 10_000


@dataclass
class Signal:
    symbol: str
    kind: Literal["breakout_long", "breakout_short", "bounce_long", "bounce_short", "flat"]
    confidence: float
    reason: str


@dataclass
class Position:
    symbol: str
    side: Literal["long", "short"]
    qty: float
    entry: float
    stop: float
    risk_usdt: float
