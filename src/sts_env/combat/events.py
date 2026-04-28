"""Combat event bus: centralised signal/dispatch for triggered effects.

Architecture
------------
Handlers live in module-level registries keyed by (event, listener_name).
CombatState.subscribers stores only strings — ``{Event: {owner: [name, ...]}}``
— so ``copy.deepcopy`` (used by ``Combat.clone``) keeps working with zero
special-casing.

``emit`` snapshots the subscriber list before iterating, so handlers may
freely subscribe/unsubscribe during dispatch without skipping later handlers.

Contract
--------
- ``state`` and ``owner`` are always passed; additional keyword arguments
  form the ``payload`` dict.
- Handlers mutate ``state`` directly; payload is read-only contextual data.
- Owner is ``"player"`` or an ``int`` enemy index.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum, auto
from typing import Callable, Union

if __import__("typing").TYPE_CHECKING:
    from .state import CombatState

Owner = Union[str, int]


class Event(Enum):
    COMBAT_START = auto()
    TURN_START = auto()
    TURN_END = auto()
    CARD_PLAYED = auto()
    CARD_EXHAUSTED = auto()
    CARD_CREATED = auto()
    BLOCK_GAINED = auto()
    HP_LOSS = auto()
    ATTACK_DAMAGED = auto()
    DEATH = auto()
    DEBUFF_APPLIED = auto()
    POTION_USED = auto()       # payload: potion_id — fired when a potion is consumed


# event -> {listener_name: handler}
_LISTENERS: dict[Event, dict[str, Callable]] = {
    event: {} for event in Event
}

# Sentinel for "no subscribers yet for this (event, owner)"
_SENTINEL_LIST: list[str] = []


def register_listener(
    event: Event,
    name: str,
    handler: Callable[["CombatState", Owner, dict], None],
) -> None:
    """Register *handler* under *name* for *event*.

    Called at module-import time by listener modules.  Insertion order is
    preserved (plain dict since Python 3.7), so later ``emit`` calls dispatch
    handlers in registration order.
    """
    _LISTENERS[event][name] = handler


def listener(
    event: Event,
    name: str,
    subscriptions: list[tuple[dict, str]] | None = None,
) -> Callable[[Callable[["CombatState", Owner, dict], None]], Callable[["CombatState", Owner, dict], None]]:
    """Decorator that registers a handler and populates subscription tables.

    Args:
        event: The event this handler responds to.
        name: Unique identifier for this handler.
        subscriptions: List of (table, key) pairs where (event, name) should be appended.
                      Each table is a dict[str, list[tuple[Event, str]]].
    """
    def deco(fn: Callable[["CombatState", Owner, dict], None]) -> Callable[["CombatState", Owner, dict], None]:
        register_listener(event, name, fn)
        for table, key in subscriptions or ():
            table.setdefault(key, []).append((event, name))
        return fn
    return deco


def subscribe(state: "CombatState", event: Event, name: str, owner: Owner) -> None:
    """Add *name* to the subscriber list for ``(event, owner)``.

    Idempotent — subscribing the same name twice is a no-op.
    """
    event_subs = state.subscribers[event]
    owner_subs = event_subs[owner]
    if name not in owner_subs:
        owner_subs.append(name)


def unsubscribe(state: "CombatState", event: Event, name: str, owner: Owner) -> None:
    """Remove *name* from the subscriber list for ``(event, owner)``.

    Safe to call even if *name* was never subscribed or *owner* has no list.
    """
    event_subs = state.subscribers.get(event)
    if event_subs is None:
        return
    owner_subs = event_subs.get(owner)
    if owner_subs is None:
        return
    try:
        owner_subs.remove(name)
    except ValueError:
        pass


def emit(state: "CombatState", event: Event, owner: Owner, **payload: object) -> None:
    """Fire all subscribed handlers for ``(event, owner)``.

    The subscriber list is snapshotted before iteration so handlers may
    mutate it (subscribe/unsubscribe) without affecting dispatch of
    later handlers in the same emit.
    """
    event_subs = state.subscribers.get(event)
    if event_subs is None:
        return
    owner_subs = event_subs.get(owner)
    if not owner_subs:
        return
    snapshot = list(owner_subs)
    handlers = _LISTENERS[event]
    for name in snapshot:
        handler = handlers.get(name)
        if handler is not None:
            handler(state, owner, payload)
