"""Card and potion reward system for after winning combat.

After winning a combat encounter, the player receives:
  - 3 card choices drawn from the Ironclad card pool (with rarity weighting).
  - An optional potion reward (40% chance).

Card rarity and pool composition mirrors StS Act 1:
  - Common: 60% weight
  - Uncommon: 37% weight
  - Rare: 3% weight (guaranteed 1 in 3 for elite fights)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..combat.rng import RNG


# ---------------------------------------------------------------------------
# Ironclad card pool — only cards with registered handlers in cards.py
# ---------------------------------------------------------------------------

IRONCLAD_COMMON_CARDS: list[str] = [
    "Anger",
    "Armaments",
    "Cleave",
    "Clothesline",
    "Flex",
    "Havoc",
    "Headbutt",
    "IronWave",
    "PommelStrike",
    "ShrugItOff",
    "SwordBoomerang",
    "ThunderClap",
    "TrueStrike",
    "TwinStrike",
    "WarCry",
    "WildStrike",
]

IRONCLAD_UNCOMMON_CARDS: list[str] = [
    "BattleTrance",
    "Bloodletting",
    "BurningPact",
    "Carnage",
    "Disarm",
    "Dropkick",
    "DualWield",
    "Entrench",
    "FeelNoPain",
    "FlameBarrier",
    "GhostArmor",
    "Inflame",
    "Metallicize",
    "PowerThrough",
    "Pummel",
    "Rage",
    "Rampage",
    "RecklessCharge",
    "SecondWind",
    "SeeingRed",
    "SearingBlow",
    "Sentinel",
    "SeverSoul",
    "ShockWave",
    "SpotWeakness",
    "Uppercut",
    "Whirlwind",
]

IRONCLAD_RARE_CARDS: list[str] = [
    "Berserk",
    "Bludgeon",
    "Brutality",
    "Corruption",
    "DarkEmbrace",
    "DemonForm",
    "DoubleTap",
    "Feed",
    "Impervious",
    "Juggernaut",
    "LimitBreak",
    "Offering",
]

# Combined pool for random selection (weighted)
_ALL_REWARD_CARDS = IRONCLAD_COMMON_CARDS + IRONCLAD_UNCOMMON_CARDS + IRONCLAD_RARE_CARDS

# Rarity weights for normal combats (Common 60%, Uncommon 37%, Rare 3%)
_RARITY_ROLLS = [
    (0.60, IRONCLAD_COMMON_CARDS),
    (0.97, IRONCLAD_UNCOMMON_CARDS),
    (1.00, IRONCLAD_RARE_CARDS),
]


def _roll_rarity(rng: "RNG", guaranteed_rare: bool = False) -> list[str]:
    """Roll which rarity pool to draw from.

    If guaranteed_rare is True, always returns the rare pool.
    """
    if guaranteed_rare:
        return IRONCLAD_RARE_CARDS
    roll = rng.random()
    for threshold, pool in _RARITY_ROLLS:
        if roll < threshold:
            return pool
    return IRONCLAD_RARE_CARDS


def roll_card_rewards(rng: "RNG", is_elite: bool = False) -> list[str]:
    """Return 3 card IDs to choose from as a card reward.

    Cards are drawn from the Ironclad card pool with rarity weighting.
    For elite fights, 1 of the 3 cards is guaranteed to be rare.
    """
    rewards: list[str] = []

    for i in range(3):
        # Elite: first card is guaranteed rare
        guaranteed_rare = is_elite and i == 0
        pool = _roll_rarity(rng, guaranteed_rare=guaranteed_rare)
        card = rng.choice(pool)
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
    "RedSkull", "CentennialPuzzle", "JuzuBracelet", "Orichalcum", "CeramicFish",
]

UNCOMMON_RELICS: list[str] = [
    # Stub — can add more later
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
