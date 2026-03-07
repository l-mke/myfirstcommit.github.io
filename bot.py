"""Production-oriented Bybit scalper entrypoint with monitoring/safety layers."""

from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Dict, List

from scalper_bot.bybit_client import BybitRESTClient
from scalper_bot.config import BotConfig
from scalper_bot.detectors import build_microstructure_state, detect_levels_from_candles, detect_patterns
from scalper_bot.event_store import JsonlEventStore
from scalper_bot.execution import ExecutionSimulator, OrderIntent, PaperExecutor
from scalper_bot.exits import build_exit_plan, simulate_partial_tp_and_trailing
from scalper_bot.features import CoinSelector
from scalper_bot.l2_ws import L2SequencedBook
from scalper_bot.metrics import AlertEngine, AlertThresholds, ExecutionQualityMonitor, ExecutionSample
from scalper_bot.models import Candle, OrderbookUpdate, Ticker24h
from scalper_bot.observability import MetricsRegistry, init_otel, init_sentry, setup_logger
from scalper_bot.private_ws import PrivateStreamManager, PrivateWSConfig
from scalper_bot.risk import RiskManager
from scalper_bot.safeguards import CircuitBreaker, KillSwitch
from scalper_bot.secrets import EnvSecretsProvider, redact
from scalper_bot.strategy import StrategyCore


def _sample_tickers() -> List[Ticker24h]:
    return [
        Ticker24h("BTCUSDT", 70500, 68100, 1_200_000_000, 20000, 69000, 69000.5),
        Ticker24h("ETHUSDT", 3800, 3600, 800_000_000, 35000, 3700, 3700.3),
        Ticker24h("SOLUSDT", 190, 170, 600_000_000, 45000, 178.2, 178.25),
    ]


def _sample_candles(mid: float) -> List[Candle]:
    candles: List[Candle] = []
    base = mid * 0.99
    for i in range(200):
        drift = (i % 9 - 4) * 0.0004 * mid
        close = base + i * 0.0002 * mid + drift
        candles.append(
            Candle(
                ts_ms=1_700_000_000_000 + i * 60_000,
                open=close * 0.999,
                high=close * 1.0015,
                low=close * 0.9985,
                close=close,
                volume=1000 + i * 5,
            )
        )
    return candles


def _hold_ms_for_level(candles: List[Candle], level: float, candle_ms: int = 60_000) -> tuple[int, int]:
    above = 0
    below = 0
    for c in reversed(candles):
        if c.close > level:
            if below:
                break
            above += candle_ms
        elif c.close < level:
            if above:
                break
            below += candle_ms
        else:
            break
    return above, below


def _parse_snapshot_to_update(symbol: str, depth: int, snapshot: Dict[str, object]) -> OrderbookUpdate:
    result = snapshot.get("result", {}) if isinstance(snapshot, dict) else {}
    bids_raw = result.get("b", []) if isinstance(result, dict) else []
    asks_raw = result.get("a", []) if isinstance(result, dict) else []

    bids = [(float(p), float(s)) for p, s in bids_raw]
    asks = [(float(p), float(s)) for p, s in asks_raw]

    return OrderbookUpdate(
        symbol=symbol,
        depth=depth,
        msg_type="snapshot",
        u=int(result.get("u", 1)),
        seq=int(result.get("seq", 0)),
        cts_ms=int(result.get("cts", 0)),
        bids=bids,
        asks=asks,
    )


def _start_private_stream_if_enabled(cfg: BotConfig, event_store: JsonlEventStore) -> PrivateStreamManager | None:
    if not cfg.exchange.private_ws_enabled:
        return None

    secrets = EnvSecretsProvider().load()
    if not secrets.bybit_api_key or not secrets.bybit_api_secret:
        event_store.append("warning", {"reason": "private ws enabled but api creds missing"})
        return None

    manager = PrivateStreamManager(
        PrivateWSConfig(url=cfg.exchange.private_ws_url, api_key=secrets.bybit_api_key, api_secret=secrets.bybit_api_secret)
    )
    manager.on("order", lambda msg: event_store.append("private.order", msg))
    manager.on("position", lambda msg: event_store.append("private.position", msg))
    manager.on("execution", lambda msg: event_store.append("private.execution", msg))
    manager.start()
    event_store.append("private_ws", {"status": "started", "url": cfg.exchange.private_ws_url})
    return manager


