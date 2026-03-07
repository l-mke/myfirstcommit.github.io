from scalper_bot.observability import MetricsRegistry
from scalper_bot.secrets import redact


def test_metrics_registry_basic() -> None:
    m = MetricsRegistry()
    m.inc("orders", 2)
    m.inc("orders")
    m.set_gauge("spread", 1.2)
    assert m.counters["orders"] == 3
    assert m.gauges["spread"] == 1.2


def test_redact_secret() -> None:
    assert redact("") == ""
    assert redact("abcdefghi") == "abc***ghi"
