"""Treasure room logic for Slay the Spire.

Treasure rooms contain a chest that always grants a relic.
Gold is optional and depends on chest size.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..combat.rng import RNG

if TYPE_CHECKING:
    from .character import Character


@dataclass
class TreasureResult:
    """Result of visiting a treasure room."""

    gold_found: int = 0
    relic_found: str | None = None


# Chest roll model mirrors sts_lightspeed constants:
# SMALL/MEDIUM/LARGE chest roll chances: 50/33/17
# Gold chance by chest size: 50/35/50
# Base gold amount by chest size: 25/50/75 (then 90%-110% variance)
_SMALL_CHEST_CHANCE = 50
_MEDIUM_CHEST_CHANCE = 33
_LARGE_CHEST_CHANCE = 17

_CHEST_GOLD_CHANCES = (50, 35, 50)
_CHEST_GOLD_AMOUNTS = (25, 50, 75)

# Common relic pool for treasure rooms
_TREASURE_RELICS = [
    "Anchor",
    "BagOfMarbles",
    "BloodVial",
    "BronzeScales",
    "CentennialPuzzle",
    "CeramicFish",
    "HappyFlower",
    "JuzuBracelet",
    "Lantern",
    "Nunchaku",
    "Orichalcum",
    "OrnamentalFan",
    "PreservedInsect",
    "RedSkull",
    "RegalPillow",
    "Shuriken",
    "Strawberry",
    "Sundial",
    "TheBoot",
    "Vajra",
    "WarPaint",
    "Whetstone",
]


def open_treasure(character: Character, rng: RNG) -> TreasureResult:
    """Open a treasure chest, granting relic and optional gold."""
    roll = rng.randint(0, 99)
    if roll < _SMALL_CHEST_CHANCE:
        chest_idx = 0  # small
    elif roll < _SMALL_CHEST_CHANCE + _MEDIUM_CHEST_CHANCE:
        chest_idx = 1  # medium
    else:
        chest_idx = 2  # large

    gold = 0
    gold_roll = rng.randint(0, 99)
    if gold_roll < _CHEST_GOLD_CHANCES[chest_idx]:
        base_gold = _CHEST_GOLD_AMOUNTS[chest_idx]
        variance_mult = 0.9 + (0.2 * rng.random())
        gold = round(base_gold * variance_mult)
        character.gold += gold

    relic = rng.choice(_TREASURE_RELICS)
    character.add_relic(relic)

    return TreasureResult(gold_found=gold, relic_found=relic)
