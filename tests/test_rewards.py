"""Tests for the rewards system (cards, potions, elite relics)."""

from sts_env.combat.card_pools import pool
from sts_env.combat.cards import CardColor, Rarity
from sts_env.combat.rng import RNG
from sts_env.run.rewards import (
    ALL_RELICS,
    BOSS_RELICS,
    COMBAT_GOLD,
    COMMON_RELICS,
    UNCOMMON_RELICS,
    RARE_RELICS,
    CombatRewardOffer,
    Room,
    roll_boss_relic_choices,
    roll_card_rewards,
    roll_combat_reward_offer,
    roll_elite_relic,
    roll_elite_relic_tier,
    roll_potion_reward,
)


class TestEliteRelicTier:
    """Tests for roll_elite_relic_tier — mirrors returnRandomRelicTierElite."""

    def test_returns_one_of_three_tiers(self, rng: RNG) -> None:
        from sts_env.run.rewards import RelicTier
        tier = roll_elite_relic_tier(rng)
        assert tier in (RelicTier.COMMON, RelicTier.UNCOMMON, RelicTier.RARE)

    def test_roll_below_50_is_common(self) -> None:
        from unittest.mock import patch
        from sts_env.run.rewards import RelicTier
        with patch.object(RNG, "randint", return_value=49):
            tier = roll_elite_relic_tier(RNG(0))
        assert tier == RelicTier.COMMON

    def test_roll_above_82_is_rare(self) -> None:
        from unittest.mock import patch
        from sts_env.run.rewards import RelicTier
        with patch.object(RNG, "randint", return_value=83):
            tier = roll_elite_relic_tier(RNG(0))
        assert tier == RelicTier.RARE

    def test_roll_50_to_82_is_uncommon(self) -> None:
        from unittest.mock import patch
        from sts_env.run.rewards import RelicTier
        with patch.object(RNG, "randint", return_value=66):
            tier = roll_elite_relic_tier(RNG(0))
        assert tier == RelicTier.UNCOMMON

    def test_distribution_roughly_matches_sts(self) -> None:
        """50% common, ~33% uncommon, ~17% rare over many rolls."""
        from sts_env.run.rewards import RelicTier
        counts: dict[RelicTier, int] = {RelicTier.COMMON: 0, RelicTier.UNCOMMON: 0, RelicTier.RARE: 0}
        n = 1000
        for seed in range(n):
            counts[roll_elite_relic_tier(RNG(seed))] += 1
        assert 400 < counts[RelicTier.COMMON] < 600, f"Common out of range: {counts}"
        assert 250 < counts[RelicTier.UNCOMMON] < 420, f"Uncommon out of range: {counts}"
        assert 100 < counts[RelicTier.RARE] < 250, f"Rare out of range: {counts}"


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

    def test_can_return_rare_relic(self) -> None:
        """Elite relics have ~17% rare chance — should appear within 100 seeds."""
        found_rare = any(roll_elite_relic(RNG(seed)) in RARE_RELICS for seed in range(100))
        assert found_rare, "No rare relic appeared in 100 seeds — tier roll likely missing"

    def test_can_return_uncommon_relic(self) -> None:
        found_uncommon = any(roll_elite_relic(RNG(seed)) in UNCOMMON_RELICS for seed in range(100))
        assert found_uncommon

    def test_tier_fallback_common_to_uncommon(self) -> None:
        """When common pool is exhausted, should fall back to uncommon."""
        relic = roll_elite_relic(RNG(0), owned=list(COMMON_RELICS))
        assert relic is not None
        assert relic in UNCOMMON_RELICS or relic in RARE_RELICS


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


