from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CircuitBreaker:
    max_spread_bps: float
    max_consecutive_errors: int = 3
    consecutive_errors: int = 0

    def register_success(self) -> None:
        self.consecutive_errors = 0

    def register_error(self) -> None:
        self.consecutive_errors += 1

    def is_tripped(self, current_spread_bps: float) -> bool:
        return current_spread_bps > self.max_spread_bps or self.consecutive_errors >= self.max_consecutive_errors


@dataclass
class KillSwitch:
    max_daily_loss_ratio: float
    max_open_risk_ratio: float

    def should_halt(self, *, equity: float, daily_pnl: float, open_risk: float) -> bool:
        if daily_pnl <= -equity * self.max_daily_loss_ratio:
            return True
        if open_risk >= equity * self.max_open_risk_ratio:
            return True
        return False
