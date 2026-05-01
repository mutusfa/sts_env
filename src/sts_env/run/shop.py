"""Act 1 shop system for Slay the Spire.

Generates shop inventory and handles purchase / card-removal transactions.
Mirrors C++ Shop::setup (Shop.cpp) for card layout, pricing, and relics.

Shop stock (7 cards):
  - cards[0], cards[1]: 2 class ATTACK (rarity rolled; 2nd != 1st)
  - cards[2], cards[3]: 2 class SKILL  (same)
  - cards[4]          : 1 class POWER  (COMMON rarity upgraded to UNCOMMON)
  - cards[5]          : 1 colorless UNCOMMON
  - cards[6]          : 1 colorless RARE

Pricing (C++ Shop::setupCards):
  - Per-slot: base * rng.uniform(0.9, 1.1), truncated to int
  - Colorless: ×1.2 applied after variance
  - One sale slot among indices 0–4: halved (merchantRng.random(4) → inclusive [0,4])
  - Global discounts: ascension ≥ 16 ×0.8, THE_COURIER ×0.8, MEMBERSHIP_CARD ×0.5

Relics (3 total, C++ Shop::setupRelics):
  - relics[0], relics[1]: tier rolled (48% COMMON, 34% UNCOMMON, 18% RARE)
  - relics[2]           : always SHOP-tier
  - Prices: base * rng.uniform(0.95, 1.05), rounded

NOTE: C++ uses separate cardRng / merchantRng / potionRng streams. Here a
single RNG is passed for all operations, so draw order diverges from the
reference (pricing rolls perturb subsequent card draws).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from ..combat.card_pools import colorless_pool, typed_pool
from ..combat.cards import CardColor, CardType, Rarity
from ..combat.rng import RNG
from .events import _pick_worst_card
from .rewards import (
    COMMON_POTIONS,
    COMMON_RELICS,
    UNCOMMON_POTIONS,
    UNCOMMON_RELICS,
    RARE_RELICS,
    RelicTier,
)

if TYPE_CHECKING:
    from .character import Character


# ---------------------------------------------------------------------------
# Shop pricing constants (C++ cardRarityPrices)
# ---------------------------------------------------------------------------

CARD_PRICES: dict[str, int] = {
    "common": 50,
    "uncommon": 75,
    "rare": 150,
}

COMMON_POTION_PRICE = 50
UNCOMMON_POTION_PRICE = 75

REMOVE_CARD_COST = 75  # flat base cost; increases with each removal in C++

_RARITY_TO_PRICE_KEY: dict[Rarity, str] = {
    Rarity.COMMON:   "common",
    Rarity.UNCOMMON: "uncommon",
    Rarity.RARE:     "rare",
}


# ---------------------------------------------------------------------------
# Relic pools
# ---------------------------------------------------------------------------

# Relics that are exclusively SHOP-tier in StS (C++ RelicTier::SHOP).
SHOP_TIER_RELICS: list[str] = [
    "SmilingMask",
    "RegalPillow",
    "ToyOrnithopter",
    "MealTicket",
    "MawBank",
    "Pantograph",
    "DreamCatcher",
    "FrozenEgg",
    "QuestionCard",
]

# Combined pool indexed by RelicTier (used in _roll_relic_tier).
_RELIC_POOL_BY_TIER: dict[RelicTier, list[str]] = {
    RelicTier.COMMON:   COMMON_RELICS,
    RelicTier.UNCOMMON: UNCOMMON_RELICS,
    RelicTier.RARE:     RARE_RELICS,
}

# Legacy name kept for any external code still referencing it.
SHOP_RELIC_POOL: list[str] = list({
    *COMMON_RELICS, *UNCOMMON_RELICS, *SHOP_TIER_RELICS
})


# ---------------------------------------------------------------------------
# Rarity roll for shop cards (C++ Shop::rollCardRarityShop)
# ---------------------------------------------------------------------------

_SHOP_BASE_RARE_CHANCE = 9
_SHOP_BASE_UNCOMMON_CHANCE = 37


def _roll_rarity_shop(rng: RNG, card_rarity_factor: int) -> Rarity:
    """Roll card rarity for a shop slot.

    C++ Shop::rollCardRarityShop: rare 9 / uncommon 37 / common 54.
    Factor is read-only here — shop does NOT update cardRarityFactor.
    """
    roll = rng.randint(0, 99) + card_rarity_factor
    if roll < _SHOP_BASE_RARE_CHANCE:
        return Rarity.RARE
    elif roll < _SHOP_BASE_RARE_CHANCE + _SHOP_BASE_UNCOMMON_CHANCE:
        return Rarity.UNCOMMON
    else:
        return Rarity.COMMON


# ---------------------------------------------------------------------------
# Relic tier roll (C++ Shop::rollRelicTier)
# ---------------------------------------------------------------------------

def _roll_relic_tier(rng: RNG) -> RelicTier:
    """Roll a relic tier: 48% COMMON, 34% UNCOMMON, 18% RARE.

    Mirrors C++ Shop::rollRelicTier.
    """
    roll = rng.randint(0, 99)
    if roll < 48:
        return RelicTier.COMMON
    elif roll < 82:
        return RelicTier.UNCOMMON
    else:
        return RelicTier.RARE


def _pick_relic(rng: RNG, pool: list[str], owned: set[str]) -> str | None:
    """Pick a random relic from *pool* not in *owned*. Returns None if pool exhausted."""
    available = [r for r in pool if r not in owned]
    if not available:
        return None
    return rng.choice(available)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ShopInventory:
    """Generated shop inventory.

    cards[0-1]=ATTACK, [2-3]=SKILL, [4]=POWER, [5]=colorless UNCOMMON,
    [6]=colorless RARE.  Slot value is None after purchase.
    """

    cards: list[tuple[str | None, int]]        # (card_id, price) × 7; None when bought
    potions: list[tuple[str | None, int]]       # (potion_id, price) × 3; None when bought
    relics: list[tuple[str, int] | None]        # [(relic_id, price) or None when bought] × 3
    remove_cost: int


@dataclass
class ShopResult:
    """Result of visiting a shop."""

    gold_spent: int = 0
    cards_bought: list[str] = field(default_factory=list)
    potions_bought: list[str] = field(default_factory=list)
    relic_bought: str | None = None
    card_removed: str | None = None


# ---------------------------------------------------------------------------
# Inventory generation
# ---------------------------------------------------------------------------


def generate_shop(
    rng: RNG,
    character: "Character",
    card_rarity_factor: int = 0,
) -> ShopInventory:
    """Generate a random shop inventory following C++ Shop::setup.

    ``card_rarity_factor`` mirrors C++ gc.cardRarityFactor — it adjusts rarity
    rolls but is NOT mutated (shop doesn't update the factor).
    """
    color = character.character_class
    owned_relics = set(character.relics)

    # -----------------------------------------------------------------------
    # Cards
    # -----------------------------------------------------------------------
    cards: list[tuple[str | None, int]] = []

    def _pick_class_card(card_type: CardType, exclude: str | None = None) -> tuple[str, Rarity]:
        """Pick a class card of given type; re-roll (rarity + id) if matches *exclude*."""
        rarity = _roll_rarity_shop(rng, card_rarity_factor)
        card_pool = typed_pool(color, card_type, rarity)
        if not card_pool:
            # Fallback: try UNCOMMON
            rarity = Rarity.UNCOMMON
            card_pool = typed_pool(color, card_type, rarity)
        card_id = rng.choice(card_pool) if card_pool else ""
        if exclude is not None:
            # C++ assignRandomCardExcluding: re-roll both rarity and id until != exclude
            attempts = 0
            max_attempts = 20
            while card_id == exclude and attempts < max_attempts:
                rarity = _roll_rarity_shop(rng, card_rarity_factor)
                card_pool = typed_pool(color, card_type, rarity)
                if not card_pool:
                    rarity = Rarity.UNCOMMON
                    card_pool = typed_pool(color, card_type, rarity)
                card_id = rng.choice(card_pool) if card_pool else ""
                attempts += 1
        return card_id, rarity

    # 2 ATTACK
    atk0, r_atk0 = _pick_class_card(CardType.ATTACK)
    atk1, r_atk1 = _pick_class_card(CardType.ATTACK, exclude=atk0)

    # 2 SKILL
    skl0, r_skl0 = _pick_class_card(CardType.SKILL)
    skl1, r_skl1 = _pick_class_card(CardType.SKILL, exclude=skl0)

    # 1 POWER: COMMON → upgraded to UNCOMMON (C++ rarities[4] = ... == COMMON ? UNCOMMON : rarities[4])
    pwr_id, r_pwr = _pick_class_card(CardType.POWER)
    if r_pwr == Rarity.COMMON:
        r_pwr = Rarity.UNCOMMON
        pwr_pool = typed_pool(color, CardType.POWER, Rarity.UNCOMMON)
        if pwr_pool:
            pwr_id = rng.choice(pwr_pool)

    # 2 colorless
    cl_uncommons = colorless_pool(Rarity.UNCOMMON)
    cl_rares = colorless_pool(Rarity.RARE)
    cl_unc_id = rng.choice(cl_uncommons) if cl_uncommons else ""
    cl_rare_id = rng.choice(cl_rares) if cl_rares else ""

    # -----------------------------------------------------------------------
    # Pricing (C++ merchantRng.random(0.9f, 1.1f) variance)
    # -----------------------------------------------------------------------
    def _card_price(rarity: Rarity, colorless: bool = False) -> int:
        base = CARD_PRICES[_RARITY_TO_PRICE_KEY[rarity]]
        price = int(base * (0.9 + rng.random() * 0.2))
        if colorless:
            price = int(price * 1.2)
        return price

    raw_prices: list[int] = [
        _card_price(r_atk0),
        _card_price(r_atk1),
        _card_price(r_skl0),
        _card_price(r_skl1),
        _card_price(r_pwr),
        _card_price(Rarity.UNCOMMON, colorless=True),
        _card_price(Rarity.RARE, colorless=True),
    ]

    # One sale among class cards (indices 0–4 inclusive): C++ saleIdx = merchantRng.random(4)
    sale_idx = rng.randint(0, 4)
    raw_prices[sale_idx] = raw_prices[sale_idx] // 2

    # Global discounts
    has_courier = character.has_relic("THE_COURIER")
    has_membership = character.has_relic("MEMBERSHIP_CARD")
    ascension = getattr(character, "ascension", 0)

    def _apply_discounts(price: int) -> int:
        if ascension >= 16:
            price = int(round(price * 0.8))
        if has_courier:
            price = int(round(price * 0.8))
        if has_membership:
            price = int(round(price * 0.5))
        return max(1, price)

    final_prices = [_apply_discounts(p) for p in raw_prices]

    card_entries: list[str] = [atk0, atk1, skl0, skl1, pwr_id, cl_unc_id, cl_rare_id]
    cards = [(cid or None, fp) for cid, fp in zip(card_entries, final_prices)]

    # -----------------------------------------------------------------------
    # Potions — 3 random, no dedup (matches C++)
    # -----------------------------------------------------------------------
    all_potion_pools: list[tuple[list[str], int]] = [
        (COMMON_POTIONS, COMMON_POTION_PRICE),
        (UNCOMMON_POTIONS, UNCOMMON_POTION_PRICE),
    ]
    potions: list[tuple[str | None, int]] = []
    for _ in range(3):
        potion_pool, base_price = rng.choice(all_potion_pools)
        potion_id = rng.choice(potion_pool)
        price = int(round(base_price * (0.95 + rng.random() * 0.10)))
        potions.append((potion_id, price))

    # -----------------------------------------------------------------------
    # Relics — 2 random-tier + 1 SHOP-tier (C++ Shop::setupRelics)
    # -----------------------------------------------------------------------
    relics: list[tuple[str, int] | None] = []

    def _relic_base_price(relic_id: str) -> int:
        """Simplified base price per C++ getRelicBasePrice."""
        if relic_id in RARE_RELICS:
            return 300
        if relic_id in UNCOMMON_RELICS:
            return 250
        if relic_id in SHOP_TIER_RELICS:
            return 143
        return 150  # COMMON

    for _ in range(2):
        tier = _roll_relic_tier(rng)
        rpool = _RELIC_POOL_BY_TIER.get(tier, [])
        relic_id = _pick_relic(rng, rpool, owned_relics)
        if relic_id is None:
            # Fallback: try UNCOMMON then COMMON
            for fallback_tier in (RelicTier.UNCOMMON, RelicTier.COMMON):
                relic_id = _pick_relic(rng, _RELIC_POOL_BY_TIER[fallback_tier], owned_relics)
                if relic_id is not None:
                    break
        if relic_id is None:
            relic_id = rng.choice(COMMON_RELICS)
        base = _relic_base_price(relic_id)
        price = int(round(base * (0.95 + rng.random() * 0.10)))
        price = _apply_discounts(price)
        relics.append((relic_id, price))

    # relic[2]: always SHOP-tier
    shop_id = _pick_relic(rng, SHOP_TIER_RELICS, owned_relics)
    if shop_id is None:
        shop_id = rng.choice(SHOP_TIER_RELICS)
    shop_base = _relic_base_price(shop_id)
    shop_price = int(round(shop_base * (0.95 + rng.random() * 0.10)))
    shop_price = _apply_discounts(shop_price)
    relics.append((shop_id, shop_price))

    return ShopInventory(
        cards=cards,
        potions=potions,
        relics=relics,
        remove_cost=REMOVE_CARD_COST,
    )


# ---------------------------------------------------------------------------
# Purchase helpers
# ---------------------------------------------------------------------------


def buy_card(inventory: ShopInventory, index: int, character: "Character") -> str | None:
    """Buy a card from the shop.

    Returns the card_id on success, or None if the slot is empty / already
    bought, index is out of range, or the character cannot afford it.
    """
    if index < 0 or index >= len(inventory.cards):
        return None

    entry = inventory.cards[index]
    if entry[0] is None:
        return None

    card_id, price = entry
    if character.gold < price:
        return None

    character.gold -= price
    character.add_card(card_id)
    inventory.cards[index] = (None, price)
    return card_id


def buy_potion(inventory: ShopInventory, index: int, character: "Character") -> str | None:
    """Buy a potion from the shop.

    Returns the potion_id on success, or None if the slot is empty / already
    bought, index is out of range, the character cannot afford it, or there
    are no empty potion slots.
    """
    if index < 0 or index >= len(inventory.potions):
        return None

    entry = inventory.potions[index]
    if entry[0] is None:
        return None

    potion_id, price = entry
    if character.gold < price:
        return None

    if len(character.potions) >= character.max_potion_slots:
        return None

    character.gold -= price
    character.add_potion(potion_id)
    inventory.potions[index] = (None, price)
    return potion_id


def buy_relic(inventory: ShopInventory, index: int, character: "Character") -> str | None:
    """Buy a relic from the shop by slot index (0–2).

    Returns the relic_id on success, or None if the slot is empty / already
    bought, index is out of range, or the character cannot afford it.
    """
    if index < 0 or index >= len(inventory.relics):
        return None

    entry = inventory.relics[index]
    if entry is None:
        return None

    relic_id, price = entry
    if character.gold < price:
        return None

    character.gold -= price
    character.add_relic(relic_id)
    inventory.relics[index] = None
    return relic_id


def remove_card(character: "Character", card_id: str) -> bool:
    """Remove a specific card from the character's deck.

    Deducts :data:`REMOVE_CARD_COST` gold.  Returns True on success,
    False if the card is not in the deck or the character cannot afford it.
    """
    if card_id not in character.deck:
        return False

    if character.gold < REMOVE_CARD_COST:
        return False

    character.gold -= REMOVE_CARD_COST
    character.deck.remove(card_id)
    return True


def remove_worst_card(character: "Character") -> str | None:
    """Remove the worst card from the deck automatically.

    Uses the priority table from :mod:`events`.  Returns the removed
    card_id on success, or None if the deck is empty / cannot afford.
    """
    worst = _pick_worst_card(character.deck)
    if worst is None:
        return None

    if not remove_card(character, worst):
        return None

    return worst
