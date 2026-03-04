from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional


@dataclass
class EventRecord:
    ts_ms: int
    topic: str
    payload: Dict[str, Any]


class JsonlEventStore:
    def __init__(self, path: str = "events/bot_events.jsonl") -> None:
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def append(self, topic: str, payload: Dict[str, Any]) -> None:
        record = EventRecord(ts_ms=int(time.time() * 1000), topic=topic, payload=payload)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.__dict__, ensure_ascii=False) + "\n")

    def iter_events(self, topic: Optional[str] = None) -> Iterable[EventRecord]:
        if not os.path.exists(self.path):
            return []

        out: list[EventRecord] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                record = EventRecord(ts_ms=int(row["ts_ms"]), topic=row["topic"], payload=row["payload"])
                if topic and record.topic != topic:
                    continue
                out.append(record)
        return out

    def replay(self, callback: Callable[[EventRecord], None], topic: Optional[str] = None) -> int:
        count = 0
        for event in self.iter_events(topic=topic):
            callback(event)
            count += 1
        return count
