"""Tests for the rewards system (cards, potions, elite relics)."""

from sts_env.combat.rng import RNG
from sts_env.run.rewards import (
    ALL_RELICS,
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
    """Smoke tests for card rewards (existing functionality)."""

    def test_normal_combat_returns_three(self, rng: RNG) -> None:
        cards = roll_card_rewards(rng, is_elite=False)
        assert len(cards) == 3

    def test_elite_combat_returns_three(self, rng: RNG) -> None:
        cards = roll_card_rewards(rng, is_elite=True)
        assert len(cards) == 3


class TestPotionReward:
    """Smoke test for potion rewards."""

    def test_returns_potion_or_none(self, rng: RNG) -> None:
        result = roll_potion_reward(rng)
        assert result is None or isinstance(result, str)
