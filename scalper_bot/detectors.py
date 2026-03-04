from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import Candle, OrderbookState


@dataclass
class Level:
    price: float
    band: float
    touches: int
    strength: float
    kind: str


@dataclass
class Pattern:
    name: str
    bias: str  # long/short/neutral
    confidence: float


@dataclass
class MicrostructureState:
    mid: float
    imbalance_l1: float
    ofi_approx: float
    spread_bps: float
    hold_above_ms: int
    hold_below_ms: int


def _pivots(values: List[float], window: int = 2, kind: str = "high") -> List[float]:
    if len(values) < window * 2 + 1:
        return values[:]
    out: List[float] = []
    for i in range(window, len(values) - window):
        chunk = values[i - window : i + window + 1]
        center = values[i]
        if kind == "high" and center == max(chunk):
            out.append(center)
        if kind == "low" and center == min(chunk):
            out.append(center)
    return out


def detect_horizontal_levels(prices: List[float], eps: float, min_touches: int = 3) -> List[Level]:
    if not prices:
        return []
    sorted_prices = sorted(prices)
    clusters: List[List[float]] = []
    current = [sorted_prices[0]]

    for p in sorted_prices[1:]:
        if abs(p - current[-1]) <= eps:
            current.append(p)
        else:
            clusters.append(current)
            current = [p]
    clusters.append(current)

    levels = []
    for c in clusters:
        if len(c) >= min_touches:
            level = c[len(c) // 2]
            levels.append(Level(price=level, band=eps, touches=len(c), strength=float(len(c)), kind="horizontal"))
    return sorted(levels, key=lambda l: l.strength, reverse=True)


def detect_levels_from_candles(candles: List[Candle], eps: float, min_touches: int = 3) -> List[Level]:
    highs = _pivots([c.high for c in candles], kind="high")
    lows = _pivots([c.low for c in candles], kind="low")
    return detect_horizontal_levels(highs + lows, eps=eps, min_touches=min_touches)


def detect_patterns(candles: List[Candle], tolerance_ratio: float = 0.002) -> List[Pattern]:
    if len(candles) < 20:
        return []
    closes = [c.close for c in candles]
    highs = _pivots([c.high for c in candles], kind="high")
    lows = _pivots([c.low for c in candles], kind="low")
    patterns: List[Pattern] = []

    if len(highs) >= 2:
        p1, p2 = highs[-2], highs[-1]
        if abs(p1 - p2) / max(p1, 1.0) <= tolerance_ratio and closes[-1] < min(p1, p2):
            patterns.append(Pattern(name="double_top", bias="short", confidence=0.65))

    if len(lows) >= 2:
        p1, p2 = lows[-2], lows[-1]
        if abs(p1 - p2) / max(p1, 1.0) <= tolerance_ratio and closes[-1] > max(p1, p2):
            patterns.append(Pattern(name="double_bottom", bias="long", confidence=0.65))

    if len(highs) >= 3 and len(lows) >= 3:
        high_slope = highs[-1] - highs[-3]
        low_slope = lows[-1] - lows[-3]
        if high_slope < 0 < low_slope:
            patterns.append(Pattern(name="sym_triangle", bias="neutral", confidence=0.55))
        elif abs(high_slope) < abs(low_slope) * 0.3 and low_slope > 0:
            patterns.append(Pattern(name="asc_triangle", bias="long", confidence=0.6))
        elif high_slope < 0 and abs(low_slope) < abs(high_slope) * 0.3:
            patterns.append(Pattern(name="desc_triangle", bias="short", confidence=0.6))

    return patterns


def build_microstructure_state(
    current: OrderbookState,
    previous: OrderbookState | None,
    hold_above_ms: int,
    hold_below_ms: int,
) -> MicrostructureState:
    if current.bid1 is None or current.ask1 is None:
        return MicrostructureState(mid=0.0, imbalance_l1=0.0, ofi_approx=0.0, spread_bps=999.0, hold_above_ms=0, hold_below_ms=0)

    bid_price, bid_size = current.bid1
    ask_price, ask_size = current.ask1
    mid = (bid_price + ask_price) / 2
    spread_bps = ((ask_price - bid_price) / mid) * 10_000 if mid > 0 else 999.0
    denom = bid_size + ask_size
    imbalance_l1 = (bid_size - ask_size) / denom if denom > 0 else 0.0

    ofi_approx = 0.0
    if previous and previous.bid1 and previous.ask1:
        prev_bid_size = previous.bid1[1]
        prev_ask_size = previous.ask1[1]
        ofi_approx = (bid_size - prev_bid_size) - (ask_size - prev_ask_size)

    return MicrostructureState(
        mid=mid,
        imbalance_l1=imbalance_l1,
        ofi_approx=ofi_approx,
        spread_bps=spread_bps,
        hold_above_ms=hold_above_ms,
        hold_below_ms=hold_below_ms,
    )


def breakout(
    level: Level,
    side: str,
    st: MicrostructureState,
    buffer_ticks: float,
    hold_ms: int,
    min_imbalance: float,
    min_ofi: float,
    max_spread_bps: float,
) -> bool:
    if side == "up":
        return (
            st.mid > level.price + buffer_ticks
            and st.hold_above_ms >= hold_ms
            and st.imbalance_l1 >= min_imbalance
            and st.ofi_approx >= min_ofi
            and st.spread_bps <= max_spread_bps
        )
    return (
        st.mid < level.price - buffer_ticks
        and st.hold_below_ms >= hold_ms
        and st.imbalance_l1 <= -min_imbalance
        and st.ofi_approx <= -min_ofi
        and st.spread_bps <= max_spread_bps
    )
