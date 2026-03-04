from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import List


@dataclass
class ExecutionSample:
    symbol: str
    expected_price: float
    filled_price: float
    created_ts_ms: int
    filled_ts_ms: int

    @property
    def slippage_bps(self) -> float:
        if self.expected_price <= 0:
            return 0.0
        return abs(self.filled_price - self.expected_price) / self.expected_price * 10_000

    @property
    def fill_delay_ms(self) -> int:
        return max(0, self.filled_ts_ms - self.created_ts_ms)


@dataclass
class ExecutionQualityMonitor:
    samples: List[ExecutionSample] = field(default_factory=list)

    def add(self, sample: ExecutionSample) -> None:
        self.samples.append(sample)

    @property
    def avg_slippage_bps(self) -> float:
        if not self.samples:
            return 0.0
        return mean(s.slippage_bps for s in self.samples)

    @property
    def avg_fill_delay_ms(self) -> float:
        if not self.samples:
            return 0.0
        return mean(s.fill_delay_ms for s in self.samples)


@dataclass(frozen=True)
class AlertThresholds:
    max_avg_slippage_bps: float = 8.0
    max_avg_fill_delay_ms: float = 1500.0


class AlertEngine:
    def evaluate(self, monitor: ExecutionQualityMonitor, thresholds: AlertThresholds) -> list[str]:
        alerts: list[str] = []
        if monitor.avg_slippage_bps > thresholds.max_avg_slippage_bps:
            alerts.append(f"slippage alert: avg={monitor.avg_slippage_bps:.2f}bps")
        if monitor.avg_fill_delay_ms > thresholds.max_avg_fill_delay_ms:
            alerts.append(f"fill-delay alert: avg={monitor.avg_fill_delay_ms:.0f}ms")
        return alerts
