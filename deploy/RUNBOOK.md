# Scalper Bot Incident Runbook

## 1. Kill Switch Triggered
- Check event store (`BOT_EVENT_STORE_PATH`) for topic `halt`.
- Validate `daily_pnl` and `open_risk` values.
- If market anomaly: keep halted until spread normalizes.

## 2. Circuit Breaker Triggered
- Verify spread and consecutive connectivity errors.
- Confirm Bybit API status and local network health.
- Restart only after spread and connectivity recover.

## 3. Private WS Issues
- Ensure `BYBIT_PRIVATE_WS_ENABLED=true` and keys are present.
- Check reconnect loop and last `private_ws` events in JSONL.
- Fallback to REST-only mode if WS unavailable.

## 4. High Slippage / Fill Delay Alerts
- Inspect `alert` and `execution` events.
- Reduce size / switch to stricter order type.
- Temporarily disable trading if persistent.

## 5. Secret Rotation
- Rotate keys in secret manager.
- Restart service to pick up new env vars.
- Validate with paper run before `--live`.
