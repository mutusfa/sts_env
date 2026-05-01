"""Treasure room logic for Slay the Spire.

Treasure rooms contain a chest that always grants a relic.
Gold is optional and depends on chest size.

Chest size roll (treasureRng): 50% SMALL / 33% MEDIUM / 17% LARGE.
A second roll (same value) determines both gold and relic tier, mirroring
C++ GameContext::setupTreasureRoom which reuses the same random value for
both chestGoldChances and chestRelicTierChances.

Relic tier by chest size (C++ chestRelicTierChances[3][2]):
  SMALL:  common=75, uncommon=25, rare= 0
  MEDIUM: common=35, uncommon=50, rare=15
  LARGE:  common= 0, uncommon=75, rare=25
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..combat.rng import RNG
from .rewards import COMMON_RELICS, UNCOMMON_RELICS, RARE_RELICS, RelicTier

if TYPE_CHECKING:
    from .character import Character


@dataclass
class TreasureResult:
    """Result of visiting a treasure room."""

    relic_found: str
    gold_found: int = 0


# Chest size roll chances: SMALL 50%, MEDIUM 33%, LARGE 17%
_SMALL_CHEST_CHANCE = 50
_MEDIUM_CHEST_CHANCE = 33
_LARGE_CHEST_CHANCE = 17

# Gold drop chance and base amount per chest size (indices 0=SMALL, 1=MEDIUM, 2=LARGE)
_CHEST_GOLD_CHANCES = (50, 35, 50)
_CHEST_GOLD_AMOUNTS = (25, 50, 75)

# (common_chance, uncommon_chance) per chest size — remainder is rare.
# Mirrors C++ chestRelicTierChances[3][2].
_CHEST_RELIC_TIER_CHANCES: tuple[tuple[int, int], ...] = (
    (75, 25),   # SMALL:  common 75%, uncommon 25%, rare  0%
    (35, 50),   # MEDIUM: common 35%, uncommon 50%, rare 15%
    (0,  75),   # LARGE:  common  0%, uncommon 75%, rare 25%
)

_RELIC_POOL_BY_TIER: dict[RelicTier, list[str]] = {
    RelicTier.COMMON:   COMMON_RELICS,
    RelicTier.UNCOMMON: UNCOMMON_RELICS,
    RelicTier.RARE:     RARE_RELICS,
}


def _chest_relic_tier(roll: int, chest_idx: int) -> RelicTier:
    """Determine relic tier from the shared gold/tier roll and chest size index."""
    common_c, uncommon_c = _CHEST_RELIC_TIER_CHANCES[chest_idx]
    if roll < common_c:
        return RelicTier.COMMON
    elif roll < common_c + uncommon_c:
        return RelicTier.UNCOMMON
    else:
        return RelicTier.RARE


def open_treasure(character: Character, rng: RNG) -> TreasureResult:
    """Open a treasure chest, granting relic and optional gold.

    Uses one roll for chest size, then a second roll for both gold determination
    and relic rarity — mirroring C++ setupTreasureRoom's single ``roll`` value.
    """
    size_roll = rng.randint(0, 99)
    if size_roll < _SMALL_CHEST_CHANCE:
        chest_idx = 0
    elif size_roll < _SMALL_CHEST_CHANCE + _MEDIUM_CHEST_CHANCE:
        chest_idx = 1
    else:
        chest_idx = 2

    # Same roll used for both gold check and relic tier (mirrors C++).
    roll = rng.randint(0, 99)

    gold = 0
    if roll < _CHEST_GOLD_CHANCES[chest_idx]:
        base_gold = _CHEST_GOLD_AMOUNTS[chest_idx]
        variance_mult = 0.9 + (0.2 * rng.random())
        gold = round(base_gold * variance_mult)
        character.gold += gold

    tier = _chest_relic_tier(roll, chest_idx)
    pool = _RELIC_POOL_BY_TIER[tier]
    owned = set(character.relics)
    available = [r for r in pool if r not in owned]
    if not available:
        # Cascade to next tier if exhausted (mirrors C++ returnRandomRelic fallback).
        for fallback_tier in (RelicTier.UNCOMMON, RelicTier.RARE, RelicTier.COMMON):
            if fallback_tier == tier:
                continue
            available = [r for r in _RELIC_POOL_BY_TIER[fallback_tier] if r not in owned]
            if available:
                break
    relic = rng.choice(available) if available else "Circlet"
    character.add_relic(relic)

    return TreasureResult(gold_found=gold, relic_found=relic)
