from scalper_bot.detectors import Level
from scalper_bot.exits import build_exit_plan, simulate_partial_tp_and_trailing


def test_build_exit_plan_uses_nearest_resistance_for_long() -> None:
    levels = [
        Level(price=99.0, band=0.5, touches=3, strength=3.0, kind="horizontal"),
        Level(price=101.0, band=0.5, touches=3, strength=3.0, kind="horizontal"),
        Level(price=103.0, band=0.5, touches=3, strength=3.0, kind="horizontal"),
    ]
    plan = build_exit_plan(side="Buy", entry=100.0, stop_loss=99.0, levels=levels, partial_close_ratio=0.5, trailing_distance_pct=0.003)
    assert plan.take_profit == 101.0


def test_partial_tp_then_trailing_stop_for_long() -> None:
    levels = [Level(price=101.0, band=0.5, touches=3, strength=3.0, kind="horizontal")]
    plan = build_exit_plan(side="Buy", entry=100.0, stop_loss=99.0, levels=levels, partial_close_ratio=0.4, trailing_distance_pct=0.01)
    result = simulate_partial_tp_and_trailing(plan, total_qty=10.0, price_path=[100.2, 101.2, 102.0, 100.9])
    assert result.tp_hit is True
    assert result.trailing_activated is True
    assert result.partial_closed_qty == 4.0
    assert result.reason == "trailing_stop"
