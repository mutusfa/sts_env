"""Act 1 shop system for Slay the Spire.

Generates shop inventory (cards, potions, relic) and handles purchase
and card-removal transactions.  Pricing mirrors StS Act 1 values.

Shop stock mirrors StS:
  - 5 cards: 3 character-color (1 common + 1 uncommon + 1 rare)
              + 2 colorless (1 uncommon + 1 rare)
  - 3 potions drawn from common/uncommon pools
  - 1 relic from the shop relic pool
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..combat.card_pools import colorless_pool, pool
from ..combat.cards import CardColor, Rarity
from ..combat.rng import RNG
from .events import _pick_worst_card
from .rewards import COMMON_POTIONS, UNCOMMON_POTIONS

if TYPE_CHECKING:
    from .character import Character

# ---------------------------------------------------------------------------
# Shop pricing (matches StS Act 1)
# ---------------------------------------------------------------------------

CARD_PRICES: dict[str, int] = {
    "common": 50,
    "uncommon": 75,
    "rare": 150,
}

COMMON_POTION_PRICE = 50
UNCOMMON_POTION_PRICE = 75

RELIC_PRICE = 150

REMOVE_CARD_COST = 75  # flat cost per removal (simplified)

# ---------------------------------------------------------------------------
# Shop relic pool (Act 1 shop exclusives)
# ---------------------------------------------------------------------------

SHOP_RELIC_POOL: list[str] = [
    "BagOfPreparation",
    "BlueCandle",
    "BronzeBlade",
    "CeramicFish",
    "DreamCatcher",
    "FrozenEgg",
    "HappyFlower",
    "InkBottle",
    "Lantern",
    "MawBank",
    "MealTicket",
    "Nunchaku",
    "OrnamentalFan",
    "PenNib",
    "PreservedInsect",
    "Shuriken",
    "Sundial",
    "TheBoot",
    "TinyChest",
    "WarPaint",
    "Whetstone",
]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ShopInventory:
    """Generated shop inventory."""

    cards: list[tuple[str | None, int]]  # (card_id, price) — 5 cards; None when bought
    potions: list[tuple[str | None, int]]  # (potion_id, price) — 3 potions; None when bought
    relic: tuple[str, int] | None  # (relic_id, price) or None when bought
    remove_cost: int  # Cost to remove a card


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


def generate_shop(rng: RNG, character: Character) -> ShopInventory:
    """Generate a random shop inventory.

    Stock:
      - 5 cards: 3 character-color (1C/1U/1R) + 2 colorless (1U/1R)
      - 3 potions drawn from common/uncommon pools
      - 1 relic from the shop relic pool
    """
    color = character.character_class

    # --- Cards ---------------------------------------------------------------
    cards: list[tuple[str | None, int]] = []

    # 1 character common card
    char_commons = pool(color, Rarity.COMMON)
    if char_commons:
        cards.append((rng.choice(char_commons), CARD_PRICES["common"]))

    # 1 character uncommon card
    char_uncommons = pool(color, Rarity.UNCOMMON)
    if char_uncommons:
        cards.append((rng.choice(char_uncommons), CARD_PRICES["uncommon"]))

    # 1 character rare card
    char_rares = pool(color, Rarity.RARE)
    if char_rares:
        cards.append((rng.choice(char_rares), CARD_PRICES["rare"]))

    # 1 colorless uncommon card
    cl_uncommons = colorless_pool(Rarity.UNCOMMON)
    if cl_uncommons:
        cards.append((rng.choice(cl_uncommons), CARD_PRICES["uncommon"]))

    # 1 colorless rare card
    cl_rares = colorless_pool(Rarity.RARE)
    if cl_rares:
        cards.append((rng.choice(cl_rares), CARD_PRICES["rare"]))

    # --- Potions -------------------------------------------------------------
    potions: list[tuple[str | None, int]] = []
    all_potion_pools: list[tuple[list[str], int]] = [
        (COMMON_POTIONS, COMMON_POTION_PRICE),
        (UNCOMMON_POTIONS, UNCOMMON_POTION_PRICE),
    ]
    for _ in range(3):
        potion_pool, price = rng.choice(all_potion_pools)
        potion_id = rng.choice(potion_pool)
        potions.append((potion_id, price))

    # --- Relic ---------------------------------------------------------------
    relic_id = rng.choice(SHOP_RELIC_POOL)
    relic: tuple[str, int] | None = (relic_id, RELIC_PRICE)

    return ShopInventory(
        cards=cards,
        potions=potions,
        relic=relic,
        remove_cost=REMOVE_CARD_COST,
    )


# ---------------------------------------------------------------------------
# Purchase helpers
# ---------------------------------------------------------------------------


def buy_card(inventory: ShopInventory, index: int, character: Character) -> str | None:
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


def buy_potion(inventory: ShopInventory, index: int, character: Character) -> str | None:
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


def buy_relic(inventory: ShopInventory, character: Character) -> str | None:
    """Buy the relic from the shop.

    Returns the relic_id on success, or None if already bought or the
    character cannot afford it.
    """
    if inventory.relic is None:
        return None

    relic_id, price = inventory.relic
    if character.gold < price:
        return None

    character.gold -= price
    character.relics.append(relic_id)
    inventory.relic = None
    return relic_id


def remove_card(character: Character, card_id: str) -> bool:
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


def remove_worst_card(character: Character) -> str | None:
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
