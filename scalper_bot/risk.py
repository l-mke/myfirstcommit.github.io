from dataclasses import dataclass


@dataclass
class RiskManager:
    equity: float
    risk_per_trade: float
    max_open_positions: int
    max_total_risk: float
    daily_loss_limit: float
    daily_pnl: float = 0.0
    open_risk: float = 0.0
    open_positions: int = 0

    def can_trade(self, new_risk_usdt: float) -> bool:
        if self.daily_pnl <= -self.equity * self.daily_loss_limit:
            return False
        if self.open_positions >= self.max_open_positions:
            return False
        if (self.open_risk + new_risk_usdt) > self.equity * self.max_total_risk:
            return False
        return True

    def size_position(self, entry: float, stop: float) -> tuple[float, float]:
        risk_budget = self.equity * self.risk_per_trade
        distance = abs(entry - stop)
        if distance <= 0:
            return 0.0, 0.0
        qty = risk_budget / distance
        return qty, risk_budget
