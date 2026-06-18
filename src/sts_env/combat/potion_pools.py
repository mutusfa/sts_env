"""Potion pools and RNG — faithful to sts_lightspeed Potions.h / Game.cpp.

Single source of truth for Ironclad potion IDs, rarities, shop prices, and
``returnRandomPotion`` semantics.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from ..helpers import below_d100, roll_d100

if TYPE_CHECKING:
    from .rng import RNG


class PotionRarity(Enum):
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()


# Internal compact IDs (existing sts_env convention).
_POTION_BY_ENUM_INDEX: dict[int, str] = {
    2: "Ambrosia",
    3: "AncientPotion",
    4: "AttackPotion",
    5: "BlessingOfTheForge",
    6: "BlockPotion",
    7: "BloodPotion",
    8: "BottledMiracle",
    9: "ColorlessPotion",
    10: "CultistPotion",
    11: "CunningPotion",
    12: "DexterityPotion",
    13: "DistilledChaos",
    14: "DuplicationPotion",
    15: "ElixirPotion",
    16: "EnergyPotion",
    17: "EntropicBrew",
    18: "EssenceOfDarkness",
    19: "EssenceOfSteel",
    20: "ExplosivePotion",
    21: "FairyPotion",
    22: "FearPotion",
    23: "FirePotion",
    24: "SteroidPotion",  # FLEX_POTION in C++
    25: "FocusPotion",
    26: "FruitJuice",
    27: "GamblersBrew",
    28: "GhostInAJar",
    29: "HeartOfIron",
    30: "LiquidBronze",
    31: "LiquidMemories",
    32: "PoisonPotion",
    33: "PotionOfCapacity",
    34: "PowerPotion",
    35: "RegenPotion",
    36: "SkillPotion",
    37: "SmokeBomb",
    38: "SneckoOil",
    39: "SpeedPotion",
    40: "StancePotion",
    41: "StrengthPotion",
    42: "SwiftPotion",
    43: "WeakPotion",
}

# Ironclad pool — PotionPool::potionPool[IRONCLAD] enum indices.
_IRONCLAD_POOL_INDICES = (
    7, 15, 29, 6, 12, 16, 20, 23, 41, 42, 43, 22, 4, 36, 34, 9, 24, 39,
    5, 35, 3, 30, 27, 19, 14, 13, 31, 10, 26, 38, 21, 37, 17,
)

IRONCLAD_POTION_POOL: tuple[str, ...] = tuple(
    _POTION_BY_ENUM_INDEX[i] for i in _IRONCLAD_POOL_INDICES
)

POTION_RARITY: dict[str, PotionRarity] = {
    _POTION_BY_ENUM_INDEX[i]: r
    for i, r in {
        2: PotionRarity.RARE,
        3: PotionRarity.UNCOMMON,
        4: PotionRarity.COMMON,
        5: PotionRarity.COMMON,
        6: PotionRarity.COMMON,
        7: PotionRarity.COMMON,
        8: PotionRarity.COMMON,
        9: PotionRarity.COMMON,
        10: PotionRarity.RARE,
        11: PotionRarity.UNCOMMON,
        12: PotionRarity.COMMON,
        13: PotionRarity.UNCOMMON,
        14: PotionRarity.UNCOMMON,
        15: PotionRarity.UNCOMMON,
        16: PotionRarity.COMMON,
        17: PotionRarity.RARE,
        18: PotionRarity.RARE,
        19: PotionRarity.UNCOMMON,
        20: PotionRarity.COMMON,
        21: PotionRarity.RARE,
        22: PotionRarity.COMMON,
        23: PotionRarity.COMMON,
        24: PotionRarity.COMMON,
        25: PotionRarity.COMMON,
        26: PotionRarity.RARE,
        27: PotionRarity.UNCOMMON,
        28: PotionRarity.RARE,
        29: PotionRarity.RARE,
        30: PotionRarity.UNCOMMON,
        31: PotionRarity.UNCOMMON,
        32: PotionRarity.COMMON,
        33: PotionRarity.UNCOMMON,
        34: PotionRarity.COMMON,
        35: PotionRarity.UNCOMMON,
        36: PotionRarity.COMMON,
        37: PotionRarity.RARE,
        38: PotionRarity.RARE,
        39: PotionRarity.COMMON,
        40: PotionRarity.UNCOMMON,
        41: PotionRarity.COMMON,
        42: PotionRarity.COMMON,
        43: PotionRarity.COMMON,
    }.items()
}

POTION_BASE_PRICE: dict[PotionRarity, int] = {
    PotionRarity.COMMON: 50,
    PotionRarity.UNCOMMON: 75,
    PotionRarity.RARE: 100,
}

_POOL_SIZE = 33


def potion_requires_target(potion_id: str) -> bool:
    """Mirrors potionRequiresTarget() in Potions.h."""
    return potion_id in ("FearPotion", "FirePotion", "PoisonPotion", "WeakPotion")


def get_potion_base_price(potion_id: str) -> int:
    return POTION_BASE_PRICE[POTION_RARITY[potion_id]]


def get_random_potion_from_pool(rng: RNG, *, index: int | None = None) -> str:
    """Pick a potion from the Ironclad pool by random index (getRandomPotion)."""
    idx = index if index is not None else rng.randint(0, _POOL_SIZE - 1)
    return IRONCLAD_POTION_POOL[idx]


_POTION_RARITY_COMMON = 0.65
_POTION_RARITY_UNCOMMON_CUMULATIVE = 0.90


def _roll_potion_rarity(rng: RNG) -> PotionRarity:
    """Mirrors returnRandomPotion rarity roll: 65% common, 25% uncommon, 10% rare."""
    roll = roll_d100(rng)
    if below_d100(roll, _POTION_RARITY_COMMON):
        return PotionRarity.COMMON
    if below_d100(roll, _POTION_RARITY_UNCOMMON_CUMULATIVE):
        return PotionRarity.UNCOMMON
    return PotionRarity.RARE


def roll_random_potion(rng: RNG, *, limited: bool = False) -> str:
    """Mirrors returnRandomPotion + returnRandomPotionOfRarity for Ironclad."""
    target_rarity = _roll_potion_rarity(rng)
    temp = get_random_potion_from_pool(rng)
    spam_check = limited
    while POTION_RARITY[temp] != target_rarity or spam_check:
        spam_check = limited
        temp = get_random_potion_from_pool(rng)
        if temp != "FruitJuice":
            spam_check = False
    return temp
