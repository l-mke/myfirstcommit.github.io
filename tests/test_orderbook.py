from scalper_bot.models import OrderbookUpdate
from scalper_bot.orderbook import OrderbookAggregator


def test_snapshot_and_delta_application() -> None:
    agg = OrderbookAggregator()

    snapshot = OrderbookUpdate(
        symbol="BTCUSDT",
        depth=50,
        msg_type="snapshot",
        u=10,
        seq=100,
        cts_ms=1,
        bids=[(100.0, 1.0), (99.5, 2.0)],
        asks=[(100.5, 1.5), (101.0, 3.0)],
    )
    state = agg.apply(snapshot)
    assert state.bid1 == (100.0, 1.0)
    assert state.ask1 == (100.5, 1.5)
    assert round(state.spread_bps, 3) == round(((100.5 - 100.0) / 100.25) * 10_000, 3)

    delta = OrderbookUpdate(
        symbol="BTCUSDT",
        depth=50,
        msg_type="delta",
        u=11,
        seq=101,
        cts_ms=2,
        bids=[(100.0, 0.0), (99.8, 4.0)],
        asks=[(100.5, 2.5)],
    )
    state = agg.apply(delta)

    assert state.bid1 == (99.8, 4.0)
    assert state.asks[100.5] == 2.5
