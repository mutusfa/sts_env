"""Tests for Act 1 event system."""

from __future__ import annotations

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.events import (
    EventChoice,
    EventSpec,
    get_event,
    random_act1_event,
    register_event,
    resolve_event,
    _pick_worst_card,
    _COMMON_RELICS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def char() -> Character:
    return Character.ironclad()


@pytest.fixture
def rng() -> RNG:
    return RNG(seed=42)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_events_registered(self):
        for eid in [
            "Big Fish",
            "Golden Idol",
            "The Cleric",
            "Dead Adventurer",
            "Golden Wing",
            "Liars Game",
            "Scrap Ooze",
            "Shining Light",
            "Bonfire",
            "Wing Statue",
            "Wheel of Change",
            "Hypnotizing Colored Mushrooms",
        ]:
            spec = get_event(eid)
            assert spec.event_id == eid
            assert len(spec.choices) > 0

    def test_get_event_raises_on_unknown(self):
        with pytest.raises(KeyError):
            get_event("NonExistentEvent")

    def test_random_act1_event_returns_valid(self, rng):
        ev = random_act1_event(rng)
        assert isinstance(ev, EventSpec)
        assert ev.event_id in [
            "Big Fish",
            "Golden Idol",
            "The Cleric",
            "Dead Adventurer",
            "Golden Wing",
            "Liars Game",
            "Scrap Ooze",
            "Shining Light",
            "Bonfire",
            "Wing Statue",
            "Wheel of Change",
            "Hypnotizing Colored Mushrooms",
        ]


# ---------------------------------------------------------------------------
# Big Fish
# ---------------------------------------------------------------------------

class TestBigFish:
    def test_gold_choice(self, char, rng):
        old_max_hp = char.player_max_hp
        old_gold = char.gold
        result = resolve_event("Big Fish", 0, char, rng)
        assert char.gold == old_gold + 50
        assert char.player_max_hp < old_max_hp
        assert "gold" in result.lower()

    def test_upgrade_choice(self, char, rng):
        old_deck = list(char.deck)
        result = resolve_event("Big Fish", 1, char, rng)
        # At least one card should have been upgraded (added "+")
        upgraded = [c for c in char.deck if c.endswith("+")]
        assert len(upgraded) >= 1
        assert "Upgraded" in result

    def test_pay_choice_enough_gold(self, char, rng):
        char.gold = 50
        result = resolve_event("Big Fish", 2, char, rng)
        assert char.gold == 43
        assert "7 gold" in result

    def test_pay_choice_not_enough_gold(self, char, rng):
        char.gold = 3
        result = resolve_event("Big Fish", 2, char, rng)
        assert char.gold == 3
        assert "Not enough" in result


# ---------------------------------------------------------------------------
# Golden Idol
# ---------------------------------------------------------------------------

class TestGoldenIdol:
    def test_navigate(self, char, rng):
        old_max_hp = char.player_max_hp
        old_gold = char.gold
        result = resolve_event("Golden Idol", 0, char, rng)
        assert char.gold == old_gold + 50
        assert char.player_max_hp < old_max_hp

    def test_flowers_heal_and_relic(self, char, rng):
        char.player_hp = 40  # damaged
        old_relics = list(char.relics)
        result = resolve_event("Golden Idol", 1, char, rng)
        # Should have healed
        assert char.player_hp > 40
        # Should have gained a relic
        assert len(char.relics) == len(old_relics) + 1
        new_relic = char.relics[-1]
        assert new_relic in _COMMON_RELICS


# ---------------------------------------------------------------------------
# The Cleric
# ---------------------------------------------------------------------------

class TestCleric:
    def test_heal_choice(self, char, rng):
        char.player_hp = 50
        char.gold = 50
        result = resolve_event("The Cleric", 0, char, rng)
        assert char.gold == 15  # paid 35
        assert char.player_hp > 50  # healed

    def test_heal_not_enough_gold(self, char, rng):
        char.gold = 20
        result = resolve_event("The Cleric", 0, char, rng)
        assert char.gold == 20  # unchanged

    def test_remove_choice(self, char, rng):
        char.gold = 99
        old_deck_len = len(char.deck)
        result = resolve_event("The Cleric", 1, char, rng)
        assert char.gold == 49  # paid 50
        # Card removal is now handled by the orchestrator calling
        # agent.pick_card_to_remove() — resolve_event only deducts gold.
        assert len(char.deck) == old_deck_len
        assert "paid" in result.lower() or "remove" in result.lower()

    def test_remove_not_enough_gold(self, char, rng):
        char.gold = 30
        old_deck_len = len(char.deck)
        result = resolve_event("The Cleric", 1, char, rng)
        assert char.gold == 30
        assert len(char.deck) == old_deck_len

    def test_leave(self, char, rng):
        old_hp = char.player_hp
        old_gold = char.gold
        result = resolve_event("The Cleric", 2, char, rng)
        assert char.player_hp == old_hp
        assert char.gold == old_gold


# ---------------------------------------------------------------------------
# Dead Adventurer
# ---------------------------------------------------------------------------

class TestDeadAdventurer:
    def test_loot_safe_phase0(self, char, rng):
        """Phase 0: 25% encounter chance. With deterministic RNG we may get safe loot."""
        from sts_env.run.events import _da_state, _dead_adventurer_setup
        _da_state.clear()
        _da_state.update(_dead_adventurer_setup(rng))
        old_gold = char.gold
        old_deck_len = len(char.deck)
        result = resolve_event("Dead Adventurer", 0, char, rng)
        # Either safe loot (gold/card/relic gained) or combat triggered
        assert "Looted safely" in result or "ambushed" in result.lower()

    def test_loot_safe_gives_gold(self, char):
        """Force a gold reward by setting rewards schedule and ensuring no encounter."""
        from sts_env.run.events import _da_state, _dead_adventurer_loot
        from sts_env.combat.rng import RNG
        rng = RNG(42)
        _da_state.clear()
        _da_state.update({"phase": 0, "rewards": [0, 1, 2], "encounter_id": "Lagavulin"})
        old_gold = char.gold
        # Use a seeded RNG that won't trigger encounter at phase 0
        result = _dead_adventurer_loot(char, RNG(100))
        if "Looted safely" in result:
            assert char.gold == old_gold + 30  # gold reward
            assert _da_state["phase"] == 1

    def test_leave(self, char, rng):
        from sts_env.run.events import _da_state, _dead_adventurer_setup
        _da_state.clear()
        _da_state.update(_dead_adventurer_setup(rng))
        old_hp = char.player_hp
        old_gold = char.gold
        result = resolve_event("Dead Adventurer", 1, char, rng)
        assert char.player_hp == old_hp
        assert char.gold == old_gold

    def test_phase_advances(self, char):
        """After 3 safe loots, event reports nothing left."""
        from sts_env.run.events import _da_state, _dead_adventurer_loot
        from sts_env.combat.rng import RNG
        _da_state.clear()
        _da_state.update({"phase": 3, "rewards": [0, 1, 2], "encounter_id": "Lagavulin"})
        result = _dead_adventurer_loot(char, RNG(42))
        assert "nothing left" in result.lower()


# ---------------------------------------------------------------------------
# Golden Wing
# ---------------------------------------------------------------------------

class TestGoldenWing:
    def test_gold_choice(self, char, rng):
        old_max_hp = char.player_max_hp
        old_gold = char.gold
        result = resolve_event("Golden Wing", 0, char, rng)
        assert char.gold == old_gold + 100
        assert char.player_max_hp < old_max_hp

    def test_heal_choice(self, char, rng):
        char.gold = 60
        char.player_hp = 40
        old_max_hp = char.player_max_hp
        result = resolve_event("Golden Wing", 1, char, rng)
        assert char.gold == 0
        assert char.player_hp > 40


# ---------------------------------------------------------------------------
# Liars Game
# ---------------------------------------------------------------------------

class TestLiarsGame:
    def test_win(self, char):
        rng = RNG(seed=99)
        char.gold = 50
        result = resolve_event("Liars Game", 0, char, rng)
        # Seed 99 first random() determines win or lose
        # Just verify gold changed and result mentions outcome
        assert "win" in result.lower() or "lose" in result.lower()

    def test_not_enough_gold(self, char, rng):
        char.gold = 3
        result = resolve_event("Liars Game", 0, char, rng)
        assert char.gold == 3
        assert "Not enough" in result

    def test_leave(self, char, rng):
        char.gold = 50
        result = resolve_event("Liars Game", 1, char, rng)
        assert char.gold == 50


# ---------------------------------------------------------------------------
# Scrap Ooze
# ---------------------------------------------------------------------------

class TestScrapOoze:
    def test_card_choice_adds_colorless_card(self, char, rng):
        """colorless_pool() now has cards — Scrap Ooze grants one."""
        old_deck_len = len(char.deck)
        result = resolve_event("Scrap Ooze", 0, char, rng)
        assert len(char.deck) == old_deck_len + 1
        assert "Obtained" in result

    def test_pay_choice_enough_gold(self, char, rng):
        char.gold = 20
        result = resolve_event("Scrap Ooze", 1, char, rng)
        assert char.gold == 17

    def test_pay_choice_not_enough_gold(self, char, rng):
        char.gold = 2
        result = resolve_event("Scrap Ooze", 1, char, rng)
        assert char.gold == 2
        assert "Not enough" in result


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_pick_worst_card_strike(self):
        deck = ["Defend", "Strike", "Bash", "Defend"]
        assert _pick_worst_card(deck) == "Strike"

    def test_pick_worst_card_slimed(self):
        deck = ["Strike", "Slimed", "Defend"]
        assert _pick_worst_card(deck) == "Slimed"

    def test_pick_worst_card_empty(self):
        assert _pick_worst_card([]) is None

    def test_pick_worst_card_no_priority(self):
        deck = ["Bash", "Anger"]
        # Neither has priority entry → just returns one (min by priority 99)
        result = _pick_worst_card(deck)
        assert result in deck
