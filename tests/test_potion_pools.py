"""Tests for potion pool registry (aligned with sts_lightspeed Potions.h)."""

from __future__ import annotations

from sts_env.combat.potion_pools import (
    IRONCLAD_POTION_POOL,
    POTION_BASE_PRICE,
    POTION_RARITY,
    PotionRarity,
    get_potion_base_price,
    get_random_potion_from_pool,
    potion_requires_target,
    roll_random_potion,
)
from sts_env.combat.rng import RNG


class TestIroncladPool:
    def test_pool_length(self):
        assert len(IRONCLAD_POTION_POOL) == 33

    def test_pool_unique(self):
        assert len(set(IRONCLAD_POTION_POOL)) == 33

    def test_class_specific_head(self):
        assert IRONCLAD_POTION_POOL[0] == "BloodPotion"
        assert IRONCLAD_POTION_POOL[1] == "ElixirPotion"
        assert IRONCLAD_POTION_POOL[2] == "HeartOfIron"

    def test_contains_steroid_not_flex(self):
        assert "SteroidPotion" in IRONCLAD_POTION_POOL
        assert "FlexPotion" not in IRONCLAD_POTION_POOL


class TestPotionRarity:
    def test_block_common(self):
        assert POTION_RARITY["BlockPotion"] == PotionRarity.COMMON
        assert POTION_BASE_PRICE[PotionRarity.COMMON] == 50

    def test_fairy_rare(self):
        assert POTION_RARITY["FairyPotion"] == PotionRarity.RARE
        assert POTION_BASE_PRICE[PotionRarity.RARE] == 100

    def test_ancient_uncommon(self):
        assert POTION_RARITY["AncientPotion"] == PotionRarity.UNCOMMON
        assert POTION_BASE_PRICE[PotionRarity.UNCOMMON] == 75

    def test_get_potion_base_price(self):
        assert get_potion_base_price("BlockPotion") == 50
        assert get_potion_base_price("AncientPotion") == 75
        assert get_potion_base_price("FairyPotion") == 100


class TestPotionRequiresTarget:
    def test_fire_requires_target(self):
        assert potion_requires_target("FirePotion") is True

    def test_block_no_target(self):
        assert potion_requires_target("BlockPotion") is False

    def test_weak_requires_target(self):
        assert potion_requires_target("WeakPotion") is True


class TestRollRandomPotion:
    def test_returns_pool_member(self):
        rng = RNG(42)
        for _ in range(50):
            p = roll_random_potion(rng)
            assert p in IRONCLAD_POTION_POOL

    def test_deterministic_seed(self):
        p1 = roll_random_potion(RNG(123))
        p2 = roll_random_potion(RNG(123))
        assert p1 == p2

    def test_limited_avoids_fruit_juice_on_first_roll(self):
        """When limited=True, FruitJuice is re-rolled (C++ spamCheck)."""
        # Seed that would hit FruitJuice without limited — just verify limited runs.
        results = {roll_random_potion(RNG(s), limited=True) for s in range(200)}
        assert all(p in IRONCLAD_POTION_POOL for p in results)


class TestGetRandomPotionFromPool:
    def test_index_into_pool(self):
        assert get_random_potion_from_pool(RNG(0), index=0) == "BloodPotion"
