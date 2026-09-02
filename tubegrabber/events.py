"""Simple event bus for decoupled progress & status notifications."""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event: str, callback: Callable[[Any], None]) -> None:
        self._subscribers.setdefault(event, []).append(callback)

    def publish(self, event: str, payload: Any = None) -> None:
        for cb in self._subscribers.get(event, []):
            try:
                cb(payload)
            except Exception:
                logging.getLogger("tubegrabber").exception(
                    "Event handler failed for %s", event
                )
