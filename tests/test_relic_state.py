"""Tests for relic state/disable infrastructure and key relic behaviors."""

from __future__ import annotations

import pytest

from sts_env.combat.engine import Combat
from sts_env.combat.events import Event, emit
from sts_env.combat.healing import heal_player
from sts_env.combat.player_state import PlayerState
from sts_env.combat.relic_state import disable_relic_combat, relic_active
from sts_env.run.character import Character
from sts_env.run.map import RoomType
from sts_env.run.relic_hooks import (
    apply_relic_on_obtain,
    relics_on_enter_room,
    resolve_mystery_room,
    spend_gold_at_shop,
)
from sts_env.run.relic_state import disable_relic_run, init_relic_on_obtain
from sts_env.combat.rng import RNG
from sts_env.run.rng_streams import RunRNG


class TestRelicActive:
    def test_default_data_active(self):
        assert relic_active("MawBank", owned=["MawBank"], relic_data={})

    def test_run_disabled(self):
        assert not relic_active("MawBank", owned=["MawBank"], relic_data={"MawBank": 0})

    def test_combat_disabled(self):
        assert not relic_active(
            "CentennialPuzzle",
            owned=["CentennialPuzzle"],
            relic_data={},
            combat_disabled={"CentennialPuzzle"},
        )


class TestMawBank:
    def test_gold_each_room_until_shop_spend(self):
        char = Character.ironclad()
        char.relics.append("MawBank")
        init_relic_on_obtain("MawBank", char)

        relics_on_enter_room(char, RoomType.MONSTER)
        assert char.gold == 99 + 12

        relics_on_enter_room(char, RoomType.EVENT)
        assert char.gold == 99 + 24

        spend_gold_at_shop(char, 10)
        assert char.relic_data["MawBank"] == 0

        gold_before = char.gold
        relics_on_enter_room(char, RoomType.MONSTER)
        assert char.gold == gold_before  # disabled — no more +12


class TestCentennialPuzzle:
    def test_once_per_combat_via_combat_disable(self):
        ps = PlayerState(
            deck=["Strike", "Defend"],
            relics=["CentennialPuzzle"],
        )
        c = Combat(ps, ["JawWorm"], 42)
        state = c._state

        state.player_hp = 30
        emit(state, Event.HP_LOSS, "player", hp_before=40)
        assert "CentennialPuzzle" in state.relic_combat_disabled

        hand_before = len(state.piles.hand)
        state.player_hp = 20
        emit(state, Event.HP_LOSS, "player", hp_before=30)
        assert len(state.piles.hand) == hand_before


class TestRedSkullHeal:
    def test_removes_strength_when_healing_above_half(self):
        ps = PlayerState(deck=["Strike"], player_hp=38, player_max_hp=80, relics=["RedSkull"])
        c = Combat(ps, ["JawWorm"], 42)
        state = c._state
        assert state.player_powers.strength == 3

        heal_player(state, 10)
        assert state.player_powers.strength == 0
        assert not state.relic_state.get("red_skull_active", 0)


class TestLizardTail:
    def test_revives_once(self):
        ps = PlayerState(
            deck=["Strike"],
            player_hp=10,
            player_max_hp=80,
            relics=["LizardTail"],
        )
        init_relic_on_obtain("LizardTail", ps)
        c = Combat(ps, ["JawWorm"], 42)
        state = c._state

        state.player_hp = 0
        emit(state, Event.HP_LOSS, "player", hp_before=10)
        assert state.player_hp == 40
        assert state.relic_data["LizardTail"] == 0


class TestObtainHooks:
    def test_strawberry_max_hp(self):
        char = Character.ironclad()
        apply_relic_on_obtain(char, "Strawberry")
        assert char.player_max_hp == 87

    def test_whetstone_upgrades_attack(self):
        char = Character.ironclad()
        apply_relic_on_obtain(char, "Whetstone")
        assert any(c.endswith("+") for c in char.deck)


class TestJuzuBracelet:
    def test_mystery_monster_becomes_event(self):
        char = Character.ironclad()
        char.relics.append("JuzuBracelet")
        rng = RNG(0)
        # Seed 0 → low roll → monster bucket
        outcome = resolve_mystery_room(rng, char)
        from sts_env.run.relic_hooks import MysteryOutcome

        assert outcome == MysteryOutcome.EVENT


class TestCoffeeDripperEnergy:
    def test_plus_one_energy_per_turn(self):
        ps = PlayerState(deck=["Strike"], relics=["CoffeeDripper"])
        c = Combat(ps, ["JawWorm"], 42)
        # Turn 0 start: COMBAT_START_PRE_DRAW already fired; TURN_START on first player turn
        state = c._state
        energy_at_combat_start = state.energy
        emit(state, Event.TURN_START, "player")
        assert state.energy == energy_at_combat_start + 1


class TestFrozenEgg:
    def test_offer_shows_upgraded_attack(self):
        from sts_env.combat.cards import CardType, get_spec
        from sts_env.run.rewards import roll_card_rewards

        char = Character.ironclad()
        char.add_relic("MoltenEgg")
        cards, _ = roll_card_rewards(RNG(42), relics=char.relics)
        for card_id in cards:
            base = card_id.rstrip("+")
            try:
                if get_spec(base).card_type == CardType.ATTACK:
                    assert card_id.endswith("+")
            except KeyError:
                pass

    def test_add_card_still_upgrades_non_offer_paths(self):
        char = Character.ironclad()
        char.add_relic("MoltenEgg")
        char.add_card("Anger")
        assert "Anger+" in char.deck

    def test_agent_pick_matches_deck_entry(self):
        """Picking an upgraded offer adds that exact ID — no hidden upgrade."""
        from sts_env.run.rewards import roll_combat_reward_offer
        from sts_env.run.rewards import Room

        char = Character.ironclad()
        char.add_relic("FrozenEgg")
        offer, _ = roll_combat_reward_offer(RunRNG(7), 0, Room.MONSTER, relics=char.relics)
        picked = offer.card_choices[0]
        char.add_card(picked)
        assert char.deck[-1] == picked
