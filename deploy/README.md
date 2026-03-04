# Deployment & Secret Management

## Secrets
Use environment-injection from your platform secret manager (examples):
- Kubernetes Secrets + sealed-secrets/external-secrets
- AWS Secrets Manager / SSM Parameter Store
- HashiCorp Vault

Required secrets:
- `BYBIT_API_KEY`
- `BYBIT_API_SECRET`
- `SENTRY_DSN` (optional)

Never commit `.env` with real keys.

## Example systemd unit

```ini
[Unit]
Description=Bybit Scalper Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/scalper
EnvironmentFile=/etc/scalper-bot/secrets.env
ExecStart=/usr/bin/python3 /opt/scalper/bot.py --live
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Incident runbook
See `deploy/RUNBOOK.md`.
