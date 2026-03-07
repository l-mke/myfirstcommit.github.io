from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .models import Candle, Ticker24h


@dataclass(frozen=True)
class BybitCredentials:
    api_key: str
    api_secret: str
    recv_window: str = "5000"


class BybitRESTClient:
    def __init__(self, base_url: str, credentials: Optional[BybitCredentials] = None, timeout_s: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.timeout_s = timeout_s

    @staticmethod
    def from_env() -> "BybitRESTClient":
        testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        api_key = os.getenv("BYBIT_API_KEY", "")
        api_secret = os.getenv("BYBIT_API_SECRET", "")
        creds = BybitCredentials(api_key, api_secret) if api_key and api_secret else None
        return BybitRESTClient(base_url=base_url, credentials=creds)

    def get_tickers(self, category: str = "linear") -> List[Ticker24h]:
        payload = self._request("GET", "/v5/market/tickers", {"category": category})
        out: List[Ticker24h] = []
        for row in payload.get("result", {}).get("list", []):
            try:
                out.append(
                    Ticker24h(
                        symbol=row["symbol"],
                        high_price_24h=float(row.get("highPrice24h") or 0.0),
                        low_price_24h=float(row.get("lowPrice24h") or 0.0),
                        turnover_24h=float(row.get("turnover24h") or 0.0),
                        volume_24h=float(row.get("volume24h") or 0.0),
                        bid1=float(row.get("bid1Price") or 0.0),
                        ask1=float(row.get("ask1Price") or 0.0),
                    )
                )
            except (KeyError, ValueError):
                continue
        return out

    def get_kline(self, *, category: str, symbol: str, interval: str = "1", limit: int = 200) -> List[Candle]:
        payload = self._request(
            "GET",
            "/v5/market/kline",
            {"category": category, "symbol": symbol, "interval": interval, "limit": str(limit)},
        )
        rows = payload.get("result", {}).get("list", [])
        out: List[Candle] = []
        for row in rows:
            try:
                # [startTime,open,high,low,close,volume,turnover]
                out.append(
                    Candle(
                        ts_ms=int(row[0]),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                    )
                )
            except (IndexError, ValueError, TypeError):
                continue
        out.sort(key=lambda c: c.ts_ms)
        return out

    def get_orderbook_snapshot(self, *, category: str, symbol: str, limit: int = 50) -> Dict[str, Any]:
        return self._request(
            "GET",
            "/v5/market/orderbook",
            {"category": category, "symbol": symbol, "limit": str(limit)},
        )


    def set_leverage(self, *, category: str, symbol: str, buy_leverage: str, sell_leverage: str) -> Dict[str, Any]:
        body = {
            "category": category,
            "symbol": symbol,
            "buyLeverage": buy_leverage,
            "sellLeverage": sell_leverage,
        }
        return self._request("POST", "/v5/position/set-leverage", body, private=True)

    def place_order(self, *, category: str, symbol: str, side: str, qty: str, order_type: str = "Market") -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty,
            "timeInForce": "IOC" if order_type == "Market" else "PostOnly",
        }
        return self._request("POST", "/v5/order/create", body, private=True)

    def _request(self, method: str, path: str, params_or_body: Dict[str, Any], private: bool = False) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}{path}"

        if method == "GET":
            qs = urllib.parse.urlencode(params_or_body)
            url = f"{url}?{qs}"
            body_bytes = None
            sign_payload = qs
        else:
            body_str = json.dumps(params_or_body, separators=(",", ":"))
            body_bytes = body_str.encode("utf-8")
            sign_payload = body_str

        if private:
            if self.credentials is None:
                raise RuntimeError("Missing BYBIT_API_KEY/BYBIT_API_SECRET")
            timestamp = str(int(time.time() * 1000))
            signature = self._sign(timestamp, self.credentials.api_key, self.credentials.recv_window, sign_payload)
            headers.update(
                {
                    "X-BAPI-API-KEY": self.credentials.api_key,
                    "X-BAPI-TIMESTAMP": timestamp,
                    "X-BAPI-RECV-WINDOW": self.credentials.recv_window,
                    "X-BAPI-SIGN": signature,
                }
            )

        req = urllib.request.Request(url=url, headers=headers, data=body_bytes, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout_s) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))

    def _sign(self, timestamp: str, api_key: str, recv_window: str, payload: str) -> str:
        if self.credentials is None:
            raise RuntimeError("Credentials required for signing")
        raw = f"{timestamp}{api_key}{recv_window}{payload}"
        return hmac.new(self.credentials.api_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
