from pathlib import Path

from scalper_bot.config import BotConfig


def test_from_env_loads_dotenv_file(monkeypatch, tmp_path: Path) -> None:
    dotenv = tmp_path / ".env.test"
    dotenv.write_text("BYBIT_TESTNET=false\nBOT_EQUITY_USDT=7777\nBYBIT_LEVERAGE=5\n")

    monkeypatch.setenv("BOT_DOTENV_PATH", str(dotenv))
    monkeypatch.delenv("BYBIT_TESTNET", raising=False)
    monkeypatch.delenv("BOT_EQUITY_USDT", raising=False)
    monkeypatch.delenv("BYBIT_LEVERAGE", raising=False)

    cfg = BotConfig.from_env()

    assert cfg.exchange.testnet is False
    assert cfg.runtime.equity_usdt == 7777.0
    assert cfg.exchange.leverage == 5.0
