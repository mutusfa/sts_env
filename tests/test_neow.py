"""Tests for Neow blessing system."""
import pytest

from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.neow import (
    NeowChoice,
    NeowOption,
    apply_neow,
    roll_neow_options,
    _COMMON_RELIC_POOL,
)


# ---------------------------------------------------------------------------
# roll_neow_options
# ---------------------------------------------------------------------------

class TestRollNeowOptions:
    def test_returns_four_options(self):
        rng = RNG(0)
        options = roll_neow_options(rng)
        assert len(options) == 4

    def test_all_choices_unique(self):
        rng = RNG(0)
        options = roll_neow_options(rng)
        choices = [o.choice for o in options]
        assert len(set(choices)) == 4

    def test_covers_all_enum_values(self):
        rng = RNG(0)
        options = roll_neow_options(rng)
        choices = {o.choice for o in options}
        assert choices == set(NeowChoice)

    def test_options_have_descriptions(self):
        rng = RNG(0)
        options = roll_neow_options(rng)
        for opt in options:
            assert isinstance(opt, NeowOption)
            assert isinstance(opt.description, str)
            assert len(opt.description) > 0


# ---------------------------------------------------------------------------
# apply_neow — MAX_HP
# ---------------------------------------------------------------------------

class TestMaxHp:
    def test_increases_max_and_current_hp(self):
        rng = RNG(42)
        char = Character.ironclad()
        old_hp = char.player_hp
        old_max = char.player_max_hp

        result = apply_neow(NeowChoice.MAX_HP, char, rng)

        assert char.player_max_hp == old_max + 7
        assert char.player_hp == old_hp + 7
        assert "+7 Max HP" in result


# ---------------------------------------------------------------------------
# apply_neow — RANDOM_RELIC
# ---------------------------------------------------------------------------

class TestRandomRelic:
    def test_adds_a_relic(self):
        rng = RNG(42)
        char = Character.ironclad()
        old_relics = list(char.relics)

        result = apply_neow(NeowChoice.RANDOM_RELIC, char, rng)

        assert len(char.relics) == len(old_relics) + 1
        assert "Gained relic:" in result

    def test_avoids_duplicates(self):
        rng = RNG(42)
        char = Character.ironclad()
        # Pre-give all common relics to the character
        for relic in _COMMON_RELIC_POOL:
            char.relics.append(relic)

        result = apply_neow(NeowChoice.RANDOM_RELIC, char, rng)

        assert result == "No available relics"

    def test_relic_from_pool(self):
        rng = RNG(42)
        char = Character.ironclad()

        apply_neow(NeowChoice.RANDOM_RELIC, char, rng)

        added = [r for r in char.relics if r != "BurningBlood"]
        assert len(added) == 1
        assert added[0] in _COMMON_RELIC_POOL


# ---------------------------------------------------------------------------
# apply_neow — REMOVE_CARD
# ---------------------------------------------------------------------------

class TestRemoveCard:
    def test_removes_strike_first(self):
        rng = RNG(42)
        char = Character.ironclad()
        strike_count = char.deck.count("Strike")
        defend_count = char.deck.count("Defend")

        result = apply_neow(NeowChoice.REMOVE_CARD, char, rng)

        assert "Removed Strike" in result
        assert char.deck.count("Strike") == strike_count - 1
        # Defend unchanged
        assert char.deck.count("Defend") == defend_count

    def test_removes_defend_when_no_strike(self):
        rng = RNG(42)
        char = Character.ironclad()
        # Remove all Strikes
        while "Strike" in char.deck:
            char.deck.remove("Strike")
        defend_count = char.deck.count("Defend")

        result = apply_neow(NeowChoice.REMOVE_CARD, char, rng)

        assert "Removed Defend" in result
        assert char.deck.count("Defend") == defend_count - 1

    def test_no_basic_cards_returns_message(self):
        rng = RNG(42)
        char = Character.ironclad()
        # Remove all Strikes and Defends
        char.deck = [c for c in char.deck if c not in ("Strike", "Defend")]

        result = apply_neow(NeowChoice.REMOVE_CARD, char, rng)

        assert result == "No basic cards to remove"

    def test_removes_only_one_card(self):
        rng = RNG(42)
        char = Character.ironclad()
        deck_len_before = len(char.deck)

        apply_neow(NeowChoice.REMOVE_CARD, char, rng)

        assert len(char.deck) == deck_len_before - 1


# ---------------------------------------------------------------------------
# apply_neow — RANDOM_CARD
# ---------------------------------------------------------------------------

class TestRandomCard:
    def test_adds_card_to_deck(self):
        rng = RNG(42)
        char = Character.ironclad()
        deck_len_before = len(char.deck)

        result = apply_neow(NeowChoice.RANDOM_CARD, char, rng)

        assert len(char.deck) == deck_len_before + 1
        assert "Added" in result
        assert "to deck" in result

    def test_added_card_is_in_pool(self):
        from sts_env.run.neow import _NEOW_CARD_POOL

        rng = RNG(42)
        char = Character.ironclad()

        apply_neow(NeowChoice.RANDOM_CARD, char, rng)

        added_card = char.deck[-1]
        assert added_card in _NEOW_CARD_POOL

    def test_deterministic_with_seed(self):
        char1 = Character.ironclad()
        char2 = Character.ironclad()

        rng1 = RNG(123)
        rng2 = RNG(123)

        apply_neow(NeowChoice.RANDOM_CARD, char1, rng1)
        apply_neow(NeowChoice.RANDOM_CARD, char2, rng2)

        assert char1.deck[-1] == char2.deck[-1]
