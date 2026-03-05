from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .detectors import Level


@dataclass(frozen=True)
class ExitPlan:
    side: Literal["Buy", "Sell"]
    entry: float
    stop_loss: float
    take_profit: float
    partial_close_ratio: float
    trailing_distance_pct: float


@dataclass(frozen=True)
class ExitSimulationResult:
    tp_hit: bool
    partial_closed_qty: float
    trailing_activated: bool
    trailing_stop_price: float
    exit_price: float
    reason: str


def _nearest_resistance(levels: Iterable[Level], entry: float) -> float | None:
    higher = sorted([lvl.price for lvl in levels if lvl.price > entry])
    return higher[0] if higher else None


def _nearest_support(levels: Iterable[Level], entry: float) -> float | None:
    lower = sorted([lvl.price for lvl in levels if lvl.price < entry])
    return lower[-1] if lower else None


def build_exit_plan(
    *,
    side: Literal["Buy", "Sell"],
    entry: float,
    stop_loss: float,
    levels: Iterable[Level],
    partial_close_ratio: float,
    trailing_distance_pct: float,
) -> ExitPlan:
    partial_close_ratio = min(1.0, max(0.0, partial_close_ratio))
    trailing_distance_pct = max(0.001, trailing_distance_pct)

    if side == "Buy":
        tp = _nearest_resistance(levels, entry)
        if tp is None:
            rr = abs(entry - stop_loss)
            tp = entry + rr * 1.5
    else:
        tp = _nearest_support(levels, entry)
        if tp is None:
            rr = abs(entry - stop_loss)
            tp = entry - rr * 1.5

    return ExitPlan(
        side=side,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=tp,
        partial_close_ratio=partial_close_ratio,
        trailing_distance_pct=trailing_distance_pct,
    )


def simulate_partial_tp_and_trailing(plan: ExitPlan, total_qty: float, price_path: Iterable[float]) -> ExitSimulationResult:
    prices = list(price_path)
    trailing_active = False
    trailing_stop_price = 0.0
    peak = plan.entry
    partial_closed_qty = 0.0

    for price in prices:
        if plan.side == "Buy":
            if price <= plan.stop_loss:
                return ExitSimulationResult(
                    tp_hit=False,
                    partial_closed_qty=partial_closed_qty,
                    trailing_activated=trailing_active,
                    trailing_stop_price=trailing_stop_price,
                    exit_price=price,
                    reason="stop_loss",
                )
            if not trailing_active and price >= plan.take_profit:
                partial_closed_qty = total_qty * plan.partial_close_ratio
                trailing_active = True
                peak = price
                trailing_stop_price = peak * (1 - plan.trailing_distance_pct)
                continue

            if trailing_active:
                peak = max(peak, price)
                trailing_stop_price = peak * (1 - plan.trailing_distance_pct)
                if price <= trailing_stop_price:
                    return ExitSimulationResult(
                        tp_hit=True,
                        partial_closed_qty=partial_closed_qty,
                        trailing_activated=True,
                        trailing_stop_price=trailing_stop_price,
                        exit_price=price,
                        reason="trailing_stop",
                    )
        else:
            if price >= plan.stop_loss:
                return ExitSimulationResult(
                    tp_hit=False,
                    partial_closed_qty=partial_closed_qty,
                    trailing_activated=trailing_active,
                    trailing_stop_price=trailing_stop_price,
                    exit_price=price,
                    reason="stop_loss",
                )
            if not trailing_active and price <= plan.take_profit:
                partial_closed_qty = total_qty * plan.partial_close_ratio
                trailing_active = True
                peak = price
                trailing_stop_price = peak * (1 + plan.trailing_distance_pct)
                continue

            if trailing_active:
                peak = min(peak, price)
                trailing_stop_price = peak * (1 + plan.trailing_distance_pct)
                if price >= trailing_stop_price:
                    return ExitSimulationResult(
                        tp_hit=True,
                        partial_closed_qty=partial_closed_qty,
                        trailing_activated=True,
                        trailing_stop_price=trailing_stop_price,
                        exit_price=price,
                        reason="trailing_stop",
                    )

    return ExitSimulationResult(
        tp_hit=trailing_active,
        partial_closed_qty=partial_closed_qty,
        trailing_activated=trailing_active,
        trailing_stop_price=trailing_stop_price,
        exit_price=prices[-1] if prices else plan.entry,
        reason="path_end",
    )
