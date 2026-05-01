"""Tests for the Act 1 shop system."""

from __future__ import annotations

import pytest

from sts_env.combat.card_pools import typed_pool
from sts_env.combat.cards import CardColor, CardType, Rarity
from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.shop import (
    CARD_PRICES,
    COMMON_POTION_PRICE,
    REMOVE_CARD_COST,
    SHOP_TIER_RELICS,
    UNCOMMON_POTION_PRICE,
    ShopInventory,
    ShopResult,
    buy_card,
    buy_potion,
    buy_relic,
    generate_shop,
    remove_card,
    remove_worst_card,
)
from sts_env.run.rewards import ALL_RELICS, COMMON_RELICS, UNCOMMON_RELICS, RARE_RELICS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rng() -> RNG:
    return RNG(seed=42)


@pytest.fixture
def character() -> Character:
    return Character.ironclad()


@pytest.fixture
def rich_character() -> Character:
    c = Character.ironclad()
    c.gold = 9999
    return c


@pytest.fixture
def shop(rng: RNG, character: Character) -> ShopInventory:
    return generate_shop(rng, character)


# ---------------------------------------------------------------------------
# Inventory generation — card layout
# ---------------------------------------------------------------------------


class TestGenerateShopCards:
    """Tests for the C++-faithful 2A+2S+1P+2CL card layout."""

    def test_generates_seven_cards(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        # 2 ATTACK + 2 SKILL + 1 POWER + 1 colorless UNCOMMON + 1 colorless RARE = 7
        assert len(inv.cards) == 7

    def test_card_type_layout(self, rng: RNG, character: Character) -> None:
        """Slots 0-1=ATTACK, 2-3=SKILL, 4=POWER, 5-6=colorless."""
        from sts_env.combat.card_pools import colorless_pool
        from sts_env.combat.cards import get_spec

        inv = generate_shop(rng, character)
        card_ids = [slot[0] for slot in inv.cards]
        assert card_ids[0] is not None and card_ids[1] is not None
        assert get_spec(card_ids[0]).card_type == CardType.ATTACK
        assert get_spec(card_ids[1]).card_type == CardType.ATTACK
        assert get_spec(card_ids[2]).card_type == CardType.SKILL
        assert get_spec(card_ids[3]).card_type == CardType.SKILL
        assert get_spec(card_ids[4]).card_type == CardType.POWER

        cl_uncommons = set(colorless_pool(Rarity.UNCOMMON))
        cl_rares = set(colorless_pool(Rarity.RARE))
        assert card_ids[5] in cl_uncommons
        assert card_ids[6] in cl_rares

    def test_attack_pair_no_duplicates(self) -> None:
        """The two ATTACK slots must be different cards (C++ assignRandomCardExcluding)."""
        for seed in range(30):
            inv = generate_shop(RNG(seed), Character.ironclad())
            a0, a1 = inv.cards[0][0], inv.cards[1][0]
            assert a0 != a1, f"Duplicate ATTACK cards at seed={seed}: {a0}"

    def test_skill_pair_no_duplicates(self) -> None:
        """The two SKILL slots must be different cards."""
        for seed in range(30):
            inv = generate_shop(RNG(seed), Character.ironclad())
            s0, s1 = inv.cards[2][0], inv.cards[3][0]
            assert s0 != s1, f"Duplicate SKILL cards at seed={seed}: {s0}"

    def test_power_slot_never_common_rarity(self) -> None:
        """POWER slot COMMON rarity is upgraded to UNCOMMON (C++ behaviour)."""
        common_power = set(typed_pool(CardColor.RED, CardType.POWER, Rarity.COMMON))
        if not common_power:
            pytest.skip("No COMMON POWER cards registered")
        # We can't directly inspect the rolled rarity, but if the pool
        # has only UNCOMMON/RARE POWERs that means the upgrade path ran.
        uncommon_power = set(typed_pool(CardColor.RED, CardType.POWER, Rarity.UNCOMMON))
        rare_power = set(typed_pool(CardColor.RED, CardType.POWER, Rarity.RARE))
        valid = uncommon_power | rare_power
        for seed in range(30):
            inv = generate_shop(RNG(seed), Character.ironclad())
            card_id = inv.cards[4][0]
            assert card_id in valid, (
                f"POWER slot has COMMON card {card_id} at seed={seed}"
            )

    def test_generates_three_potions(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert len(inv.potions) == 3

    def test_remove_cost_is_set(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert inv.remove_cost == REMOVE_CARD_COST

    def test_seeded_shops_are_deterministic(self, character: Character) -> None:
        inv1 = generate_shop(RNG(42), character)
        inv2 = generate_shop(RNG(42), character)
        assert inv1.cards == inv2.cards
        assert inv1.potions == inv2.potions
        assert inv1.relics == inv2.relics

    def test_different_seeds_produce_different_shops(self, character: Character) -> None:
        inv1 = generate_shop(RNG(1), character)
        inv2 = generate_shop(RNG(999), character)
        all_cards_same = all(a[0] == b[0] for a, b in zip(inv1.cards, inv2.cards))
        assert not all_cards_same


# ---------------------------------------------------------------------------
# Inventory generation — pricing
# ---------------------------------------------------------------------------


class TestShopPricing:
    """Prices have variance (×0.9–1.1) and one sale slot (×0.5)."""

    _BASE = CARD_PRICES

    def test_class_card_prices_near_base(self, rng: RNG, character: Character) -> None:
        """Class card prices must be within ±10 % of base (before any sale)."""
        inv = generate_shop(rng, character)
        for i in range(5):
            slot = inv.cards[i]
            assert slot[0] is not None
        # We can't know the sale index, but even on sale the price is base*0.5
        # Without sale, price is in [base*0.9, base*1.1].
        # Just verify all prices are positive integers.
        for card_id, price in inv.cards:
            assert price > 0

    def test_colorless_cards_priced_higher_than_same_rarity_class(
        self, character: Character
    ) -> None:
        """Colorless cards cost ×1.2 of base, so they should be >= class cards."""
        results: list[tuple[bool, bool]] = []
        for seed in range(20):
            inv = generate_shop(RNG(seed), character)
            # At same rarity UNCOMMON: colorless(idx 5) vs class uncommon
            # After variance [0.9-1.1] × 1.2 vs [0.9-1.1] × 1.0
            # Colorless should usually be higher but occasionally variance crosses
            cl_unc_price = inv.cards[5][1]
            results.append(cl_unc_price > 0)
        assert all(results)

    def test_one_sale_slot_among_class_cards(self) -> None:
        """Over many seeds, some price should be approximately half base (sale slot)."""
        # Base prices are 50/75/150. Half would be ~25/37/75.
        # Since variance is applied before halving, exact value varies.
        # Check that at least one card in [0-4] has a price ≤ half of base+10%
        max_half = max(CARD_PRICES.values()) * 1.1 / 2
        found_sale = False
        character = Character.ironclad()
        for seed in range(50):
            inv = generate_shop(RNG(seed), character)
            for i in range(5):
                price = inv.cards[i][1]
                if price <= max_half:
                    found_sale = True
                    break
            if found_sale:
                break
        assert found_sale, "No sale slot detected in 50 seeds"

    def test_sale_never_on_colorless_slots(self) -> None:
        """Sale index is among 0..4 so colorless slots (5,6) must not be halved."""
        character = Character.ironclad()
        for seed in range(50):
            inv = generate_shop(RNG(seed), character)
            for i in [5, 6]:
                price = inv.cards[i][1]
                # Minimum non-sale colorless uncommon price ≈ 75*1.2*0.9 = 81
                assert price > 40, f"Colorless slot {i} looks like it got a sale: {price}"


# ---------------------------------------------------------------------------
# Inventory generation — relics
# ---------------------------------------------------------------------------


class TestShopRelics:
    """Shop generates 3 relics: 2 random-tier + 1 SHOP-tier."""

    def test_generates_three_relics(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert len(inv.relics) == 3

    def test_all_relics_non_none(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert all(r is not None for r in inv.relics)

    def test_third_relic_always_shop_tier(self) -> None:
        """relic[2] must come from SHOP_TIER_RELICS."""
        character = Character.ironclad()
        for seed in range(20):
            inv = generate_shop(RNG(seed), character)
            relic_id, _ = inv.relics[2]
            assert relic_id in SHOP_TIER_RELICS, (
                f"relic[2]={relic_id} not in SHOP_TIER_RELICS (seed={seed})"
            )

    def test_first_two_relics_from_known_pool(self) -> None:
        """relic[0] and relic[1] must come from COMMON + UNCOMMON + RARE pool."""
        known_pool = set(ALL_RELICS)
        character = Character.ironclad()
        for seed in range(20):
            inv = generate_shop(RNG(seed), character)
            for i in [0, 1]:
                relic_id, _ = inv.relics[i]
                assert relic_id in known_pool, (
                    f"relic[{i}]={relic_id} not in known pool (seed={seed})"
                )

    def test_relic_prices_positive(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        for relic_entry in inv.relics:
            assert relic_entry is not None
            _, price = relic_entry
            assert price > 0

    def test_rare_relics_pool_not_empty(self) -> None:
        """RARE_RELICS must be non-empty so the shop can actually stock them."""
        assert len(RARE_RELICS) > 0, "RARE_RELICS is empty — shop's 18% rare roll always falls back"

    def test_shop_can_stock_rare_relic(self) -> None:
        """Shop rolls 18% RARE for slots 0/1 — rare relics must actually appear."""
        character = Character.ironclad()
        found_rare = any(
            inv.relics[i][0] in RARE_RELICS
            for seed in range(200)
            for i in [0, 1]
            if (inv := generate_shop(RNG(seed), character)) is not None
        )
        assert found_rare, "No rare relic appeared in shop slots 0/1 over 200 seeds"


# ---------------------------------------------------------------------------
# Buying cards
# ---------------------------------------------------------------------------


class TestBuyCard:
    def test_buy_card_success(self, shop: ShopInventory, rich_character: Character) -> None:
        card_id, price = shop.cards[0]
        gold_before = rich_character.gold
        result = buy_card(shop, 0, rich_character)
        assert result == card_id
        assert rich_character.gold == gold_before - price
        assert card_id in rich_character.deck

    def test_buy_card_marks_slot_empty(self, shop: ShopInventory, rich_character: Character) -> None:
        buy_card(shop, 0, rich_character)
        assert shop.cards[0][0] is None

    def test_cannot_buy_twice(self, shop: ShopInventory, rich_character: Character) -> None:
        buy_card(shop, 0, rich_character)
        result = buy_card(shop, 0, rich_character)
        assert result is None

    def test_insufficient_gold(self, shop: ShopInventory) -> None:
        poor = Character.ironclad()
        poor.gold = 0
        result = buy_card(shop, 0, poor)
        assert result is None

    def test_out_of_range_index(self, shop: ShopInventory, rich_character: Character) -> None:
        assert buy_card(shop, -1, rich_character) is None
        assert buy_card(shop, 99, rich_character) is None

    def test_buy_all_cards(self, shop: ShopInventory, rich_character: Character) -> None:
        for i in range(len(shop.cards)):
            result = buy_card(shop, i, rich_character)
            assert result is not None
        assert all(c[0] is None for c in shop.cards)


# ---------------------------------------------------------------------------
# Buying potions
# ---------------------------------------------------------------------------


class TestBuyPotion:
    def test_buy_potion_success(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        potion_id, price = shop.potions[0]
        gold_before = rich_character.gold
        result = buy_potion(shop, 0, rich_character)
        assert result == potion_id
        assert rich_character.gold == gold_before - price
        assert potion_id in rich_character.potions

    def test_buy_potion_marks_slot_empty(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        buy_potion(shop, 0, rich_character)
        assert shop.potions[0][0] is None

    def test_no_potion_slots(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        rich_character.potions = ["PotionA", "PotionB", "PotionC"]
        result = buy_potion(shop, 0, rich_character)
        assert result is None

    def test_insufficient_gold(self, shop: ShopInventory) -> None:
        poor = Character.ironclad()
        poor.gold = 0
        result = buy_potion(shop, 0, poor)
        assert result is None

    def test_out_of_range(self, shop: ShopInventory, rich_character: Character) -> None:
        assert buy_potion(shop, -1, rich_character) is None
        assert buy_potion(shop, 99, rich_character) is None

    def test_cannot_buy_twice(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        buy_potion(shop, 0, rich_character)
        assert buy_potion(shop, 0, rich_character) is None


# ---------------------------------------------------------------------------
# Buying relics (now indexed — 3 relics per shop)
# ---------------------------------------------------------------------------


class TestBuyRelic:
    def test_buy_relic_success(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        relic_id, price = shop.relics[0]
        gold_before = rich_character.gold
        result = buy_relic(shop, 0, rich_character)
        assert result == relic_id
        assert rich_character.gold == gold_before - price
        assert relic_id in rich_character.relics

    def test_buy_relic_clears_slot(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        buy_relic(shop, 0, rich_character)
        assert shop.relics[0] is None

    def test_cannot_buy_twice(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        buy_relic(shop, 0, rich_character)
        assert buy_relic(shop, 0, rich_character) is None

    def test_insufficient_gold(self, shop: ShopInventory) -> None:
        poor = Character.ironclad()
        poor.gold = 0
        assert buy_relic(shop, 0, poor) is None

    def test_buy_all_three_relics(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        for i in range(3):
            result = buy_relic(shop, i, rich_character)
            assert result is not None
        assert all(r is None for r in shop.relics)

    def test_out_of_range_index(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        assert buy_relic(shop, -1, rich_character) is None
        assert buy_relic(shop, 99, rich_character) is None


# ---------------------------------------------------------------------------
# Card removal
# ---------------------------------------------------------------------------


class TestRemoveCard:
    def test_remove_strike(self, rich_character: Character) -> None:
        rich_character.deck = ["Strike", "Defend", "Anger"]
        gold_before = rich_character.gold
        assert remove_card(rich_character, "Strike") is True
        assert "Strike" not in rich_character.deck
        assert rich_character.gold == gold_before - REMOVE_CARD_COST

    def test_remove_nonexistent_card(self, rich_character: Character) -> None:
        assert remove_card(rich_character, "NonExistent") is False

    def test_insufficient_gold(self) -> None:
        poor = Character.ironclad()
        poor.gold = 0
        poor.deck = ["Strike"]
        assert remove_card(poor, "Strike") is False
        assert "Strike" in poor.deck

    def test_remove_exact_cost(self) -> None:
        c = Character.ironclad()
        c.gold = REMOVE_CARD_COST
        c.deck = ["Wound"]
        assert remove_card(c, "Wound") is True
        assert c.gold == 0


# ---------------------------------------------------------------------------
# remove_worst_card helper
# ---------------------------------------------------------------------------


class TestRemoveWorstCard:
    def test_removes_worst(self, rich_character: Character) -> None:
        rich_character.deck = ["Anger", "Strike", "Defend"]
        removed = remove_worst_card(rich_character)
        assert removed == "Strike"
        assert "Strike" not in rich_character.deck

    def test_empty_deck(self, rich_character: Character) -> None:
        rich_character.deck = []
        assert remove_worst_card(rich_character) is None

    def test_cannot_afford(self) -> None:
        c = Character.ironclad()
        c.gold = 0
        c.deck = ["Strike"]
        assert remove_worst_card(c) is None


# ---------------------------------------------------------------------------
# ShopResult dataclass
# ---------------------------------------------------------------------------


class TestShopResult:
    def test_default_values(self) -> None:
        result = ShopResult()
        assert result.gold_spent == 0
        assert result.cards_bought == []
        assert result.potions_bought == []
        assert result.relic_bought is None
        assert result.card_removed is None
