"""Card and potion reward system for after winning combat.

After winning a combat encounter, the player receives:
  - 3 card choices drawn from the character's card pool (with rarity weighting).
  - An optional potion reward (40% chance).

Card rarity and pool composition mirrors StS Act 1:
  - Common: 60% weight
  - Uncommon: 37% weight
  - Rare: 3% weight (guaranteed 1 in 3 for elite fights)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..combat.card_pools import pool
from ..combat.cards import CardColor, Rarity
from .bus import RunEvent

if TYPE_CHECKING:
    from ..combat.rng import RNG
    from .bus import RunEventBus


# ---------------------------------------------------------------------------
# Rarity weights for normal combats (Common 60%, Uncommon 37%, Rare 3%)
# ---------------------------------------------------------------------------

_RARITY_ROLLS: list[tuple[float, Rarity]] = [
    (0.60, Rarity.COMMON),
    (0.97, Rarity.UNCOMMON),
    (1.00, Rarity.RARE),
]


def _roll_rarity(
    rng: "RNG",
    color: CardColor,
    guaranteed_rare: bool = False,
) -> list[str]:
    """Roll which rarity pool to draw from.

    If guaranteed_rare is True, always returns the rare pool.
    """
    if guaranteed_rare:
        return pool(color, Rarity.RARE)
    roll = rng.random()
    for threshold, rarity in _RARITY_ROLLS:
        if roll < threshold:
            return pool(color, rarity)
    return pool(color, Rarity.RARE)


def roll_card_rewards(
    rng: "RNG",
    color: CardColor = CardColor.RED,
    is_elite: bool = False,
    event_bus: "RunEventBus | None" = None,
    # ``relics`` kept temporarily for backward compat — prefer ``event_bus``
    relics: list[str] | None = None,
) -> list[str]:
    """Return card IDs to choose from as a card reward.

    Cards are drawn from the given character color's card pool with rarity
    weighting.  For elite fights, 1 of the 3 cards is guaranteed to be rare.
    Relics that modify card reward count (e.g. BustedCrown) are handled
    through the run-layer event bus.
    """
    num_cards = 3
    if event_bus is not None:
        payload = event_bus.emit(RunEvent.CARD_REWARD_COUNT, count=num_cards)
        num_cards = payload["count"]

    rewards: list[str] = []

    for i in range(num_cards):
        guaranteed_rare = is_elite and i == 0
        card_pool = _roll_rarity(rng, color, guaranteed_rare=guaranteed_rare)
        if not card_pool:
            continue
        card = rng.choice(card_pool)
        rewards.append(card)

    return rewards


# ---------------------------------------------------------------------------
# Potion rewards
# ---------------------------------------------------------------------------

COMMON_POTIONS: list[str] = [
    "BlockPotion",
    "EnergyPotion",
    "FirePotion",
    "ExplosivePotion",
    "StrengthPotion",
    "SwiftPotion",
    "DexterityPotion",
    "SpeedPotion",
    "SteroidPotion",
    "FlexPotion",
    "FearPotion",
    "AttackPotion",
    "SkillPotion",
]

UNCOMMON_POTIONS: list[str] = [
    "BloodPotion",
    "HeartOfIron",
    "PowerPotion",
]

_ALL_POTIONS = COMMON_POTIONS + UNCOMMON_POTIONS

# 40% chance to receive a potion after combat
_POTION_DROP_RATE = 0.40


def roll_potion_reward(rng: "RNG") -> str | None:
    """Return a potion ID if one drops, or None.

    40% chance to drop a random potion from the common/uncommon pool.
    """
    if rng.random() < _POTION_DROP_RATE:
        return rng.choice(_ALL_POTIONS)
    return None


# ---------------------------------------------------------------------------
# Relic rewards (elite drops)
# ---------------------------------------------------------------------------

COMMON_RELICS: list[str] = [
    "RedSkull",
    "CentennialPuzzle",
    "JuzuBracelet",
    "Orichalcum",
    "CeramicFish",
    "Anchor",
    "BagOfMarbles",
    "BloodVial",
    "BronzeScales",
    "HappyFlower",
    "Lantern",
    "Nunchaku",
    "OrnamentalFan",
    "PreservedInsect",
    "Shuriken",
    "Sundial",
    "Vajra",
    "WarPaint",
    "Whetstone",
    "TheBoot",
    "Strawberry",
    "RegalPillow",
]

UNCOMMON_RELICS: list[str] = [
    "DreamCatcher",
    "MealTicket",
    "MawBank",
    "ToyOrnithopter",
    "Pantograph",
    "FrozenEgg",
    "InkBottle",
    "PenNib",
    "QuestionCard",
    "SmilingMask",
    "TinyChest",
    "BagOfPreparation",
    "BlueCandle",
]

ALL_RELICS = COMMON_RELICS + UNCOMMON_RELICS


def roll_elite_relic(rng: "RNG", owned: list[str] | None = None) -> str | None:
    """Return a relic ID from the common/uncommon pool, avoiding duplicates.

    Returns None if all relics are already owned.
    """
    owned_set = set(owned) if owned else set()
    available = [r for r in ALL_RELICS if r not in owned_set]
    if not available:
        return None
    return rng.choice(available)
