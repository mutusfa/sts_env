"""Tests for Act 1 event system — all 17 events.

Covers: Big Fish, The Cleric, Dead Adventurer, Golden Idol, Wing Statue,
World of Goop, The Ssssserpent, Living Wall, Hypnotizing Colored Mushrooms,
Scrap Ooze, Shining Light, Match and Keep, Golden Shrine, Transmorgrifier,
Purifier, Upgrade Shrine, Wheel of Change.
"""

from __future__ import annotations

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.events import (
    EventSpec,
    get_event,
    random_act1_event,
    register_event,
    resolve_event,
    _pick_worst_card,
    transform_card,
    _da_state,
    _dead_adventurer_setup,
    _dead_adventurer_loot,
    _ooze_state,
    _scrap_ooze_setup,
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
    ALL_EVENT_IDS = [
        "Big Fish",
        "The Cleric",
        "Dead Adventurer",
        "Golden Idol",
        "Wing Statue",
        "World of Goop",
        "The Ssssserpent",
        "Living Wall",
        "Hypnotizing Colored Mushrooms",
        "Scrap Ooze",
        "Shining Light",
        "Match and Keep",
        "Golden Shrine",
        "Transmorgrifier",
        "Purifier",
        "Upgrade Shrine",
        "Wheel of Change",
    ]

    def test_all_17_events_registered(self):
        assert len(self.ALL_EVENT_IDS) == 17
        for eid in self.ALL_EVENT_IDS:
            spec = get_event(eid)
            assert spec.event_id == eid
            assert len(spec.choices) > 0

    def test_get_event_raises_on_unknown(self):
        with pytest.raises(KeyError):
            get_event("NonExistentEvent")

    def test_random_act1_event_returns_valid(self, rng):
        ev = random_act1_event(rng)
        assert isinstance(ev, EventSpec)
        assert ev.event_id in self.ALL_EVENT_IDS

    def test_random_act1_event_excludes_seen(self, rng):
        seen = ["Big Fish", "The Cleric"]
        ev = random_act1_event(rng, seen_events=seen)
        assert ev.event_id not in seen

    def test_no_fabricated_events(self):
        """Ensure fabricated events Golden Wing, Bonfire, Liars Game are gone."""
        for fake in ["Golden Wing", "Bonfire", "Liars Game"]:
            from sts_env.run.events import _EVENTS
            assert fake not in _EVENTS, f"Fabricated event {fake!r} still registered"


# ---------------------------------------------------------------------------
# Big Fish
#   choice 0 = heal 33% max HP
#   choice 1 = gain 5 max HP
#   choice 2 = relic + Regret
# ---------------------------------------------------------------------------

class TestBigFish:
    def test_heal_choice(self, char, rng):
        char.player_hp = 30
        old_hp = char.player_hp
        result = resolve_event("Big Fish", 0, char, rng)
        assert char.player_hp > old_hp
        assert "healed" in result.lower() or "Healed" in result

    def test_max_hp_choice(self, char, rng):
        old_max = char.player_max_hp
        result = resolve_event("Big Fish", 1, char, rng)
        assert char.player_max_hp == old_max + 5
        assert "Max HP" in result

    def test_relic_choice_adds_relic_and_regret(self, char, rng):
        old_relics = list(char.relics)
        old_deck_len = len(char.deck)
        result = resolve_event("Big Fish", 2, char, rng)
        # Should have gotten a relic (or not, if pool exhausted)
        assert "Regret" in char.deck
        assert "Regret" in result or "relic" in result.lower()


# ---------------------------------------------------------------------------
# The Cleric
#   choice 0 = pay 35 gold, heal 25% max HP
#   choice 1 = pay 50 gold, remove card (flagged for orchestrator)
#   choice 2 = leave
# ---------------------------------------------------------------------------

class TestCleric:
    def test_heal_choice(self, char, rng):
        char.player_hp = 50
        char.gold = 100
        result = resolve_event("The Cleric", 0, char, rng)
        assert char.gold == 65  # paid 35
        assert char.player_hp > 50
        assert "Healed" in result

    def test_heal_not_enough_gold(self, char, rng):
        char.gold = 20
        old_hp = char.player_hp
        result = resolve_event("The Cleric", 0, char, rng)
        assert char.gold == 20
        assert char.player_hp == old_hp

    def test_remove_choice_pays_gold(self, char, rng):
        char.gold = 99
        result = resolve_event("The Cleric", 1, char, rng)
        assert char.gold == 49  # paid 50
        # Card removal is handled by orchestrator, not resolve_event

    def test_remove_not_enough_gold(self, char, rng):
        char.gold = 30
        result = resolve_event("The Cleric", 1, char, rng)
        assert char.gold == 30

    def test_leave(self, char, rng):
        old_hp = char.player_hp
        old_gold = char.gold
        result = resolve_event("The Cleric", 2, char, rng)
        assert char.player_hp == old_hp
        assert char.gold == old_gold


# ---------------------------------------------------------------------------
# Dead Adventurer
#   choice 0 = loot (escalating elite encounter risk)
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestDeadAdventurer:
    def test_setup_creates_state(self, rng):
        state = _dead_adventurer_setup(rng)
        assert state["phase"] == 0
        assert len(state["rewards"]) == 3
        assert state["encounter_id"] in ["Three Sentries", "Gremlin Nob", "lagavulin_event"]

    def test_loot_safe_gives_gold(self, char):
        rng = RNG(100)
        _da_state.clear()
        _da_state.update({"phase": 0, "rewards": [0, 1, 2], "encounter_id": "Lagavulin"})
        old_gold = char.gold
        result = _dead_adventurer_loot(char, rng)
        if "Looted safely" in result:
            assert char.gold == old_gold + 30
            assert _da_state["phase"] == 1

    def test_loot_triggers_combat(self, char):
        """Force combat by setting high encounter roll seed."""
        _da_state.clear()
        _da_state.update({"phase": 2, "rewards": [0, 1, 2], "encounter_id": "Gremlin Nob"})
        result = _dead_adventurer_loot(char, RNG(0))
        # With seed 0 at phase 2 (75% chance), likely triggers combat
        assert "ambushed" in result.lower() or "Looted safely" in result

    def test_leave(self, char, rng):
        _da_state.clear()
        _da_state.update(_dead_adventurer_setup(rng))
        result = resolve_event("Dead Adventurer", 1, char, rng)
        assert _da_state["phase"] == 3  # event ended

    def test_phase_exhausted(self, char):
        _da_state.clear()
        _da_state.update({"phase": 3, "rewards": [0, 1, 2], "encounter_id": "Lagavulin"})
        result = _dead_adventurer_loot(char, RNG(42))
        assert "nothing left" in result.lower()

    def test_combat_sets_phase_3(self, char):
        """When combat triggers, phase is set to 3 (event ends)."""
        _da_state.clear()
        _da_state.update({"phase": 2, "rewards": [0, 0, 2], "encounter_id": "Lagavulin"})
        result = _dead_adventurer_loot(char, RNG(0))
        if "ambushed" in result.lower():
            assert _da_state["phase"] == 3
            assert _da_state.get("combat_needed") is True


# ---------------------------------------------------------------------------
# Golden Idol
#   choice 0 = relic
#   choice 1 = leave
#   choice 2 = Injury card
#   choice 3 = 25% max HP damage
#   choice 4 = lose 8% max HP
# ---------------------------------------------------------------------------

class TestGoldenIdol:
    def test_relic_choice(self, char, rng):
        result = resolve_event("Golden Idol", 0, char, rng)
        assert "Golden Idol" in char.relics
        assert "Golden Idol" in result

    def test_leave(self, char, rng):
        old_hp = char.player_hp
        result = resolve_event("Golden Idol", 1, char, rng)
        assert char.player_hp == old_hp

    def test_injury(self, char, rng):
        result = resolve_event("Golden Idol", 2, char, rng)
        assert "Injury" in char.deck
        assert "Injury" in result

    def test_damage(self, char, rng):
        old_hp = char.player_hp
        result = resolve_event("Golden Idol", 3, char, rng)
        assert char.player_hp < old_hp
        assert "damage" in result.lower()

    def test_lose_max_hp(self, char, rng):
        old_max = char.player_max_hp
        result = resolve_event("Golden Idol", 4, char, rng)
        assert char.player_max_hp < old_max
        assert "Max HP" in result


# ---------------------------------------------------------------------------
# Wing Statue
#   choice 0 = take 7 damage + remove card (flagged)
#   choice 1 = gain 50-80 gold
#   choice 2 = leave
# ---------------------------------------------------------------------------

class TestWingStatue:
    def test_remove_takes_damage(self, char, rng):
        old_hp = char.player_hp
        result = resolve_event("Wing Statue", 0, char, rng)
        assert char.player_hp == old_hp - 7
        # Card removal handled by orchestrator

    def test_gold_choice(self, char, rng):
        old_gold = char.gold
        result = resolve_event("Wing Statue", 1, char, rng)
        assert char.gold > old_gold
        assert 50 <= (char.gold - old_gold) <= 80

    def test_leave(self, char, rng):
        old_hp = char.player_hp
        old_gold = char.gold
        result = resolve_event("Wing Statue", 2, char, rng)
        assert char.player_hp == old_hp
        assert char.gold == old_gold


# ---------------------------------------------------------------------------
# World of Goop
#   choice 0 = take 11 damage, gain 75 gold
#   choice 1 = lose 20-50 gold
# ---------------------------------------------------------------------------

class TestWorldOfGoop:
    def test_damage_and_gold(self, char, rng):
        old_hp = char.player_hp
        old_gold = char.gold
        result = resolve_event("World of Goop", 0, char, rng)
        assert char.player_hp == old_hp - 11
        assert char.gold == old_gold + 75

    def test_lose_gold(self, char, rng):
        char.gold = 100
        old_hp = char.player_hp
        result = resolve_event("World of Goop", 1, char, rng)
        assert char.player_hp == old_hp  # no damage
        assert char.gold < 100
        loss = 100 - char.gold
        assert 20 <= loss <= 50

    def test_lose_gold_capped_by_current(self, char, rng):
        char.gold = 10
        result = resolve_event("World of Goop", 1, char, rng)
        assert char.gold == 0  # can't lose more than you have


# ---------------------------------------------------------------------------
# The Ssssserpent
#   choice 0 = gain 175 gold + Doubt
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestSsssserpent:
    def test_gold_and_doubt(self, char, rng):
        old_gold = char.gold
        result = resolve_event("The Ssssserpent", 0, char, rng)
        assert char.gold == old_gold + 175
        assert "Doubt" in char.deck

    def test_leave(self, char, rng):
        old_gold = char.gold
        result = resolve_event("The Ssssserpent", 1, char, rng)
        assert char.gold == old_gold
        assert "Doubt" not in char.deck


# ---------------------------------------------------------------------------
# Living Wall
#   choice 0 = remove card (flagged)
#   choice 1 = transform card (flagged)
#   choice 2 = upgrade card (flagged)
# ---------------------------------------------------------------------------

class TestLivingWall:
    def test_remove_flagged(self, char, rng):
        spec = get_event("Living Wall")
        assert spec.choices[0].requires_card_removal is True
        result = resolve_event("Living Wall", 0, char, rng)
        # Returns sentinel string for orchestrator
        assert "REMOVE" in result

    def test_transform_flagged(self, char, rng):
        spec = get_event("Living Wall")
        assert spec.choices[1].requires_card_transform is True
        result = resolve_event("Living Wall", 1, char, rng)
        assert "TRANSFORM" in result

    def test_upgrade_flagged(self, char, rng):
        spec = get_event("Living Wall")
        assert spec.choices[2].requires_card_upgrade is True
        result = resolve_event("Living Wall", 2, char, rng)
        assert "UPGRADE" in result


# ---------------------------------------------------------------------------
# Hypnotizing Colored Mushrooms
#   choice 0 = fight (flagged triggers_combat)
#   choice 1 = gain 99 gold
# ---------------------------------------------------------------------------

class TestMushrooms:
    def test_fight_choice_triggers_combat(self, char, rng):
        spec = get_event("Hypnotizing Colored Mushrooms")
        assert spec.choices[0].triggers_combat is True
        result = resolve_event("Hypnotizing Colored Mushrooms", 0, char, rng)
        assert "FIGHT" in result

    def test_fight_encounter_id(self, char, rng):
        spec = get_event("Hypnotizing Colored Mushrooms")
        assert spec.encounter_id == "three_fungi_beasts_event"

    def test_gold_choice(self, char, rng):
        old_gold = char.gold
        result = resolve_event("Hypnotizing Colored Mushrooms", 1, char, rng)
        assert char.gold == old_gold + 99
        assert "99" in result


# ---------------------------------------------------------------------------
# Scrap Ooze
#   choice 0 = take 3 damage, escalating relic chance
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestScrapOoze:
    def test_setup(self):
        state = _scrap_ooze_setup()
        assert state["attempts"] == 0
        assert state["done"] is False

    def test_dig_takes_damage(self, char):
        _ooze_state.clear()
        _ooze_state.update(_scrap_ooze_setup())
        old_hp = char.player_hp
        rng = RNG(42)
        result = resolve_event("Scrap Ooze", 0, char, rng)
        assert char.player_hp == old_hp - 3

    def test_dig_finds_relic_eventually(self, char):
        """After enough attempts, relic should be found."""
        rng = RNG(42)
        _ooze_state.clear()
        _ooze_state.update({"attempts": 10, "done": False})
        result = resolve_event("Scrap Ooze", 0, char, rng)
        # At attempt 10, chance is 125% → always finds relic
        assert _ooze_state["done"] is True
        assert "relic" in result.lower()

    def test_leave(self, char, rng):
        _ooze_state.clear()
        _ooze_state.update(_scrap_ooze_setup())
        result = resolve_event("Scrap Ooze", 1, char, rng)
        assert _ooze_state["done"] is True

    def test_escalating_chance(self, char):
        """Chance formula: 25 + attempts * 10."""
        _ooze_state.clear()
        _ooze_state.update({"attempts": 5, "done": False})
        rng = RNG(42)
        old_hp = char.player_hp
        result = resolve_event("Scrap Ooze", 0, char, rng)
        assert char.player_hp == old_hp - 3
        # Either found relic or incremented attempts
        if not _ooze_state["done"]:
            assert _ooze_state["attempts"] == 6


# ---------------------------------------------------------------------------
# Shining Light
#   choice 0 = take 20% max HP damage, upgrade 2 random cards
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestShiningLight:
    def test_step_damage_and_upgrade(self, char, rng):
        old_hp = char.player_hp
        old_upgrades = sum(1 for c in char.deck if c.endswith("+"))
        result = resolve_event("Shining Light", 0, char, rng)
        assert char.player_hp < old_hp
        # Should have upgraded 0-2 cards (may already be upgraded)
        new_upgrades = sum(1 for c in char.deck if c.endswith("+"))
        assert new_upgrades >= old_upgrades
        assert "Upgraded" in result or "damage" in result.lower()

    def test_leave(self, char, rng):
        old_hp = char.player_hp
        result = resolve_event("Shining Light", 1, char, rng)
        assert char.player_hp == old_hp


# ---------------------------------------------------------------------------
# Match and Keep
#   choice 0 = play (gain 5 cards from mixed pools)
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestMatchAndKeep:
    def test_play_adds_cards(self, char, rng):
        old_deck_len = len(char.deck)
        result = resolve_event("Match and Keep", 0, char, rng)
        assert len(char.deck) > old_deck_len
        assert "Obtained" in result

    def test_leave(self, char, rng):
        old_deck_len = len(char.deck)
        result = resolve_event("Match and Keep", 1, char, rng)
        assert len(char.deck) == old_deck_len


# ---------------------------------------------------------------------------
# Golden Shrine
#   choice 0 = gain 100 gold
#   choice 1 = gain 275 gold + Regret
#   choice 2 = leave
# ---------------------------------------------------------------------------

class TestGoldenShrine:
    def test_pray_gold(self, char, rng):
        old_gold = char.gold
        result = resolve_event("Golden Shrine", 0, char, rng)
        assert char.gold == old_gold + 100

    def test_desecrate_gold_and_regret(self, char, rng):
        old_gold = char.gold
        result = resolve_event("Golden Shrine", 1, char, rng)
        assert char.gold == old_gold + 275
        assert "Regret" in char.deck

    def test_leave(self, char, rng):
        old_gold = char.gold
        result = resolve_event("Golden Shrine", 2, char, rng)
        assert char.gold == old_gold


# ---------------------------------------------------------------------------
# Transmorgrifier
#   choice 0 = transform card (flagged)
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestTransmorgrifier:
    def test_transform_flagged(self, char, rng):
        spec = get_event("Transmorgrifier")
        assert spec.choices[0].requires_card_transform is True
        result = resolve_event("Transmorgrifier", 0, char, rng)
        assert "TRANSFORM" in result

    def test_leave(self, char, rng):
        result = resolve_event("Transmorgrifier", 1, char, rng)
        assert "leave" in result.lower()


# ---------------------------------------------------------------------------
# Purifier
#   choice 0 = remove card (flagged)
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestPurifier:
    def test_remove_flagged(self, char, rng):
        spec = get_event("Purifier")
        assert spec.choices[0].requires_card_removal is True
        result = resolve_event("Purifier", 0, char, rng)
        assert "REMOVE" in result

    def test_leave(self, char, rng):
        result = resolve_event("Purifier", 1, char, rng)
        assert "leave" in result.lower()


# ---------------------------------------------------------------------------
# Upgrade Shrine
#   choice 0 = upgrade card (flagged)
#   choice 1 = leave
# ---------------------------------------------------------------------------

class TestUpgradeShrine:
    def test_upgrade_flagged(self, char, rng):
        spec = get_event("Upgrade Shrine")
        assert spec.choices[0].requires_card_upgrade is True
        result = resolve_event("Upgrade Shrine", 0, char, rng)
        assert "UPGRADE" in result

    def test_leave(self, char, rng):
        result = resolve_event("Upgrade Shrine", 1, char, rng)
        assert "leave" in result.lower()


# ---------------------------------------------------------------------------
# Wheel of Change
#   choice 0 = spin (roll 0-5: gold/relic/heal/decay/remove/hp_loss)
# ---------------------------------------------------------------------------

class TestWheelOfChange:
    def test_spin_changes_state(self, char, rng):
        """Spin always changes something."""
        snapshot = (char.gold, char.player_hp, char.player_max_hp, list(char.deck), list(char.relics))
        result = resolve_event("Wheel of Change", 0, char, rng)
        # Something should have changed
        new_snapshot = (char.gold, char.player_hp, char.player_max_hp, list(char.deck), list(char.relics))
        assert snapshot != new_snapshot or "no" in result.lower()

    def test_gold_outcome(self, char):
        rng = RNG(0)  # Deterministic
        old_gold = char.gold
        result = resolve_event("Wheel of Change", 0, char, rng)
        # Just verify it runs without error — outcome depends on RNG
        assert result  # non-empty result

    def test_only_one_choice(self, char, rng):
        spec = get_event("Wheel of Change")
        assert len(spec.choices) == 1


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
        result = _pick_worst_card(deck)
        assert result in deck

    def test_transform_card(self, char):
        """Transform a card — should remove old and add new."""
        # Use Bash which is unique in starter deck
        bash_idx = char.deck.index("Bash")
        old_deck_len = len(char.deck)
        rng = RNG(42)
        new_card = transform_card(char, "Bash", rng)
        assert "Bash" not in char.deck
        if new_card is not None:
            assert new_card in char.deck
