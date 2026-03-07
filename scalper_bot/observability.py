from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("scalper_bot")
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


@dataclass
class MetricsRegistry:
    counters: Dict[str, float] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)

    def inc(self, name: str, value: float = 1.0) -> None:
        self.counters[name] = self.counters.get(name, 0.0) + value

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = value


def init_sentry(dsn: str | None) -> bool:
    if not dsn:
        return False
    try:
        import sentry_sdk  # type: ignore

        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.1)
        return True
    except Exception:
        return False


def init_otel(service_name: str = "scalper_bot") -> bool:
    try:
        from opentelemetry import trace  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        trace.set_tracer_provider(provider)
        return True
    except Exception:
        return False
