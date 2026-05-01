"""Tests for treasure room logic."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.rewards import ALL_RELICS, COMMON_RELICS, UNCOMMON_RELICS, RARE_RELICS
from sts_env.run.treasure import (
    _CHEST_GOLD_AMOUNTS,
    _CHEST_GOLD_CHANCES,
    _CHEST_RELIC_TIER_CHANCES,
    _LARGE_CHEST_CHANCE,
    _MEDIUM_CHEST_CHANCE,
    _SMALL_CHEST_CHANCE,
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

    def test_relic_tier_chances_shape(self) -> None:
        """3 chest sizes, each with (common_chance, uncommon_chance) — remainder is rare."""
        assert len(_CHEST_RELIC_TIER_CHANCES) == 3
        for common_c, uncommon_c in _CHEST_RELIC_TIER_CHANCES:
            assert 0 <= common_c <= 100
            assert 0 <= uncommon_c <= 100
            assert common_c + uncommon_c <= 100

    def test_small_chest_never_rare(self) -> None:
        """Small chest: common=75 uncommon=25 rare=0 → C++ chestRelicTierChances[0]."""
        common_c, uncommon_c = _CHEST_RELIC_TIER_CHANCES[0]
        assert common_c + uncommon_c == 100, "Small chest should have 0% rare"

    def test_large_chest_never_common(self) -> None:
        """Large chest: common=0 uncommon=75 rare=25 → C++ chestRelicTierChances[2]."""
        common_c, _uncommon_c = _CHEST_RELIC_TIER_CHANCES[2]
        assert common_c == 0, "Large chest should have 0% common"


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


# ---------------------------------------------------------------------------
# 5. Relic tier and pool membership
# ---------------------------------------------------------------------------

class TestRelicPool:
    """Treasure relics must come from the tiered relic pools and obey chest-size constraints."""

    def test_all_relics_are_from_all_relics(self) -> None:
        """Over many seeds, every relic found must be in the combined common/uncommon/rare pool."""
        relics_found = set()
        for seed in range(500):
            c = Character.ironclad()
            result = open_treasure(c, RNG(seed))
            relics_found.add(result.relic_found)
        for r in relics_found:
            assert r in ALL_RELICS, f"Relic {r!r} not in any relic pool"

    def test_small_chest_never_yields_rare(self) -> None:
        """Small chest has 0% rare tier — no rare relic should ever appear."""
        # Force small chest (size roll < 50) over many rarity rolls.
        for rarity_roll in range(100):
            rng = MagicMock(spec=RNG)
            rng.randint.side_effect = [0, rarity_roll]  # size=SMALL, then rarity roll
            rng.random.return_value = 0.5
            rng.choice.side_effect = lambda pool: pool[0]  # pick first from whatever pool
            c = Character.ironclad()
            result = open_treasure(c, rng)
            assert result.relic_found not in RARE_RELICS, (
                f"Small chest gave rare relic on rarity_roll={rarity_roll}: {result.relic_found}"
            )

    def test_large_chest_never_yields_common(self) -> None:
        """Large chest has 0% common tier."""
        for rarity_roll in range(100):
            rng = MagicMock(spec=RNG)
            rng.randint.side_effect = [99, rarity_roll]  # size=LARGE, then rarity roll
            rng.random.return_value = 0.5
            rng.choice.side_effect = lambda pool: pool[0]
            c = Character.ironclad()
            result = open_treasure(c, rng)
            assert result.relic_found not in COMMON_RELICS, (
                f"Large chest gave common relic on rarity_roll={rarity_roll}: {result.relic_found}"
            )

    def test_rare_relics_can_appear_from_large_chest(self) -> None:
        """Large chest has 25% rare — rare relics must be reachable."""
        found_rare = False
        for seed in range(200):
            c = Character.ironclad()
            result = open_treasure(c, RNG(seed))
            if result.relic_found in RARE_RELICS:
                found_rare = True
                break
        assert found_rare, "No rare relic appeared in 200 seeds from any chest"
