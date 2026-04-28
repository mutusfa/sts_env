"""Run-layer event bus: centralised signal/dispatch for run-level triggered effects.

Mirrors the combat event system (``combat/events.py``) but simpler — no per-owner
semantics (no enemies).  Handlers are registered at import time via ``@listener``.
The per-run :class:`RunEventBus` tracks which handlers are active based on
relics / potions the character currently has.

Usage::

    from .bus import RunEvent, RunEventBus, wire_relics

    # Emit from core logic (no knowledge of specific relics):
    payload = bus.emit(RunEvent.CARD_ADDED, character=char, card_id="Strike")

    # Register a listener (at module level):
    @listener(RunEvent.CARD_ADDED, "ceramic_fish", subscriptions=[(RELI_RUN_SUBSCRIPTIONS, "CeramicFish")])
    def _ceramic_fish(payload: dict) -> None:
        payload["character"].gold += 9
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum, auto
from typing import Callable


class RunEvent(Enum):
    CARD_ADDED = auto()         # payload: character, card_id
    CARD_REWARD_COUNT = auto()  # payload: {"count": N} — mutable, handlers modify


# ---------------------------------------------------------------------------
# Global handler registry (populated at import time by @listener)
# ---------------------------------------------------------------------------

_LISTENERS: dict[RunEvent, dict[str, Callable]] = defaultdict(dict)

# Subscription tables — same pattern as combat RELIC_SUBSCRIPTIONS
RELI_RUN_SUBSCRIPTIONS: dict[str, list[tuple[RunEvent, str]]] = {}


def register_listener(
    event: RunEvent,
    name: str,
    handler: Callable[[dict], None],
) -> None:
    _LISTENERS[event][name] = handler


def listener(
    event: RunEvent,
    name: str,
    subscriptions: list[tuple[dict, str]] | None = None,
) -> Callable:
    """Decorator that registers a handler and populates subscription tables."""

    def deco(fn: Callable[[dict], None]) -> Callable[[dict], None]:
        register_listener(event, name, fn)
        for table, key in subscriptions or ():
            table.setdefault(key, []).append((event, name))
        return fn

    return deco


# ---------------------------------------------------------------------------
# Per-run bus
# ---------------------------------------------------------------------------

class RunEventBus:
    """Per-run event bus.  Holds active subscriptions; dispatches to registered handlers."""

    def __init__(self) -> None:
        self._subscribers: dict[RunEvent, list[str]] = defaultdict(list)

    def subscribe(self, event: RunEvent, name: str) -> None:
        """Idempotent — subscribing the same name twice is a no-op."""
        if name not in self._subscribers[event]:
            self._subscribers[event].append(name)

    def emit(self, event: RunEvent, **kwargs) -> dict:
        """Fire all subscribed handlers for *event*.

        Returns the (possibly mutated) payload dict.  Callers that need
        modifiers (e.g. ``CARD_REWARD_COUNT``) read from the return value;
        notification-only callers can ignore it.
        """
        payload = dict(kwargs)
        snapshot = list(self._subscribers.get(event, []))
        handlers = _LISTENERS.get(event, {})
        for name in snapshot:
            handler = handlers.get(name)
            if handler:
                handler(payload)
        return payload


def wire_relics(bus: RunEventBus, relics: list[str]) -> None:
    """Subscribe relic handlers for all relics in *relics*."""
    for relic_name in relics:
        for event, handler_name in RELI_RUN_SUBSCRIPTIONS.get(relic_name, []):
            bus.subscribe(event, handler_name)
