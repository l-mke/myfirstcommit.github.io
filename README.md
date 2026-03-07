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
cp .env.example .env
# заполните ключи/параметры в .env
python3 bot.py
```

После запуска вы увидите пошаговые логи в терминале: выбор символа, загрузка свечей/стакана, метрики микроструктуры, причину сигнала/блокировки, размер позиции, план выхода (TP/trailing), результат исполнения.

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

Ниже — **все параметры**, которые бот читает из окружения (`.env` или `export ...`).

### 1) Биржа и режим торговли

| Параметр | По умолчанию | Что делает |
|---|---:|---|
| `BYBIT_API_KEY` | `""` | API key для приватных методов (ордера, плечо, private WS). |
| `BYBIT_API_SECRET` | `""` | API secret для подписи приватных запросов. |
| `BYBIT_TESTNET` | `true` | Переключает testnet/mainnet endpoint. Для старта держите `true`. |
| `BYBIT_LIVE_TRADING` | `false` | Защита от случайной реальной торговли. Для live должно быть `true` **и** запуск с `--live`. |
| `BYBIT_CATEGORY` | `linear` | Категория рынка Bybit (обычно linear для USDT perpetual). |
| `BYBIT_SETTLE_COIN` | `USDT` | Фильтр инструментов по монете расчёта (например, `BTCUSDT`, `ETHUSDT`). |
| `BYBIT_ORDER_TYPE` | `Market` | Тип ордера (`Market`/`Limit`) при отправке live заявки. |
| `BYBIT_PRIVATE_WS_ENABLED` | `false` | Включает private WS стримы (ордера/позиции/исполнения). |
| `BYBIT_PRIVATE_WS_URL` | auto by testnet/mainnet | URL private WebSocket (можно переопределить вручную). |
| `BYBIT_LEVERAGE` | `3` | Целевое плечо для инструмента. |
| `BYBIT_SET_LEVERAGE_ON_START` | `false` | Если `true`, бот перед live-ордером вызовет `set-leverage` на бирже. |

### 2) Runtime и источники данных

| Параметр | По умолчанию | Что делает |
|---|---:|---|
| `BOT_EQUITY_USDT` | `10000` | Виртуальный размер капитала для риск-менеджера (расчёт размера позиции). |
| `BOT_KLINE_INTERVAL` | `1` | Таймфрейм свечей для уровней/паттернов. |
| `BOT_KLINE_LIMIT` | `200` | Сколько свечей загружать для анализа. |
| `BOT_ORDERBOOK_LIMIT` | `50` | Глубина стакана L2 для snapshot/микроструктуры. |
| `BOT_EVENT_STORE_PATH` | `events/bot_events.jsonl` | Куда писать события запуска (аудит, replay). |
| `BOT_DOTENV_PATH` | `.env` | Путь к dotenv-файлу, который бот читает перед стартом. |
| `BOT_LOG_LEVEL` | `INFO` | Уровень логов в терминале (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

### 3) Исполнение, TP и трейлинг

| Параметр | По умолчанию | Что делает |
|---|---:|---|
| `BOT_SIMULATE_FILLS` | `true` | Режим симуляции исполнений в paper-сценарии. |
| `BOT_PARTIAL_FILL_PROB` | `0.3` | Вероятность частичного исполнения в симуляторе. |
| `BOT_REJECT_PROB` | `0.02` | Вероятность отказа ордера в симуляторе. |
| `BOT_TP_PARTIAL_CLOSE_RATIO` | `0.5` | Доля позиции, закрываемая на первом TP (частичная фиксация). |
| `BOT_TRAILING_DISTANCE_PCT` | `0.003` | Дистанция трейлинга после частичного TP (`0.003` = 0.3%). |

### 4) Мониторинг и observability

| Параметр | По умолчанию | Что делает |
|---|---:|---|
| `BOT_MAX_AVG_SLIPPAGE_BPS` | `8` | Порог алерта по среднему slippage. |
| `BOT_MAX_AVG_FILL_DELAY_MS` | `1500` | Порог алерта по средней задержке исполнения. |
| `SENTRY_DSN` | `""` | DSN для отправки ошибок в Sentry (если задан). |
| `OTEL_ENABLED` | `false` | Включает инициализацию OpenTelemetry провайдера. |

### Важно: что пока настраивается **в коде**, а не через `.env`

Некоторые стратегические параметры пока зашиты в `scalper_bot/config.py` (например, `top_n`, `candidate_pool`, `max_spread_bps`, `imbalance_min`, риск-лимиты `risk_per_trade` и т.д.).
Если хотите, следующим шагом вынесу их в `.env`, чтобы вообще ничего не править в коде.

## Тесты

```bash
python3 -m pytest -q
```

## Деплой и runbook

- `deploy/README.md` — deployment + secret management.
- `deploy/RUNBOOK.md` — incident runbook.
