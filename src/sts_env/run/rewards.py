"""Card and potion reward system for after winning combat.

After winning a combat encounter, the player receives:
  - 3 card choices drawn from the character's card pool (with rarity weighting).
  - An optional potion reward (40% chance).

Card rarity mechanics mirror C++ GameContext::createCardReward / rollCardRarity:
  - MONSTER: rare 3 %, uncommon 37 %, common 60 %  (roll = rng(0..99) + factor)
  - ELITE:   rare 10 %, uncommon 40 %, common 50 %
  - BOSS:    100 % rare
  - A persistent ``card_rarity_factor`` (pity counter) adjusts the roll:
      COMMON drawn → max(factor - 1, -40)
      RARE drawn   → factor reset to 5
      UNCOMMON     → no change
  - Within a single reward, re-roll until all card IDs are distinct.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from ..combat.card_pools import pool
from ..combat.cards import CardColor, Rarity
from .bus import RunEvent

if TYPE_CHECKING:
    from ..combat.rng import RNG
    from .bus import RunEventBus


# ---------------------------------------------------------------------------
# Room type enum (mirrors C++ Room, used for rarity roll thresholds)
# ---------------------------------------------------------------------------

class Room(Enum):
    MONSTER = auto()
    ELITE = auto()
    BOSS = auto()
    REST = auto()
    EVENT = auto()


# ---------------------------------------------------------------------------
# Rarity roll — matches C++ GameContext::rollCardRarity
# ---------------------------------------------------------------------------

# Thresholds: (rare_chance, uncommon_chance) per room type.
# roll = rng.randint(0, 99) + card_rarity_factor
# if roll < rare_chance          → RARE
# elif roll < rare + uncommon    → UNCOMMON
# else                           → COMMON
_RARE_CHANCE: dict[Room, int] = {
    Room.MONSTER: 3,
    Room.ELITE:   10,
    Room.BOSS:    100,  # always rare
    Room.REST:    3,
    Room.EVENT:   3,
}
_UNCOMMON_CHANCE: dict[Room, int] = {
    Room.MONSTER: 37,
    Room.ELITE:   40,
    Room.BOSS:    0,
    Room.REST:    37,
    Room.EVENT:   37,
}

_FACTOR_FLOOR = -40


def roll_card_rarity(rng: "RNG", room: Room, factor: int) -> tuple[Rarity, int]:
    """Roll one card rarity and return (rarity, updated_factor).

    Mirrors C++ GameContext::rollCardRarity + the inline factor update in
    createCardReward.
    """
    rare_chance = _RARE_CHANCE[room]
    uncommon_chance = _UNCOMMON_CHANCE[room]

    roll = rng.randint(0, 99) + factor

    if roll < rare_chance:
        rarity = Rarity.RARE
        new_factor = 5
    elif roll < rare_chance + uncommon_chance:
        rarity = Rarity.UNCOMMON
        new_factor = factor  # unchanged
    else:
        rarity = Rarity.COMMON
        new_factor = max(factor - 1, _FACTOR_FLOOR)

    return rarity, new_factor


# ---------------------------------------------------------------------------
# Card reward generation
# ---------------------------------------------------------------------------

def roll_card_rewards(
    rng: "RNG",
    color: CardColor = CardColor.RED,
    room: Room = Room.MONSTER,
    card_rarity_factor: int = 0,
    event_bus: "RunEventBus | None" = None,
) -> tuple[list[str], int]:
    """Return (card_ids, new_card_rarity_factor) for one reward screen.

    Mirrors C++ GameContext::createCardReward:
    - Per-slot rarity rolls using the pity counter.
    - Re-roll card ID (within the same rarity) until it does not duplicate an
      already-chosen card in this reward (C++ hasDuplicate loop).
    - BOSS room is always 100 % rare.

    The caller is responsible for persisting the returned factor on the run
    state (e.g. ``character.card_rarity_factor = new_factor``).
    """
    num_cards = 3
    if event_bus is not None:
        payload = event_bus.emit(RunEvent.CARD_REWARD_COUNT, count=num_cards)
        num_cards = payload["count"]

    rewards: list[str] = []
    factor = card_rarity_factor

    for _ in range(num_cards):
        rarity, factor = roll_card_rarity(rng, room, factor)
        card_pool = pool(color, rarity)
        if not card_pool:
            continue

        # Re-roll until unique within this reward (C++ hasDuplicate loop).
        # Safety guard: if pool is exhausted (tiny pool), accept duplicate.
        card = rng.choice(card_pool)
        attempts = 0
        while card in rewards and attempts < len(card_pool):
            card = rng.choice(card_pool)
            attempts += 1
        rewards.append(card)

    return rewards, factor


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
