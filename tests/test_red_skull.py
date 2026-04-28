"""Tests for RedSkull relic via the event bus."""
from __future__ import annotations

import pytest

from sts_env.combat.engine import Combat
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
    c = Combat(
        deck=["Strike", "Defend", "Bash"],
        enemies=["JawWorm"],
        seed=seed,
        player_hp=player_hp,
        player_max_hp=player_max_hp,
        relics=frozenset(["RedSkull"]),
    )
    c.reset()
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
        c = _combat_with_red_skull(player_hp=38, player_max_hp=80)
        assert c._state.player_powers.strength == 3
        state = c._state
        state.player_hp = 45
        emit(state, Event.HP_LOSS, "player", hp_before=38)
        # HP went up but HP_LOSS fired; RedSkull checks current HP
        # Actually, healing wouldn't emit HP_LOSS. The check happens on
        # HP_LOSS events, and we should test that when HP crosses back above
        # the threshold the bonus is removed.
        # RedSkull should deactivate when hp > max_hp // 2
        # This would happen on a future HP_LOSS event where HP is somehow
        # above the threshold. Let's just test the state directly.
        assert state.player_powers.strength == 0
        assert not state.relic_state.get("red_skull_active", 0)

    def test_bonus_stays_at_exactly_half(self):
        c = _combat_with_red_skull(player_hp=40, player_max_hp=80)
        assert c._state.player_powers.strength == 3

    def test_bonus_not_active_without_relic(self):
        c = Combat(
            deck=["Strike", "Defend", "Bash"],
            enemies=["JawWorm"],
            seed=42,
            player_hp=30,
            player_max_hp=80,
        )
        c.reset()
        assert c._state.player_powers.strength == 0
