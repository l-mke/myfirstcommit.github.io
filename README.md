# Bybit Scalper Bot (production-oriented)

Теперь бот включает прод-операционные слои, которые вы запросили:

- полноценный L2 модуль с контролем последовательности snapshot/delta (`L2SequencedBook`),
- расширенная модель исполнения (partial fill / fees / latency),
- observability hooks (метрики, logger, Sentry/OTel init),
- private WS manager с reconnect,
- event store + replay,
- kill-switch/circuit-breaker safeguards,
- deployment notes + runbook + secret-management рекомендации.

## Что уже работает

- Выбор инструментов top-N по волатильности/ликвидности/активности.
- Реальные market tickers (`/v5/market/tickers`).
- Реальные свечи (`/v5/market/kline`) для уровней/паттернов.
- Реальный snapshot стакана (`/v5/market/orderbook`) для микро-фич.
- Breakout вход с фильтрами: imbalance/OFI/spread/pattern alignment.
- Risk manager и default paper execution.
- Live order placement (`/v5/order/create`) при `--live` + `BYBIT_LIVE_TRADING=true`.
- Event store в `events/bot_events.jsonl` и `--replay`.

## Быстрый запуск

```bash
python3 bot.py
```

## Replay событий

```bash
python3 bot.py --replay
```

## Live (сначала testnet)

```bash
export BYBIT_TESTNET=true
export BYBIT_LIVE_TRADING=true
export BYBIT_API_KEY="..."
export BYBIT_API_SECRET="..."
python3 bot.py --live
```

## Переменные окружения

- `BYBIT_API_KEY` / `BYBIT_API_SECRET` — private endpoints.
- `BYBIT_TESTNET` — `true|false` (default `true`).
- `BYBIT_LIVE_TRADING` — `true|false` (default `false`).
- `BYBIT_CATEGORY` — `linear` (default).
- `BYBIT_SETTLE_COIN` — `USDT` (default).
- `BYBIT_ORDER_TYPE` — `Market`/`Limit`.
- `BYBIT_PRIVATE_WS_ENABLED` — `true|false` (default `false`).
- `BYBIT_PRIVATE_WS_URL` — URL private WS.
- `BYBIT_LEVERAGE` — целевое плечо (например `3`).
- `BYBIT_SET_LEVERAGE_ON_START` — `true|false`, выставлять плечо перед live-ордером.

- `BOT_EQUITY_USDT`
- `BOT_KLINE_INTERVAL`, `BOT_KLINE_LIMIT`
- `BOT_ORDERBOOK_LIMIT`
- `BOT_EVENT_STORE_PATH`
- `BOT_MAX_AVG_SLIPPAGE_BPS`
- `BOT_MAX_AVG_FILL_DELAY_MS`
- `BOT_SIMULATE_FILLS`
- `BOT_PARTIAL_FILL_PROB`
- `BOT_REJECT_PROB`
- `SENTRY_DSN`
- `OTEL_ENABLED`

## Тесты

```bash
python3 -m pytest -q
```

## Деплой и runbook

- `deploy/README.md` — deployment + secret management.
- `deploy/RUNBOOK.md` — incident runbook.
