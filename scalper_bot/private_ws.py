from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional


@dataclass
class PrivateWSConfig:
    url: str
    api_key: str
    api_secret: str
    ping_interval_s: int = 20
    reconnect_delay_s: int = 3


@dataclass
class PrivateStreamManager:
    cfg: PrivateWSConfig
    _handlers: Dict[str, Callable[[dict], None]] = field(default_factory=dict)
    _thread: Optional[threading.Thread] = None
    _stop: bool = False

    def on(self, topic: str, handler: Callable[[dict], None]) -> None:
        self._handlers[topic] = handler

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run_loop(self) -> None:
        try:
            import websocket  # type: ignore
        except Exception:
            # fallback: nothing to do if websocket client package isn't available
            return

        while not self._stop:
            ws = None
            try:
                ws = websocket.create_connection(self.cfg.url, timeout=10)
                expires = int((time.time() + 10) * 1000)
                sign_payload = f"GET/realtime{expires}"
                signature = hmac.new(self.cfg.api_secret.encode(), sign_payload.encode(), hashlib.sha256).hexdigest()
                ws.send(json.dumps({"op": "auth", "args": [self.cfg.api_key, expires, signature]}))
                ws.send(json.dumps({"op": "subscribe", "args": ["order", "position", "execution"]}))

                last_ping = time.time()
                while not self._stop:
                    if time.time() - last_ping >= self.cfg.ping_interval_s:
                        ws.send(json.dumps({"op": "ping"}))
                        last_ping = time.time()

                    ws.settimeout(1)
                    try:
                        raw = ws.recv()
                    except Exception:
                        continue
                    msg = json.loads(raw)
                    topic = msg.get("topic")
                    if topic in self._handlers:
                        self._handlers[topic](msg)
            except Exception:
                time.sleep(self.cfg.reconnect_delay_s)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
