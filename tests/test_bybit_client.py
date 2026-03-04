from scalper_bot.bybit_client import BybitCredentials, BybitRESTClient


def test_sign_vector() -> None:
    client = BybitRESTClient(
        base_url="https://api-testnet.bybit.com",
        credentials=BybitCredentials(api_key="test_key", api_secret="test_secret"),
    )
    sign = client._sign("1700000000000", "test_key", "5000", "category=linear")
    assert sign == "8d008fd821ab5f67bb93ad3fdfa00948644261883071f7abc7d1fe94f5cffb01"


def test_get_kline_parses_sorted(monkeypatch) -> None:
    client = BybitRESTClient(base_url="https://api-testnet.bybit.com")

    def fake_request(method: str, path: str, params_or_body: dict, private: bool = False) -> dict:
        assert method == "GET"
        assert path == "/v5/market/kline"
        return {
            "result": {
                "list": [
                    ["2", "10", "11", "9", "10.5", "100", "1000"],
                    ["1", "9", "10", "8", "9.5", "90", "900"],
                ]
            }
        }

    monkeypatch.setattr(client, "_request", fake_request)
    rows = client.get_kline(category="linear", symbol="BTCUSDT", interval="1", limit=2)
    assert len(rows) == 2
    assert rows[0].ts_ms == 1
    assert rows[1].close == 10.5


def test_set_leverage_calls_private_endpoint(monkeypatch) -> None:
    client = BybitRESTClient(base_url="https://api-testnet.bybit.com")

    captured = {}

    def fake_request(method: str, path: str, params_or_body: dict, private: bool = False) -> dict:
        captured["method"] = method
        captured["path"] = path
        captured["body"] = params_or_body
        captured["private"] = private
        return {"retCode": 0}

    monkeypatch.setattr(client, "_request", fake_request)
    resp = client.set_leverage(category="linear", symbol="BTCUSDT", buy_leverage="3", sell_leverage="3")

    assert resp["retCode"] == 0
    assert captured["method"] == "POST"
    assert captured["path"] == "/v5/position/set-leverage"
    assert captured["private"] is True
    assert captured["body"]["buyLeverage"] == "3"
