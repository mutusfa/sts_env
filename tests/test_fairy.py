"""Tests for Fairy in a Bottle potion via the event bus."""
from __future__ import annotations

import math

import pytest

from sts_env.combat.engine import Combat
from sts_env.combat.state import CombatState
from sts_env.combat.powers import Powers
from sts_env.combat.rng import RNG
from sts_env.combat.deck import Piles
from sts_env.combat.events import Event, subscribe, emit


def _combat_with_fairy(
    player_hp: int = 80,
    player_max_hp: int = 80,
    seed: int = 42,
) -> Combat:
    c = Combat(
        deck=["Strike", "Defend", "Bash"],
        enemies=["JawWorm"],
        seed=seed,
        player_hp=player_hp,
        player_max_hp=player_max_hp,
        potions=["FairyInABottle"],
    )
    c.reset()
    return c


class TestFairyInABottle:
    def test_revives_at_30_percent_on_lethal(self):
        c = _combat_with_fairy(player_hp=10, player_max_hp=80)
        state = c._state
        expected_hp = max(1, math.floor(80 * 0.3))
        # Simulate lethal damage
        state.player_hp = 0
        emit(state, Event.HP_LOSS, "player", hp_before=10)
        assert state.player_hp == expected_hp

    def test_potion_consumed_on_revive(self):
        c = _combat_with_fairy(player_hp=10, player_max_hp=80)
        state = c._state
        assert "FairyInABottle" in state.potions
        state.player_hp = 0
        emit(state, Event.HP_LOSS, "player", hp_before=10)
        assert "FairyInABottle" not in state.potions

    def test_no_revive_above_zero_hp(self):
        c = _combat_with_fairy(player_hp=10, player_max_hp=80)
        state = c._state
        state.player_hp = 5  # not dead
        emit(state, Event.HP_LOSS, "player", hp_before=10)
        assert state.player_hp == 5  # unchanged by fairy
        assert "FairyInABottle" in state.potions

    def test_two_fairies_consume_independently(self):
        c = Combat(
            deck=["Strike", "Defend", "Bash"],
            enemies=["JawWorm"],
            seed=42,
            player_hp=10,
            player_max_hp=80,
            potions=["FairyInABottle", "FairyInABottle"],
        )
        c.reset()
        state = c._state
        assert state.potions.count("FairyInABottle") == 2

        # First lethal hit
        state.player_hp = 0
        emit(state, Event.HP_LOSS, "player", hp_before=10)
        expected_hp = max(1, math.floor(80 * 0.3))
        assert state.player_hp == expected_hp
        assert state.potions.count("FairyInABottle") == 1

        # Second lethal hit
        state.player_hp = 0
        emit(state, Event.HP_LOSS, "player", hp_before=expected_hp)
        assert state.player_hp == expected_hp
        assert "FairyInABottle" not in state.potions

    def test_no_revive_without_potion(self):
        c = Combat(
            deck=["Strike", "Defend", "Bash"],
            enemies=["JawWorm"],
            seed=42,
            player_hp=10,
            player_max_hp=80,
            potions=[],
        )
        c.reset()
        state = c._state
        state.player_hp = 0
        emit(state, Event.HP_LOSS, "player", hp_before=10)
        assert state.player_hp == 0  # stays dead

    def test_min_hp_revive_at_low_max(self):
        """With very low max HP, fairy should give at least 1 HP."""
        c = _combat_with_fairy(player_hp=1, player_max_hp=1)
        state = c._state
        state.player_hp = 0
        emit(state, Event.HP_LOSS, "player", hp_before=1)
        assert state.player_hp == 1