class TestBossRelicChoices:
    """Tests for roll_boss_relic_choices."""

    def test_returns_up_to_three_choices(self, rng: RNG) -> None:
        choices = roll_boss_relic_choices(rng)
        assert 1 <= len(choices) <= 3

    def test_choices_come_from_boss_pool(self, rng: RNG) -> None:
        choices = roll_boss_relic_choices(rng)
        for relic in choices:
            assert relic in BOSS_RELICS

    def test_no_duplicates_within_offer(self) -> None:
        for seed in range(30):
            choices = roll_boss_relic_choices(RNG(seed))
            assert len(set(choices)) == len(choices), f"Duplicate in boss relic offer (seed={seed}): {choices}"

    def test_owned_relics_excluded(self, rng: RNG) -> None:
        owned = BOSS_RELICS[:2]
        choices = roll_boss_relic_choices(rng, owned=owned)
        for relic in choices:
            assert relic not in owned

    def test_returns_empty_when_all_owned(self, rng: RNG) -> None:
        choices = roll_boss_relic_choices(rng, owned=list(BOSS_RELICS))
        assert choices == []

    def test_deterministic_with_same_rng_seed(self) -> None:
        r1, r2 = RNG(99), RNG(99)
        assert roll_boss_relic_choices(r1) == roll_boss_relic_choices(r2)

    def test_boss_pool_excludes_common_and_starter_relics(self) -> None:
        """Boss pool must not contain starter (BurningBlood) or common-tier relics."""
        forbidden = {"BurningBlood"} | set(ALL_RELICS)
        overlap = forbidden & set(BOSS_RELICS)
        assert not overlap, f"Boss pool contains non-boss relics: {overlap}"


class TestPotionReward:
    """Smoke test for potion rewards."""

    def test_returns_potion_or_none(self, rng: RNG) -> None:
        result = roll_potion_reward(rng)
        assert result is None or isinstance(result, str)


class TestCombatGold:
    """Tests for COMBAT_GOLD constant."""

    def test_all_rooms_have_gold_values(self) -> None:
        assert Room.MONSTER in COMBAT_GOLD
        assert Room.ELITE in COMBAT_GOLD
        assert Room.BOSS in COMBAT_GOLD

    def test_elite_more_gold_than_monster(self) -> None:
        assert COMBAT_GOLD[Room.ELITE] > COMBAT_GOLD[Room.MONSTER]

    def test_gold_values_positive(self) -> None:
        for gold in COMBAT_GOLD.values():
            assert gold > 0


class TestCombatRewardOffer:
    """Tests for CombatRewardOffer dataclass and roll_combat_reward_offer."""

    def test_returns_offer_and_factor(self, rng: RNG) -> None:
        offer, new_factor = roll_combat_reward_offer(rng, Room.MONSTER)
        assert isinstance(offer, CombatRewardOffer)
        assert isinstance(new_factor, int)

    def test_offer_has_three_cards(self, rng: RNG) -> None:
        offer, _ = roll_combat_reward_offer(rng, Room.MONSTER)
        assert len(offer.card_choices) == 3

    def test_offer_gold_matches_combat_gold_constant(self) -> None:
        for room in (Room.MONSTER, Room.ELITE, Room.BOSS):
            offer, _ = roll_combat_reward_offer(RNG(0), room)
            assert offer.gold == COMBAT_GOLD[room]

    def test_offer_potion_is_str_or_none(self, rng: RNG) -> None:
        offer, _ = roll_combat_reward_offer(rng, Room.MONSTER)
        assert offer.potion is None or isinstance(offer.potion, str)

    def test_elite_offer_has_correct_gold(self, rng: RNG) -> None:
        offer, _ = roll_combat_reward_offer(rng, Room.ELITE)
        assert offer.gold == COMBAT_GOLD[Room.ELITE]

    def test_boss_offer_has_correct_gold(self, rng: RNG) -> None:
        offer, _ = roll_combat_reward_offer(rng, Room.BOSS)
        assert offer.gold == COMBAT_GOLD[Room.BOSS]

    def test_factor_propagated(self, rng: RNG) -> None:
        """new_card_rarity_factor must equal what roll_card_rewards would return."""
        r1, r2 = RNG(77), RNG(77)
        _, factor_from_offer = roll_combat_reward_offer(r1, Room.MONSTER, card_rarity_factor=3)
        _, factor_from_roll = roll_card_rewards(r2, room=Room.MONSTER, card_rarity_factor=3)
        assert factor_from_offer == factor_from_roll

    def test_deterministic_with_same_seed(self) -> None:
        r1, r2 = RNG(42), RNG(42)
        offer1, f1 = roll_combat_reward_offer(r1, Room.MONSTER)
        offer2, f2 = roll_combat_reward_offer(r2, Room.MONSTER)
        assert offer1.card_choices == offer2.card_choices
        assert offer1.potion == offer2.potion
        assert offer1.gold == offer2.gold
        assert f1 == f2
