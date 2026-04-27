"""Tests for the combat event bus."""

from __future__ import annotations

import copy

import pytest

from sts_env.combat.events import (
    Event,
    Owner,
    register_listener,
    subscribe,
    unsubscribe,
    emit,
    _LISTENERS,
)
from sts_env.combat.state import CombatState
from sts_env.combat.powers import Powers
from sts_env.combat.rng import RNG
from sts_env.combat.deck import Piles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> CombatState:
    defaults = dict(
        player_hp=80,
        player_max_hp=80,
        player_block=0,
        player_powers=Powers(),
        energy=3,
        piles=Piles(draw=[], hand=[], discard=[]),
        enemies=[],
        rng=RNG(seed=0),
    )
    defaults.update(overrides)
    return CombatState(**defaults)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_register_and_lookup(self):
        # register_listener is called at module import time by listener modules;
        # we just verify the mechanism works with a fresh event.
        call_log = []

        def handler(state, owner, payload):
            call_log.append((owner, payload))

        # Use a name unlikely to collide with real listeners
        register_listener(Event.CARD_PLAYED, "_test_handler", handler)
        assert Event.CARD_PLAYED in _LISTENERS
        assert "_test_handler" in _LISTENERS[Event.CARD_PLAYED]

        state = _make_state()
        subscribe(state, Event.CARD_PLAYED, "_test_handler", "player")
        emit(state, Event.CARD_PLAYED, "player", card="Strike")
        assert call_log == [("player", {"card": "Strike"})]

        # Cleanup
        del _LISTENERS[Event.CARD_PLAYED]["_test_handler"]
        unsubscribe(state, Event.CARD_PLAYED, "_test_handler", "player")

    def test_insertion_order_preserved(self):
        """Handlers fire in the order they were registered."""
        log = []

        register_listener(Event.CARD_EXHAUSTED, "_test_first", lambda s, o, p: log.append("first"))
        register_listener(Event.CARD_EXHAUSTED, "_test_second", lambda s, o, p: log.append("second"))
        register_listener(Event.CARD_EXHAUSTED, "_test_third", lambda s, o, p: log.append("third"))

        state = _make_state()
        for name in ("_test_first", "_test_second", "_test_third"):
            subscribe(state, Event.CARD_EXHAUSTED, name, "player")

        emit(state, Event.CARD_EXHAUSTED, "player")
        assert log == ["first", "second", "third"]

        # Cleanup
        for name in ("_test_first", "_test_second", "_test_third"):
            del _LISTENERS[Event.CARD_EXHAUSTED][name]
            unsubscribe(state, Event.CARD_EXHAUSTED, name, "player")


# ---------------------------------------------------------------------------
# Subscribe / unsubscribe
# ---------------------------------------------------------------------------

class TestSubscribe:
    def test_subscribe_idempotent(self):
        state = _make_state()
        subscribe(state, Event.CARD_PLAYED, "x", "player")
        subscribe(state, Event.CARD_PLAYED, "x", "player")
        assert state.subscribers[Event.CARD_PLAYED]["player"].count("x") == 1

    def test_unsubscribe_idempotent(self):
        state = _make_state()
        subscribe(state, Event.CARD_PLAYED, "x", "player")
        unsubscribe(state, Event.CARD_PLAYED, "x", "player")
        unsubscribe(state, Event.CARD_PLAYED, "x", "player")
        assert "x" not in state.subscribers[Event.CARD_PLAYED]["player"]

    def test_unsubscribe_nonexistent_event(self):
        """Unsubscribing from an event with no subscribers is a no-op."""
        state = _make_state()
        unsubscribe(state, Event.TURN_START, "x", "player")  # should not raise

    def test_different_owners_independent(self):
        log = []

        register_listener(Event.HP_LOSS, "_test_owner_check", lambda s, o, p: log.append(o))

        state = _make_state()
        subscribe(state, Event.HP_LOSS, "_test_owner_check", "player")
        subscribe(state, Event.HP_LOSS, "_test_owner_check", 0)

        emit(state, Event.HP_LOSS, "player")
        assert log == ["player"]

        emit(state, Event.HP_LOSS, 0)
        assert log == ["player", 0]

        # Cleanup
        del _LISTENERS[Event.HP_LOSS]["_test_owner_check"]
        unsubscribe(state, Event.HP_LOSS, "_test_owner_check", "player")
        unsubscribe(state, Event.HP_LOSS, "_test_owner_check", 0)


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

class TestEmit:
    def test_emit_skips_unsubscribed(self):
        log = []

        register_listener(Event.BLOCK_GAINED, "_test_a", lambda s, o, p: log.append("a"))
        register_listener(Event.BLOCK_GAINED, "_test_b", lambda s, o, p: log.append("b"))

        state = _make_state()
        subscribe(state, Event.BLOCK_GAINED, "_test_a", "player")
        # _test_b not subscribed

        emit(state, Event.BLOCK_GAINED, "player")
        assert log == ["a"]

        del _LISTENERS[Event.BLOCK_GAINED]["_test_a"]
        del _LISTENERS[Event.BLOCK_GAINED]["_test_b"]
        unsubscribe(state, Event.BLOCK_GAINED, "_test_a", "player")

    def test_emit_snapshot_safe(self):
        """Handler that unsubscribes itself mid-emit doesn't skip later handlers."""
        log = []

        def self_removing(state, owner, payload):
            log.append("removing")
            unsubscribe(state, Event.TURN_END, "self_removing", owner)

        register_listener(Event.TURN_END, "self_removing", self_removing)
        register_listener(Event.TURN_END, "_test_after", lambda s, o, p: log.append("after"))

        state = _make_state()
        subscribe(state, Event.TURN_END, "self_removing", "player")
        subscribe(state, Event.TURN_END, "_test_after", "player")

        emit(state, Event.TURN_END, "player")
        assert log == ["removing", "after"]

        del _LISTENERS[Event.TURN_END]["self_removing"]
        del _LISTENERS[Event.TURN_END]["_test_after"]

    def test_emit_no_subscribers_is_noop(self):
        """Emitting to an event with no subscribers is safe."""
        state = _make_state()
        emit(state, Event.COMBAT_START, "player")  # should not raise


# ---------------------------------------------------------------------------
# Deepcopy safety
# ---------------------------------------------------------------------------

class TestDeepcopy:
    def test_subscribers_survive_deepcopy(self):
        log = []

        register_listener(Event.CARD_PLAYED, "_test_copy", lambda s, o, p: log.append(o))

        state = _make_state()
        subscribe(state, Event.CARD_PLAYED, "_test_copy", "player")

        clone = copy.deepcopy(state)
        assert "player" in clone.subscribers[Event.CARD_PLAYED]
        assert "_test_copy" in clone.subscribers[Event.CARD_PLAYED]["player"]

        # Mutating original doesn't affect clone
        unsubscribe(state, Event.CARD_PLAYED, "_test_copy", "player")
        assert "_test_copy" not in state.subscribers[Event.CARD_PLAYED]["player"]
        assert "_test_copy" in clone.subscribers[Event.CARD_PLAYED]["player"]

        del _LISTENERS[Event.CARD_PLAYED]["_test_copy"]