def run_once(live: bool = False, replay: bool = False) -> None:
    cfg = BotConfig.from_env()
    log_level = getattr(logging, cfg.runtime.log_level, logging.INFO)
    logger = setup_logger(level=log_level)
    secrets = EnvSecretsProvider().load()

    if cfg.monitoring.otel_enabled:
        init_otel("scalper_bot")
    init_sentry(cfg.monitoring.sentry_dsn)

    event_store = JsonlEventStore(cfg.runtime.event_store_path)
    metrics = MetricsRegistry()

    if replay:
        logger.info("Replay mode enabled, reading events from %s", cfg.runtime.event_store_path)
        count = event_store.replay(lambda e: print({"ts_ms": e.ts_ms, "topic": e.topic, "payload": e.payload}))
        logger.info("Replay complete: %s events", count)
        print({"replay_events": count})
        return

    logger.info("Starting bot (live=%s, api_key=%s)", live, redact(secrets.bybit_api_key))
    logger.info("Config summary: testnet=%s symbol_settle=%s interval=%s orderbook_limit=%s", cfg.exchange.testnet, cfg.exchange.settle_coin, cfg.runtime.kline_interval, cfg.runtime.orderbook_limit)

    client = BybitRESTClient.from_env()
    selector = CoinSelector(cfg.strategy.w_volatility, cfg.strategy.w_liquidity, cfg.strategy.w_activity)
    alerts = AlertEngine()
    monitor = ExecutionQualityMonitor()
    circuit_breaker = CircuitBreaker(max_spread_bps=cfg.strategy.max_spread_bps)

    risk = RiskManager(
        cfg.runtime.equity_usdt,
        cfg.risk.risk_per_trade,
        cfg.risk.max_open_positions,
        cfg.risk.max_total_risk,
        cfg.risk.daily_loss_limit,
    )
    kill_switch = KillSwitch(max_daily_loss_ratio=cfg.risk.daily_loss_limit, max_open_risk_ratio=cfg.risk.max_total_risk)

    ws_manager = _start_private_stream_if_enabled(cfg, event_store) if live else None

    try:
        try:
            tickers = [t for t in client.get_tickers(cfg.exchange.category) if t.symbol.endswith(cfg.exchange.settle_coin)]
            logger.info("Loaded tickers from Bybit: %s", len(tickers))
        except Exception as exc:
            logger.warning("Tickers unavailable, using local fallback: %s", exc)
            event_store.append("warning", {"reason": f"tickers unavailable: {exc}"})
            tickers = _sample_tickers()
            metrics.inc("fallback_tickers")

        if not tickers:
            raise RuntimeError("No instruments available for selection")

        candidates = sorted(tickers, key=lambda t: t.turnover_24h, reverse=True)[: cfg.strategy.candidate_pool]
        trade_counts_proxy = {t.symbol: int(max(1.0, t.volume_24h)) for t in candidates}
        ranked = selector.rank(candidates, trade_counts_proxy, top_n=cfg.strategy.top_n)
        symbol = ranked[0].symbol
        logger.info("Selected symbol=%s score=%.4f from %s candidates", symbol, ranked[0].score, len(candidates))
        event_store.append("selection", {"symbol": symbol, "score": ranked[0].score})

        ticker = next(t for t in candidates if t.symbol == symbol)
        mid_hint = (ticker.bid1 + ticker.ask1) / 2 if ticker.bid1 and ticker.ask1 else max(ticker.low_price_24h, 1.0)

        try:
            candles = client.get_kline(
                category=cfg.exchange.category,
                symbol=symbol,
                interval=cfg.runtime.kline_interval,
                limit=cfg.runtime.kline_limit,
            )
            logger.info("Loaded candles from Bybit: %s", len(candles))
        except Exception as exc:
            logger.warning("Klines unavailable, using local fallback: %s", exc)
            event_store.append("warning", {"reason": f"kline unavailable: {exc}"})
            candles = _sample_candles(mid_hint)
            metrics.inc("fallback_kline")

        if len(candles) < 20:
            candles = _sample_candles(mid_hint)
            metrics.inc("fallback_kline_short")

        levels = detect_levels_from_candles(candles, eps=max(candles[-1].close * 0.001, 0.5), min_touches=3)
        patterns = detect_patterns(candles)
        logger.info("Signal context: levels=%s patterns=%s", len(levels), [p.name for p in patterns])
        event_store.append("signal.context", {"levels": len(levels), "patterns": [p.name for p in patterns]})

        if not levels:
            logger.info("Skip run: no levels detected")
            print("No levels detected; skip")
            return

        hold_above_ms, hold_below_ms = _hold_ms_for_level(candles, levels[0].price)

        l2 = L2SequencedBook(symbol=symbol, depth=cfg.runtime.orderbook_limit)
        try:
            snap1 = client.get_orderbook_snapshot(category=cfg.exchange.category, symbol=symbol, limit=cfg.runtime.orderbook_limit)
            update1 = _parse_snapshot_to_update(symbol, cfg.runtime.orderbook_limit, snap1)
            l2.apply(update1)

            time.sleep(0.25)
            snap2 = client.get_orderbook_snapshot(category=cfg.exchange.category, symbol=symbol, limit=cfg.runtime.orderbook_limit)
            update2 = _parse_snapshot_to_update(symbol, cfg.runtime.orderbook_limit, snap2)
            # convert second snapshot top-level differences to synthetic delta for sequence checks
            prev_bid = l2.state.bid1[1] if l2.state.bid1 else 0.0
            prev_ask = l2.state.ask1[1] if l2.state.ask1 else 0.0
            bid_price = update2.bids[0][0] if update2.bids else 0.0
            ask_price = update2.asks[0][0] if update2.asks else 0.0
            bid_size = update2.bids[0][1] if update2.bids else 0.0
            ask_size = update2.asks[0][1] if update2.asks else 0.0
            delta = OrderbookUpdate(
                symbol=symbol,
                depth=cfg.runtime.orderbook_limit,
                msg_type="delta",
                u=max((l2.state.last_u or 0) + 1, update2.u),
                seq=max((l2.state.last_seq or 0) + 1, update2.seq),
                cts_ms=update2.cts_ms,
                bids=[(bid_price, bid_size if bid_size != prev_bid else prev_bid)],
                asks=[(ask_price, ask_size if ask_size != prev_ask else prev_ask)],
            )
            l2.apply(delta)
            circuit_breaker.register_success()
            logger.info("Orderbook ready: bid1=%s ask1=%s spread_bps=%.3f", l2.state.bid1, l2.state.ask1, l2.state.spread_bps)
        except Exception as exc:
            logger.warning("Orderbook unavailable, using synthetic fallback: %s", exc)
            event_store.append("warning", {"reason": f"orderbook unavailable: {exc}"})
            circuit_breaker.register_error()
            metrics.inc("fallback_orderbook")
            current_mid = candles[-1].close
            tick = max(current_mid * 0.0001, 0.0001)
            l2.apply(
                OrderbookUpdate(
                    symbol=symbol,
                    depth=cfg.runtime.orderbook_limit,
                    msg_type="snapshot",
                    u=1,
                    seq=1,
                    cts_ms=1,
                    bids=[(current_mid - tick, 10.0)],
                    asks=[(current_mid + tick, 10.0)],
                )
            )
            l2.apply(
                OrderbookUpdate(
                    symbol=symbol,
                    depth=cfg.runtime.orderbook_limit,
                    msg_type="delta",
                    u=2,
                    seq=2,
                    cts_ms=2,
                    bids=[(current_mid - tick, 13.0)],
                    asks=[(current_mid + tick, 8.0)],
                )
            )

        micro = build_microstructure_state(l2.state, l2.state, hold_above_ms=hold_above_ms, hold_below_ms=hold_below_ms)
        logger.info(
            "Microstructure: mid=%.6f spread_bps=%.3f imbalance=%.3f ofi=%.3f hold_above=%sms hold_below=%sms",
            micro.mid,
            micro.spread_bps,
            micro.imbalance_l1,
            micro.ofi_approx,
            micro.hold_above_ms,
            micro.hold_below_ms,
        )
        metrics.set_gauge("spread_bps", micro.spread_bps)

        if circuit_breaker.is_tripped(micro.spread_bps):
            event_store.append("halt", {"reason": "circuit breaker tripped", "spread_bps": micro.spread_bps})
            logger.warning("Circuit breaker tripped: spread_bps=%.3f max=%.3f", micro.spread_bps, cfg.strategy.max_spread_bps)
            print("Circuit breaker tripped; halt")
            return

        if kill_switch.should_halt(equity=risk.equity, daily_pnl=risk.daily_pnl, open_risk=risk.open_risk):
            event_store.append("halt", {"reason": "kill switch", "daily_pnl": risk.daily_pnl, "open_risk": risk.open_risk})
            logger.warning("Kill switch tripped: daily_pnl=%.4f open_risk=%.4f", risk.daily_pnl, risk.open_risk)
            print("Kill switch halted trading")
            return

        signal = StrategyCore(cfg.strategy).generate(symbol, levels, micro, patterns)
        logger.info("Signal generated: kind=%s reason=%s", signal.kind, signal.reason)
        event_store.append("signal", {"kind": signal.kind, "reason": signal.reason})

        if not signal.kind.startswith("breakout"):
            logger.info("No trade opened: %s", signal.reason)
            print({"signal": signal.kind, "reason": signal.reason, "patterns": [p.name for p in patterns]})
            return

        side = "Buy" if signal.kind.endswith("long") else "Sell"
        entry = micro.mid
        stop = entry * (0.999 if side == "Buy" else 1.001)
        qty, risk_usdt = risk.size_position(entry, stop)
        logger.info("Risk sizing: side=%s entry=%.6f stop=%.6f qty=%.6f risk_usdt=%.4f", side, entry, stop, qty, risk_usdt)
        if not risk.can_trade(risk_usdt):
            event_store.append("blocked", {"reason": "risk manager"})
            logger.warning("Risk manager blocked order: risk_usdt=%.4f", risk_usdt)
            print("Risk limits blocked order")
            return

        qty_str = f"{max(0.001, qty):.3f}"

        exit_plan = build_exit_plan(
            side=side,
            entry=entry,
            stop_loss=stop,
            levels=levels,
            partial_close_ratio=cfg.execution.tp_partial_close_ratio,
            trailing_distance_pct=cfg.execution.trailing_distance_pct,
        )
        event_store.append(
            "exit.plan",
            {
                "symbol": symbol,
                "side": side,
                "take_profit": exit_plan.take_profit,
                "stop_loss": exit_plan.stop_loss,
                "partial_ratio": exit_plan.partial_close_ratio,
                "trailing_distance_pct": exit_plan.trailing_distance_pct,
            },
        )
        logger.info(
            "Exit plan: tp=%.6f sl=%.6f partial=%.2f trailing_distance_pct=%.4f",
            exit_plan.take_profit,
            exit_plan.stop_loss,
            exit_plan.partial_close_ratio,
            exit_plan.trailing_distance_pct,
        )

        created_ts = int(time.time() * 1000)

        if live:
            if not cfg.exchange.live_trading:
                raise RuntimeError("Live mode requested but BYBIT_LIVE_TRADING is false")

            if cfg.exchange.set_leverage_on_start:
                lev = f"{cfg.exchange.leverage:.2f}"
                lev_resp = client.set_leverage(
                    category=cfg.exchange.category,
                    symbol=symbol,
                    buy_leverage=lev,
                    sell_leverage=lev,
                )
                event_store.append("leverage.set", {"symbol": symbol, "leverage": lev, "response": lev_resp})
                logger.info("Leverage set: symbol=%s leverage=%s", symbol, lev)

            result = client.place_order(
                category=cfg.exchange.category,
                symbol=symbol,
                side=side,
                qty=qty_str,
                order_type=cfg.exchange.order_type,
            )
            event_store.append("order.live", {"symbol": symbol, "side": side, "qty": qty_str, "response": result})
            logger.info("Live order submitted: symbol=%s side=%s qty=%s", symbol, side, qty_str)
            print({"mode": "live", "signal": signal.kind, "symbol": symbol, "side": side, "qty": qty_str, "exchange": result})
            # conservative assumption in live path
            simulated_fill_price = entry
            simulated_latency = int(time.time() * 1000) - created_ts
            filled_qty = float(qty_str)
            fee_paid = filled_qty * simulated_fill_price * 0.00055
            status = "filled"
        else:
            order = OrderIntent(symbol=symbol, side=side, qty=float(qty_str), price=entry, order_type="Market", time_in_force="IOC")
            paper_result = PaperExecutor().submit(order)
            sim = ExecutionSimulator(
                partial_fill_probability=cfg.execution.partial_fill_probability,
                reject_probability=cfg.execution.reject_probability,
            )
            fill = sim.simulate(order, best_bid=l2.state.bid1[0], best_ask=l2.state.ask1[0])
            event_store.append("order.paper", {"symbol": symbol, "side": side, "qty": qty_str, "fill_status": fill.status, "fee": fill.fee_paid})
            logger.info("Paper order simulated: status=%s filled_qty=%.6f avg_price=%.6f fee=%.6f", fill.status, fill.filled_qty, fill.avg_fill_price, fill.fee_paid)
            print({"mode": "paper", "signal": signal.kind, "symbol": symbol, "side": side, "qty": qty_str, "paper": paper_result, "fill": fill})
            simulated_fill_price = fill.avg_fill_price if fill.avg_fill_price > 0 else entry
            simulated_latency = fill.latency_ms
            filled_qty = fill.filled_qty
            fee_paid = fill.fee_paid
            status = fill.status

        filled_ts = int(time.time() * 1000)
        sample = ExecutionSample(symbol=symbol, expected_price=entry, filled_price=simulated_fill_price, created_ts_ms=created_ts, filled_ts_ms=max(filled_ts, created_ts + simulated_latency))
        monitor.add(sample)

        metrics.inc("orders_total")
        if status == "partial":
            metrics.inc("orders_partial")
        elif status == "rejected":
            metrics.inc("orders_rejected")

        event_store.append("execution", {"symbol": symbol, "status": status, "filled_qty": filled_qty, "fee_paid": fee_paid, "latency_ms": simulated_latency})
        logger.info("Execution stats: status=%s filled_qty=%.6f fee=%.6f latency_ms=%s", status, filled_qty, fee_paid, simulated_latency)

        # Partial TP + trailing-stop lifecycle simulation based on recent/future-like path
        path = [c.close for c in candles[-30:]]
        if side == "Buy":
            path.extend([entry * 1.002, exit_plan.take_profit * 1.001, exit_plan.take_profit * 1.004, exit_plan.take_profit * (1 - cfg.execution.trailing_distance_pct * 1.1)])
        else:
            path.extend([entry * 0.998, exit_plan.take_profit * 0.999, exit_plan.take_profit * 0.996, exit_plan.take_profit * (1 + cfg.execution.trailing_distance_pct * 1.1)])

        exit_result = simulate_partial_tp_and_trailing(exit_plan, total_qty=filled_qty, price_path=path)
        event_store.append(
            "exit.result",
            {
                "symbol": symbol,
                "tp_hit": exit_result.tp_hit,
                "partial_closed_qty": exit_result.partial_closed_qty,
                "trailing_activated": exit_result.trailing_activated,
                "trailing_stop_price": exit_result.trailing_stop_price,
                "exit_price": exit_result.exit_price,
                "reason": exit_result.reason,
            },
        )
        logger.info(
            "Exit simulation: tp_hit=%s partial_closed=%.6f trailing=%s exit_price=%s reason=%s",
            exit_result.tp_hit,
            exit_result.partial_closed_qty,
            exit_result.trailing_activated,
            exit_result.exit_price,
            exit_result.reason,
        )

        alert_msgs = alerts.evaluate(
            monitor,
            AlertThresholds(
                max_avg_slippage_bps=cfg.monitoring.max_avg_slippage_bps,
                max_avg_fill_delay_ms=cfg.monitoring.max_avg_fill_delay_ms,
            ),
        )
        for message in alert_msgs:
            event_store.append("alert", {"message": message})
            print(f"ALERT: {message}")

        logger.info("Run complete metrics=%s", {"counters": metrics.counters, "gauges": metrics.gauges})
    finally:
        if ws_manager:
            ws_manager.stop()
            event_store.append("private_ws", {"status": "stopped"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="place order via Bybit REST")
    parser.add_argument("--replay", action="store_true", help="replay stored events from event store")
    args = parser.parse_args()
    run_once(live=args.live, replay=args.replay)


if __name__ == "__main__":
    main()
