"""Neow's blessing at the start of an Act 1 run."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from .character import Character

if TYPE_CHECKING:
    from ..combat.rng import RNG


class NeowChoice(Enum):
    MAX_HP = auto()        # +7 max HP
    RANDOM_RELIC = auto()  # gain a random common relic
    REMOVE_CARD = auto()   # remove Strike or Defend from deck
    RANDOM_CARD = auto()   # add a random uncommon+ card to deck


@dataclass
class NeowOption:
    choice: NeowChoice
    description: str


# Common relic pool — imported from rewards.py to avoid duplication
from .rewards import COMMON_RELICS as _COMMON_RELIC_POOL

# Cards available as random Neow reward (uncommon+ Ironclad cards)
_NEOW_CARD_POOL = [
    "ShrugItOff", "PommelStrike", "Inflame", "Metallicize",
    "Rage", "SecondWind", "WarCry", "Clothesline",
    "ThunderClap", "Headbutt", "TwinStrike", "Carnage",
    "Uppercut", "HeavyBlade", "BodySlam", "Hemokinesis",
]


def roll_neow_options(rng: RNG) -> list[NeowOption]:
    """Generate 4 Neow blessing options."""
    return [
        NeowOption(NeowChoice.MAX_HP, "+7 Max HP"),
        NeowOption(NeowChoice.RANDOM_RELIC, "Random common relic"),
        NeowOption(NeowChoice.REMOVE_CARD, "Remove a card"),
        NeowOption(NeowChoice.RANDOM_CARD, "Random uncommon card"),
    ]


def apply_neow(choice: NeowChoice, character: Character, rng: RNG) -> str:
    """Apply Neow's blessing to the character. Returns description of what happened."""
    if choice == NeowChoice.MAX_HP:
        character.player_max_hp += 7
        character.player_hp += 7  # Also heal the bonus
        return f"+7 Max HP (now {character.player_hp}/{character.player_max_hp})"

    elif choice == NeowChoice.RANDOM_RELIC:
        # Pick a relic character doesn't already have
        available = [r for r in _COMMON_RELIC_POOL if r not in character.relics]
        if available:
            relic = rng.choice(available)
            character.relics.append(relic)
            return f"Gained relic: {relic}"
        return "No available relics"

    elif choice == NeowChoice.REMOVE_CARD:
        # Remove worst basic: prefer Strike first, then Defend
        for target in ["Strike", "Defend"]:
            if target in character.deck:
                character.deck.remove(target)
                return f"Removed {target} from deck"
        return "No basic cards to remove"

    elif choice == NeowChoice.RANDOM_CARD:
        card = rng.choice(_NEOW_CARD_POOL)
        character.deck.append(card)
        return f"Added {card} to deck"

    return "Unknown choice"
