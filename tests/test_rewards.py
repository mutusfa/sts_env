"""Tests for the rewards system (cards, potions, elite relics)."""

from sts_env.combat.card_pools import pool
from sts_env.combat.cards import CardColor, Rarity
from sts_env.combat.rng import RNG
from sts_env.run.rewards import (
    ALL_RELICS,
    Room,
    roll_card_rewards,
    roll_elite_relic,
    roll_potion_reward,
)


class TestRollEliteRelic:
    """Tests for roll_elite_relic."""

    def test_returns_valid_relic(self, rng: RNG) -> None:
        relic = roll_elite_relic(rng)
        assert relic is not None
        assert relic in ALL_RELICS

    def test_avoids_owned_relics(self, rng: RNG) -> None:
        owned = ["RedSkull", "CentennialPuzzle"]
        relic = roll_elite_relic(rng, owned=owned)
        assert relic is not None
        assert relic not in owned
        assert relic in ALL_RELICS

    def test_returns_none_when_all_owned(self, rng: RNG) -> None:
        relic = roll_elite_relic(rng, owned=list(ALL_RELICS))
        assert relic is None

    def test_returns_none_with_empty_pool(self, rng: RNG) -> None:
        """If owned list covers every relic, result must be None."""
        relic = roll_elite_relic(rng, owned=ALL_RELICS[:])
        assert relic is None

    def test_no_owned_arg_works(self) -> None:
        """Calling without owned should still return a valid relic."""
        r = RNG(seed=42)
        relic = roll_elite_relic(r)
        assert relic in ALL_RELICS


class TestCardRewards:
    """Tests for card reward generation matching C++ GameContext::createCardReward."""

    def test_normal_combat_returns_three(self, rng: RNG) -> None:
        cards, _ = roll_card_rewards(rng)
        assert len(cards) == 3

    def test_elite_combat_returns_three(self, rng: RNG) -> None:
        cards, _ = roll_card_rewards(rng, room=Room.ELITE)
        assert len(cards) == 3

    def test_boss_returns_three(self, rng: RNG) -> None:
        cards, _ = roll_card_rewards(rng, room=Room.BOSS)
        assert len(cards) == 3

    def test_rewards_are_distinct(self) -> None:
        """Cards in a single reward must be unique — no duplicates."""
        for seed in range(60):
            cards, _ = roll_card_rewards(RNG(seed))
            assert len(set(cards)) == len(cards), f"Duplicates in reward (seed={seed}): {cards}"

    def test_boss_room_all_rare(self) -> None:
        """BOSS room always produces cards from the rare pool."""
        rare_pool = set(pool(CardColor.RED, Rarity.RARE))
        for seed in range(20):
            cards, _ = roll_card_rewards(RNG(seed), room=Room.BOSS)
            for card in cards:
                assert card in rare_pool, f"{card} not rare in BOSS reward (seed={seed})"

    def test_factor_resets_to_5_after_boss(self) -> None:
        """BOSS forces all rare; each rare resets factor to 5 → final factor == 5."""
        _, new_factor = roll_card_rewards(RNG(0), room=Room.BOSS)
        assert new_factor == 5

    def test_factor_floor_at_minus_40(self) -> None:
        """card_rarity_factor must never go below -40."""
        _, new_factor = roll_card_rewards(RNG(0), card_rarity_factor=-40)
        assert new_factor >= -40

    def test_factor_decreases_with_very_positive_start(self) -> None:
        """A very high factor forces COMMON cards; each COMMON decrements factor by 1."""
        # factor=+100 makes roll always >= rare/uncommon threshold → all COMMON
        # 3 commons → factor should decrease by 3 (floored at -40, starting at 100 → 97)
        _, new_factor = roll_card_rewards(RNG(0), card_rarity_factor=100)
        assert new_factor == 97  # started 100, 3 commons → 100 - 3 = 97

    def test_elite_has_higher_rare_rate_than_monster(self) -> None:
        """ELITE rare chance (~10%) must produce more rares than MONSTER (~3%)."""
        rare_pool = set(pool(CardColor.RED, Rarity.RARE))
        elite_rares = 0
        monster_rares = 0
        for seed in range(300):
            cards_e, _ = roll_card_rewards(RNG(seed), room=Room.ELITE)
            cards_m, _ = roll_card_rewards(RNG(seed), room=Room.MONSTER)
            elite_rares += sum(1 for c in cards_e if c in rare_pool)
            monster_rares += sum(1 for c in cards_m if c in rare_pool)
        assert elite_rares > monster_rares

    def test_no_guaranteed_rare_in_elite_slot_0(self) -> None:
        """ELITE must NOT always have a rare in slot 0 (old guaranteed-rare hack removed)."""
        rare_pool = set(pool(CardColor.RED, Rarity.RARE))
        found_non_rare = False
        for seed in range(50):
            cards, _ = roll_card_rewards(RNG(seed), room=Room.ELITE)
            if cards[0] not in rare_pool:
                found_non_rare = True
                break
        assert found_non_rare, "Slot 0 was always rare over 50 seeds — guaranteed-rare hack may still be active"


class TestPotionReward:
    """Smoke test for potion rewards."""

    def test_returns_potion_or_none(self, rng: RNG) -> None:
        result = roll_potion_reward(rng)
        assert result is None or isinstance(result, str)
