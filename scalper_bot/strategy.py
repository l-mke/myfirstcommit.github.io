from dataclasses import dataclass
from typing import List

from .config import StrategyConfig
from .detectors import Level, MicrostructureState, Pattern, breakout
from .models import Signal


@dataclass
class StrategyCore:
    cfg: StrategyConfig

    def generate(self, symbol: str, levels: List[Level], micro: MicrostructureState, patterns: List[Pattern]) -> Signal:
        pattern_biases = {p.bias for p in patterns}

        for lvl in levels:
            long_ok = breakout(
                lvl,
                "up",
                micro,
                self.cfg.breakout_buffer_ticks,
                self.cfg.breakout_hold_ms,
                self.cfg.imbalance_min,
                self.cfg.ofi_min,
                self.cfg.max_spread_bps,
            )
            short_ok = breakout(
                lvl,
                "down",
                micro,
                self.cfg.breakout_buffer_ticks,
                self.cfg.breakout_hold_ms,
                self.cfg.imbalance_min,
                self.cfg.ofi_min,
                self.cfg.max_spread_bps,
            )

            if long_ok:
                if self.cfg.require_pattern_alignment and ("short" in pattern_biases and "long" not in pattern_biases):
                    return Signal(symbol=symbol, kind="flat", confidence=0.0, reason="Breakout long filtered by bearish pattern")
                return Signal(symbol=symbol, kind="breakout_long", confidence=0.8, reason=f"Breakout over {lvl.price}")

            if short_ok:
                if self.cfg.require_pattern_alignment and ("long" in pattern_biases and "short" not in pattern_biases):
                    return Signal(symbol=symbol, kind="flat", confidence=0.0, reason="Breakout short filtered by bullish pattern")
                return Signal(symbol=symbol, kind="breakout_short", confidence=0.8, reason=f"Breakdown below {lvl.price}")

        return Signal(symbol=symbol, kind="flat", confidence=0.0, reason="No valid setup")
