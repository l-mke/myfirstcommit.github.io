from scalper_bot.l2_ws import L2SequencedBook
from scalper_bot.models import OrderbookUpdate


def test_l2_sequence_and_stale_delta_guard() -> None:
    book = L2SequencedBook(symbol="BTCUSDT", depth=50)

    snap = OrderbookUpdate(
        symbol="BTCUSDT",
        depth=50,
        msg_type="snapshot",
        u=10,
        seq=100,
        cts_ms=1,
        bids=[(100.0, 1.0)],
        asks=[(100.5, 1.0)],
    )
    res = book.apply(snap)
    assert res.is_reset is True

    delta_ok = OrderbookUpdate(
        symbol="BTCUSDT",
        depth=50,
        msg_type="delta",
        u=11,
        seq=101,
        cts_ms=2,
        bids=[(100.0, 2.0)],
        asks=[(100.5, 1.0)],
    )
    res = book.apply(delta_ok)
    assert res.reason == "delta_applied"
    assert book.state.bids[100.0] == 2.0

    delta_stale = OrderbookUpdate(
        symbol="BTCUSDT",
        depth=50,
        msg_type="delta",
        u=10,
        seq=102,
        cts_ms=3,
        bids=[(100.0, 3.0)],
        asks=[(100.5, 1.0)],
    )
    res = book.apply(delta_stale)
    assert res.reason == "stale_delta_ignored"
    assert book.state.bids[100.0] == 2.0
