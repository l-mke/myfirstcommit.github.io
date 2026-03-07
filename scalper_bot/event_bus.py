from collections import defaultdict
from typing import Callable, DefaultDict, Dict, List, TypeVar


T = TypeVar("T")


class EventBus:
    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[Callable[[Dict], None]]] = defaultdict(list)

    def subscribe(self, topic: str, callback: Callable[[Dict], None]) -> None:
        self._subs[topic].append(callback)

    def publish(self, topic: str, event: Dict) -> None:
        for callback in self._subs[topic]:
            callback(event)
