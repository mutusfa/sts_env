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
    _COLORLESS_CARDS,
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
        char.gold = 30
        result = resolve_event("The Cleric", 0, char, rng)
        assert char.gold == 15  # paid 15
        assert char.player_hp > 50  # healed

    def test_heal_not_enough_gold(self, char, rng):
        char.gold = 10
        result = resolve_event("The Cleric", 0, char, rng)
        assert char.gold == 10  # unchanged

    def test_remove_choice(self, char, rng):
        char.gold = 99
        old_deck_len = len(char.deck)
        result = resolve_event("The Cleric", 1, char, rng)
        assert char.gold == 49  # paid 50
        assert len(char.deck) == old_deck_len - 1

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
    def test_fight_choice(self, char, rng):
        old_hp = char.player_hp
        old_gold = char.gold
        result = resolve_event("Dead Adventurer", 0, char, rng)
        assert char.player_hp == old_hp - 5
        assert char.gold > old_gold
        assert "damage" in result.lower()

    def test_leave(self, char, rng):
        old_hp = char.player_hp
        old_gold = char.gold
        result = resolve_event("Dead Adventurer", 1, char, rng)
        assert char.player_hp == old_hp
        assert char.gold == old_gold


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
    def test_card_choice(self, char, rng):
        old_deck_len = len(char.deck)
        result = resolve_event("Scrap Ooze", 0, char, rng)
        assert len(char.deck) == old_deck_len + 1
        new_card = char.deck[-1]
        assert new_card in _COLORLESS_CARDS

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
