from scalper_bot.detectors import (
    build_microstructure_state,
    detect_levels_from_candles,
    detect_patterns,
)
from scalper_bot.models import Candle, OrderbookState


def test_detect_levels_from_candles_returns_levels() -> None:
    candles = [
        Candle(ts_ms=i, open=100 + i, high=101 + (i % 3), low=99 - (i % 2), close=100 + i * 0.1, volume=1000)
        for i in range(40)
    ]
    levels = detect_levels_from_candles(candles, eps=1.5, min_touches=2)
    assert levels
    assert levels[0].touches >= 2


def test_detect_patterns_finds_double_top() -> None:
    candles = []
    price = 100.0
    for i in range(25):
        if i in (10, 18):
            high = 110.0
        else:
            high = price + 1
        low = price - 1
        close = 102.0 if i < 20 else 99.0
        candles.append(Candle(ts_ms=i, open=price, high=high, low=low, close=close, volume=1000))
    patterns = detect_patterns(candles, tolerance_ratio=0.01)
    assert any(p.name == "double_top" for p in patterns)


def test_build_microstructure_state_computes_imbalance_and_ofi() -> None:
    prev = OrderbookState(symbol="BTCUSDT", depth=50, bids={100.0: 10.0}, asks={100.5: 10.0})
    cur = OrderbookState(symbol="BTCUSDT", depth=50, bids={100.1: 15.0}, asks={100.6: 8.0})
    st = build_microstructure_state(cur, prev, hold_above_ms=600, hold_below_ms=0)
    assert st.imbalance_l1 > 0
    assert st.ofi_approx > 0
    assert st.hold_above_ms == 600
