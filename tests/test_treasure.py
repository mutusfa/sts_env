"""Tests for treasure room logic."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.treasure import (
    _CHEST_GOLD_AMOUNTS,
    _CHEST_GOLD_CHANCES,
    _LARGE_CHEST_CHANCE,
    _MEDIUM_CHEST_CHANCE,
    _SMALL_CHEST_CHANCE,
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
# 1. Chest model constants
# ---------------------------------------------------------------------------

class TestChestModel:
    """Treasure constants should mirror C++ chest behavior."""

    def test_chest_size_roll_chances(self) -> None:
        assert _SMALL_CHEST_CHANCE == 50
        assert _MEDIUM_CHEST_CHANCE == 33
        assert _LARGE_CHEST_CHANCE == 17

    def test_gold_chance_by_size(self) -> None:
        assert _CHEST_GOLD_CHANCES == (50, 35, 50)

    def test_gold_base_by_size(self) -> None:
        assert _CHEST_GOLD_AMOUNTS == (25, 50, 75)


# ---------------------------------------------------------------------------
# 2. Relic reward behavior
# ---------------------------------------------------------------------------

class TestRelicReward:
    """Opening treasure should always grant exactly one relic."""

    def test_relic_always_awarded(self) -> None:
        # Force a no-gold path via high first roll to keep this focused on relic behavior.
        rng = _make_rng(randint_val=99, random_val=0.5, choice_val="Lantern")
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.relic_found == "Lantern"
        assert c.relics.count("Lantern") == 1


# ---------------------------------------------------------------------------
# 3. Gold reward behavior
# ---------------------------------------------------------------------------

class TestGoldReward:
    """Gold reward should follow chest-size chance and amount variance."""

    def test_no_gold_when_roll_fails_chance(self) -> None:
        # small chest when roll=0, then no-gold when roll=99
        rng = MagicMock(spec=RNG)
        rng.randint.side_effect = [0, 99]
        rng.random.return_value = 0.5
        rng.choice.return_value = "Anchor"
        c = Character.ironclad()
        before = c.gold
        result = open_treasure(c, rng)
        assert result.gold_found == 0
        assert c.gold == before

    def test_gold_in_small_chest_range(self) -> None:
        # small chest and gold-enabled roll
        rng = MagicMock(spec=RNG)
        rng.randint.side_effect = [0, 0]
        rng.random.return_value = 0.0  # 90% of base
        rng.choice.return_value = "Anchor"
        c = Character.ironclad()
        before = c.gold
        result = open_treasure(c, rng)
        assert result.gold_found == 22  # round(25 * 0.9)
        assert c.gold == before + 22


# ---------------------------------------------------------------------------
# 4. TreasureResult fields
# ---------------------------------------------------------------------------

class TestTreasureResult:
    """TreasureResult should faithfully report what happened."""

    def test_result_matches_character_gold(self) -> None:
        rng = MagicMock(spec=RNG)
        rng.randint.side_effect = [0, 0]
        rng.random.return_value = 0.0
        rng.choice.return_value = "Anchor"
        c = Character.ironclad()
        result = open_treasure(c, rng)
        assert result.gold_found == 22

    def test_result_matches_relic(self) -> None:
        rng = MagicMock(spec=RNG)
        rng.randint.side_effect = [99, 99]
        rng.random.return_value = 0.1
        rng.choice.return_value = "Nunchaku"
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
            relics_found.add(result.relic_found)
        for r in relics_found:
            assert r in _TREASURE_RELICS, f"Relic {r!r} not in treasure pool"
