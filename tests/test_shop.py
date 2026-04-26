"""Tests for the Act 1 shop system."""

from __future__ import annotations

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.character import Character
from sts_env.run.shop import (
    CARD_PRICES,
    COMMON_POTION_PRICE,
    RELIC_PRICE,
    REMOVE_CARD_COST,
    SHOP_RELIC_POOL,
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
# Inventory generation tests
# ---------------------------------------------------------------------------


class TestGenerateShop:
    """Tests for generate_shop."""

    def test_generates_five_cards(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert len(inv.cards) == 5

    def test_generates_three_potions(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert len(inv.potions) == 3

    def test_generates_one_relic(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert inv.relic is not None
        relic_id, price = inv.relic
        assert relic_id in SHOP_RELIC_POOL
        assert price == RELIC_PRICE

    def test_card_pricing(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        # First 3 common, then 1 uncommon, then 1 rare
        assert inv.cards[0][1] == CARD_PRICES["common"]
        assert inv.cards[1][1] == CARD_PRICES["common"]
        assert inv.cards[2][1] == CARD_PRICES["common"]
        assert inv.cards[3][1] == CARD_PRICES["uncommon"]
        assert inv.cards[4][1] == CARD_PRICES["rare"]

    def test_remove_cost_is_set(self, rng: RNG, character: Character) -> None:
        inv = generate_shop(rng, character)
        assert inv.remove_cost == REMOVE_CARD_COST

    def test_seeded_shops_are_deterministic(
        self, rng: RNG, character: Character
    ) -> None:
        inv1 = generate_shop(RNG(42), character)
        inv2 = generate_shop(RNG(42), character)
        assert inv1.cards == inv2.cards
        assert inv1.potions == inv2.potions
        assert inv1.relic == inv2.relic

    def test_different_seeds_produce_different_shops(
        self, character: Character
    ) -> None:
        inv1 = generate_shop(RNG(1), character)
        inv2 = generate_shop(RNG(999), character)
        # Extremely unlikely all items match
        all_cards_same = all(a[0] == b[0] for a, b in zip(inv1.cards, inv2.cards))
        assert not all_cards_same


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

    def test_buy_all_five_cards(self, shop: ShopInventory, rich_character: Character) -> None:
        for i in range(5):
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
        # Fill all potion slots
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
# Buying relics
# ---------------------------------------------------------------------------


class TestBuyRelic:
    def test_buy_relic_success(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        relic_id, price = shop.relic
        gold_before = rich_character.gold
        result = buy_relic(shop, rich_character)
        assert result == relic_id
        assert rich_character.gold == gold_before - price
        assert relic_id in rich_character.relics

    def test_buy_relic_clears_slot(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        buy_relic(shop, rich_character)
        assert shop.relic is None

    def test_cannot_buy_twice(
        self, shop: ShopInventory, rich_character: Character
    ) -> None:
        buy_relic(shop, rich_character)
        assert buy_relic(shop, rich_character) is None

    def test_insufficient_gold(self, shop: ShopInventory) -> None:
        poor = Character.ironclad()
        poor.gold = 0
        assert buy_relic(shop, poor) is None


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
        assert "Strike" in poor.deck  # card not removed

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
