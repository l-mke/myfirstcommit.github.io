from pathlib import Path

from scalper_bot.event_store import JsonlEventStore
from scalper_bot.metrics import AlertEngine, AlertThresholds, ExecutionQualityMonitor, ExecutionSample
from scalper_bot.safeguards import CircuitBreaker, KillSwitch


def test_event_store_append_and_replay(tmp_path: Path) -> None:
    store = JsonlEventStore(str(tmp_path / "events.jsonl"))
    store.append("signal", {"kind": "flat"})
    store.append("order", {"qty": "1.0"})

    got = []
    count = store.replay(lambda e: got.append(e.topic))
    assert count == 2
    assert got == ["signal", "order"]


def test_metrics_alerts() -> None:
    monitor = ExecutionQualityMonitor()
    monitor.add(ExecutionSample("BTCUSDT", expected_price=100, filled_price=101, created_ts_ms=0, filled_ts_ms=2000))

    alerts = AlertEngine().evaluate(monitor, AlertThresholds(max_avg_slippage_bps=20, max_avg_fill_delay_ms=1000))
    assert any("fill-delay" in a for a in alerts)


def test_kill_switch_and_circuit_breaker() -> None:
    ks = KillSwitch(max_daily_loss_ratio=0.03, max_open_risk_ratio=0.02)
    assert ks.should_halt(equity=10000, daily_pnl=-400, open_risk=100)

    cb = CircuitBreaker(max_spread_bps=5.0, max_consecutive_errors=2)
    cb.register_error()
    cb.register_error()
    assert cb.is_tripped(current_spread_bps=1.0)
