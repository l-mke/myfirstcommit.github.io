from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Deque, Dict, Iterable, List

from .models import Ticker24h, Trade


@dataclass
class ScoreRow:
    symbol: str
    volatility: float
    liquidity: float
    activity: float
    score: float


def parkinson_volatility(high: float, low: float) -> float:
    import math

    if high <= 0 or low <= 0 or high <= low:
        return 0.0
    return (math.log(high / low) ** 2) / (4 * math.log(2))


def z_norm(values: Iterable[float]) -> List[float]:
    values = list(values)
    if not values:
        return []
    mu = mean(values)
    sigma = pstdev(values)
    if sigma == 0:
        return [0.0 for _ in values]
    return [(v - mu) / sigma for v in values]


class TradeCounter24h:
    def __init__(self) -> None:
        self._trades: Dict[str, Deque[int]] = defaultdict(deque)

    def on_trade(self, trade: Trade) -> None:
        bucket = self._trades[trade.symbol]
        bucket.append(trade.ts_ms)
        cutoff = trade.ts_ms - 24 * 60 * 60 * 1000
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def get_count(self, symbol: str) -> int:
        return len(self._trades[symbol])


class CoinSelector:
    def __init__(self, w_vol: float, w_liq: float, w_act: float) -> None:
        self.w_vol = w_vol
        self.w_liq = w_liq
        self.w_act = w_act

    def rank(self, tickers: List[Ticker24h], trade_counts: Dict[str, int], top_n: int) -> List[ScoreRow]:
        import math

        raw = []
        for t in tickers:
            raw.append(
                (
                    t.symbol,
                    parkinson_volatility(t.high_price_24h, t.low_price_24h),
                    math.log1p(max(0.0, t.turnover_24h)),
                    math.log1p(max(0, trade_counts.get(t.symbol, 0))),
                )
            )

        z_vol = z_norm([r[1] for r in raw])
        z_liq = z_norm([r[2] for r in raw])
        z_act = z_norm([r[3] for r in raw])

        rows = []
        for i, (symbol, vol, liq, act) in enumerate(raw):
            score = self.w_vol * z_vol[i] + self.w_liq * z_liq[i] + self.w_act * z_act[i]
            rows.append(ScoreRow(symbol=symbol, volatility=vol, liquidity=liq, activity=act, score=score))

        return sorted(rows, key=lambda r: r.score, reverse=True)[:top_n]
