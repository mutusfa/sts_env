"""Tests for treasure room logic."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.treasure import (
    _GOLD_MAX,
    _GOLD_MIN,
    _RELIC_DROP_CHANCE,
    _TREASURE_RELICS,
    TreasureResult,
    open_treasure,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rng(randint_val: int = 25, random_val: float = 1.0, choice_val: str = "Anchor") -> MagicMock:
    """Build a mock RNG with canned return values."""
    rng = MagicMock(spec=RNG)
    rng.randint.return_value = randint_val
    rng.random.return_value = random_val
    rng.choice.return_value = choice_val
    return rng


# ---------------------------------------------------------------------------
# 1. Gold is within the expected range
# ---------------------------------------------------------------------------

class TestGoldRange:
    """Gold found should always be within [GOLD_MIN, GOLD_MAX]."""

    def test_gold_never_below_minimum(self) -> None:
        """Across many seeds, gold must never drop below _GOLD_MIN."""
        character = Character.ironclad()
        for seed in range(200):
            c = Character.ironclad()
            result = open_treasure(c, RNG(seed))
            assert result.gold_found >= _GOLD_MIN

    def test_gold_never_above_maximum(self) -> None:
        """Across many seeds, gold must never exceed _GOLD_MAX."""
        for seed in range(200):
            c = Character.ironclad()
            result = open_treasure(c, RNG(seed))
            assert result.gold_found <= _GOLD_MAX

    def test_gold_is_integer(self) -> None:
        """Gold found should be an int, not a float."""
        c = Character.ironclad()
        result = open_treasure(c, RNG(42))
        assert isinstance(result.gold_found, int)


# ---------------------------------------------------------------------------
# 2. Gold is added to character
# ---------------------------------------------------------------------------

class TestGoldAddition:
    """Gold from the chest must be added to the character's gold."""

    def test_gold_added_to_character(self) -> None:
        rng = _make_rng(randint_val=30)
        c = Character.ironclad()
        starting_gold = c.gold
        result = open_treasure(c, rng)
        assert c.gold == starting_gold + result.gold_found

    def test_gold_accumulates_over_multiple_opens(self) -> None:
        c = Character.ironclad()
        starting_gold = c.gold
        total_found = 0
        for _ in range(5):
            rng = _make_rng(randint_val=25, random_val=1.0)
            result = open_treasure(c, rng)
            total_found += result.gold_found
        assert c.gold == starting_gold + total_found


# ---------------------------------------------------------------------------
# 3. Relic drop chance
# ---------------------------------------------------------------------------

class TestRelicDrop:
    """Relic should drop when RNG rolls below the threshold."""

    def test_relic_drops_when_random_below_threshold(self) -> None:
        rng = _make_rng(random_val=0.0, choice_val="Lantern")
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.relic_found == "Lantern"
        assert "Lantern" in c.relics

    def test_no_relic_when_random_above_threshold(self) -> None:
        rng = _make_rng(random_val=0.99)
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.relic_found is None
        # Only the starter relic should remain
        assert len(c.relics) == 1

    def test_relic_exactly_at_threshold_does_not_drop(self) -> None:
        """rng.random() == _RELIC_DROP_CHANCE should NOT drop (strict <)."""
        rng = _make_rng(random_val=_RELIC_DROP_CHANCE)
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.relic_found is None

    def test_just_below_threshold_drops(self) -> None:
        """A value just below threshold should still drop."""
        rng = _make_rng(random_val=_RELIC_DROP_CHANCE - 1e-9, choice_val="Shuriken")
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.relic_found == "Shuriken"


# ---------------------------------------------------------------------------
# 4. TreasureResult fields
# ---------------------------------------------------------------------------

class TestTreasureResult:
    """TreasureResult should faithfully report what happened."""

    def test_result_matches_character_gold(self) -> None:
        rng = _make_rng(randint_val=22)
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.gold_found == 22

    def test_result_matches_relic(self) -> None:
        rng = _make_rng(random_val=0.1, choice_val="Nunchaku")
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.relic_found == "Nunchaku"

    def test_default_result_fields(self) -> None:
        """Default TreasureResult should have zero gold and no relic."""
        result = TreasureResult()
        assert result.gold_found == 0
        assert result.relic_found is None


# ---------------------------------------------------------------------------
# 5. Relic is from the treasure pool
# ---------------------------------------------------------------------------

class TestRelicPool:
    """Any relic dropped must come from the treasure relic pool."""

    def test_all_relics_are_from_pool(self) -> None:
        """Over many seeds, every relic found must be in _TREASURE_RELICS."""
        relics_found = set()
        for seed in range(500):
            c = Character.ironclad()
            result = open_treasure(c, RNG(seed))
            if result.relic_found is not None:
                relics_found.add(result.relic_found)
        for r in relics_found:
            assert r in _TREASURE_RELICS, f"Relic {r!r} not in treasure pool"
