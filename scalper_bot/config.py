from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv_if_present(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


@dataclass(frozen=True)
class StrategyConfig:
    top_n: int = 10
    candidate_pool: int = 50
    w_volatility: float = 0.4
    w_liquidity: float = 0.4
    w_activity: float = 0.2
    breakout_hold_ms: int = 300
    breakout_buffer_ticks: int = 2
    max_spread_bps: float = 5.0
    imbalance_min: float = 0.2
    ofi_min: float = 0.0
    require_pattern_alignment: bool = True


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float = 0.0025
    max_open_positions: int = 3
    max_total_risk: float = 0.02
    daily_loss_limit: float = 0.03


@dataclass(frozen=True)
class ExchangeConfig:
    category: str = "linear"
    settle_coin: str = "USDT"
    testnet: bool = True
    live_trading: bool = False
    order_type: str = "Market"
    private_ws_enabled: bool = False
    private_ws_url: str = "wss://stream-testnet.bybit.com/v5/private"
    leverage: float = 3.0
    set_leverage_on_start: bool = False


@dataclass(frozen=True)
class RuntimeConfig:
    equity_usdt: float = 10_000.0
    kline_interval: str = "1"
    kline_limit: int = 200
    orderbook_limit: int = 50
    event_store_path: str = "events/bot_events.jsonl"
    log_level: str = "INFO"


@dataclass(frozen=True)
class MonitoringConfig:
    max_avg_slippage_bps: float = 8.0
    max_avg_fill_delay_ms: float = 1500.0
    sentry_dsn: str = ""
    otel_enabled: bool = False


@dataclass(frozen=True)
class ExecutionConfig:
    simulate_fills_in_paper: bool = True
    partial_fill_probability: float = 0.3
    reject_probability: float = 0.02
    tp_partial_close_ratio: float = 0.5
    trailing_distance_pct: float = 0.003


@dataclass(frozen=True)
class BotConfig:
    strategy: StrategyConfig = StrategyConfig()
    risk: RiskConfig = RiskConfig()
    exchange: ExchangeConfig = ExchangeConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    execution: ExecutionConfig = ExecutionConfig()

    @staticmethod
    def from_env() -> "BotConfig":
        _load_dotenv_if_present(os.getenv("BOT_DOTENV_PATH", ".env"))
        testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        default_ws_url = "wss://stream-testnet.bybit.com/v5/private" if testnet else "wss://stream.bybit.com/v5/private"
        return BotConfig(
            exchange=ExchangeConfig(
                category=os.getenv("BYBIT_CATEGORY", "linear"),
                settle_coin=os.getenv("BYBIT_SETTLE_COIN", "USDT"),
                testnet=testnet,
                live_trading=os.getenv("BYBIT_LIVE_TRADING", "false").lower() == "true",
                order_type=os.getenv("BYBIT_ORDER_TYPE", "Market"),
                private_ws_enabled=os.getenv("BYBIT_PRIVATE_WS_ENABLED", "false").lower() == "true",
                private_ws_url=os.getenv("BYBIT_PRIVATE_WS_URL", default_ws_url),
                leverage=float(os.getenv("BYBIT_LEVERAGE", "3")),
                set_leverage_on_start=os.getenv("BYBIT_SET_LEVERAGE_ON_START", "false").lower() == "true",
            ),
            runtime=RuntimeConfig(
                equity_usdt=float(os.getenv("BOT_EQUITY_USDT", "10000")),
                kline_interval=os.getenv("BOT_KLINE_INTERVAL", "1"),
                kline_limit=int(os.getenv("BOT_KLINE_LIMIT", "200")),
                orderbook_limit=int(os.getenv("BOT_ORDERBOOK_LIMIT", "50")),
                event_store_path=os.getenv("BOT_EVENT_STORE_PATH", "events/bot_events.jsonl"),
                log_level=os.getenv("BOT_LOG_LEVEL", "INFO").upper(),
            ),
            monitoring=MonitoringConfig(
                max_avg_slippage_bps=float(os.getenv("BOT_MAX_AVG_SLIPPAGE_BPS", "8")),
                max_avg_fill_delay_ms=float(os.getenv("BOT_MAX_AVG_FILL_DELAY_MS", "1500")),
                sentry_dsn=os.getenv("SENTRY_DSN", ""),
                otel_enabled=os.getenv("OTEL_ENABLED", "false").lower() == "true",
            ),
            execution=ExecutionConfig(
                simulate_fills_in_paper=os.getenv("BOT_SIMULATE_FILLS", "true").lower() == "true",
                partial_fill_probability=float(os.getenv("BOT_PARTIAL_FILL_PROB", "0.3")),
                reject_probability=float(os.getenv("BOT_REJECT_PROB", "0.02")),
                tp_partial_close_ratio=float(os.getenv("BOT_TP_PARTIAL_CLOSE_RATIO", "0.5")),
                trailing_distance_pct=float(os.getenv("BOT_TRAILING_DISTANCE_PCT", "0.003")),
            ),
        )
