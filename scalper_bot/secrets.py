from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretBundle:
    bybit_api_key: str
    bybit_api_secret: str
    sentry_dsn: str


class EnvSecretsProvider:
    def load(self) -> SecretBundle:
        return SecretBundle(
            bybit_api_key=os.getenv("BYBIT_API_KEY", ""),
            bybit_api_secret=os.getenv("BYBIT_API_SECRET", ""),
            sentry_dsn=os.getenv("SENTRY_DSN", ""),
        )


def redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}***{value[-3:]}"
