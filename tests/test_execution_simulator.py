from scalper_bot.execution import ExecutionSimulator, OrderIntent


def test_execution_simulator_returns_fill_report() -> None:
    sim = ExecutionSimulator(rng_seed=7, reject_probability=0.0, partial_fill_probability=0.0)
    order = OrderIntent(symbol="BTCUSDT", side="Buy", qty=1.0, price=100.0, order_type="Market", time_in_force="IOC")
    report = sim.simulate(order, best_bid=99.9, best_ask=100.1)
    assert report.status == "filled"
    assert report.filled_qty == 1.0
    assert report.fee_paid > 0
    assert report.latency_ms >= sim.min_latency_ms
