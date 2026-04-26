"""Treasure room logic for Slay the Spire.

Treasure rooms contain a chest that awards gold and have a small chance
of dropping a common relic.
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


_RELIC_DROP_CHANCE = 0.25  # 25% chance to find a relic in treasure
_GOLD_MIN = 20
_GOLD_MAX = 30

# Common relic pool for treasure rooms
_TREASURE_RELICS = [
    "Anchor",
    "BagOfMarbles",
    "CentennialPuzzle",
    "CeramicFish",
    "DreamCatcher",
    "JuzuBracelet",
    "Lantern",
    "MawBank",
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


def open_treasure(character: Character, rng: RNG) -> TreasureResult:
    """Open a treasure chest. Adds gold to character, maybe a relic."""
    gold = rng.randint(_GOLD_MIN, _GOLD_MAX)
    character.gold += gold

    relic = None
    if rng.random() < _RELIC_DROP_CHANCE:
        relic = rng.choice(_TREASURE_RELICS)
        character.relics.append(relic)

    return TreasureResult(gold_found=gold, relic_found=relic)
