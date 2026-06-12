"""Tests for RedSkull relic via the event bus."""
from __future__ import annotations

import pytest

from sts_env.combat.engine import Combat
from sts_env.combat.player_state import PlayerState
from sts_env.combat.state import CombatState
from sts_env.combat.powers import Powers
from sts_env.combat.rng import RNG
from sts_env.combat.deck import Piles
from sts_env.combat.events import Event, subscribe, emit


def _combat_with_red_skull(
    player_hp: int = 80,
    player_max_hp: int = 80,
    seed: int = 42,
) -> Combat:
    c = Combat(PlayerState(deck=["Strike", "Defend", "Bash"], player_hp=player_hp, player_max_hp=player_max_hp, relics=frozenset(["RedSkull"])), ["JawWorm"], seed)
    c.observe()
    return c


class TestRedSkull:
    def test_no_bonus_above_half_hp(self):
        c = _combat_with_red_skull(player_hp=80, player_max_hp=80)
        assert c._state.player_powers.strength == 0

    def test_bonus_active_at_half_hp(self):
        c = _combat_with_red_skull(player_hp=40, player_max_hp=80)
        assert c._state.player_powers.strength == 3

    def test_bonus_activates_on_hp_loss(self):
        c = _combat_with_red_skull(player_hp=45, player_max_hp=80)
        assert c._state.player_powers.strength == 0
        # Directly damage player below 50%
        state = c._state
        state.player_hp = 38
        emit(state, Event.HP_LOSS, "player", hp_before=45)
        assert state.player_powers.strength == 3
        assert state.relic_state.get("red_skull_active", 0)

    def test_bonus_removes_on_heal_above_half(self):
        from sts_env.combat.healing import heal_player

        c = _combat_with_red_skull(player_hp=38, player_max_hp=80)
        assert c._state.player_powers.strength == 3
        heal_player(c._state, 10)
        assert c._state.player_powers.strength == 0
        assert not c._state.relic_state.get("red_skull_active", 0)

    def test_bonus_stays_at_exactly_half(self):
        c = _combat_with_red_skull(player_hp=40, player_max_hp=80)
        assert c._state.player_powers.strength == 3

    def test_bonus_not_active_without_relic(self):
        c = Combat(PlayerState(deck=["Strike", "Defend", "Bash"], player_hp=30, player_max_hp=80), ["JawWorm"], 42)
        c.observe()
        assert c._state.player_powers.strength == 0
