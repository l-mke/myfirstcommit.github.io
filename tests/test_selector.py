from scalper_bot.features import CoinSelector
from scalper_bot.models import Ticker24h


def test_selector_returns_top_n() -> None:
    selector = CoinSelector(0.4, 0.4, 0.2)
    tickers = [
        Ticker24h("A", 120, 100, 100_000, 500, 1, 1.1),
        Ticker24h("B", 220, 180, 900_000, 1500, 2, 2.1),
        Ticker24h("C", 80, 70, 500_000, 1200, 3, 3.1),
    ]

    top = selector.rank(tickers, {"A": 1000, "B": 2000, "C": 500}, top_n=2)
    assert len(top) == 2
    assert top[0].symbol in {"B", "C"}
