"""Room handlers for the strategic map layer.

Dispatches each room type to its logic:
- MONSTER / ELITE / BOSS: combat encounters via the builder
- REST: heal 30% max_hp or upgrade a card
- EVENT / SHOP / TREASURE: no-ops (v2)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .character import Character
    from .map import RoomType, StSMap, MapNode

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rest site choices
# ---------------------------------------------------------------------------

class RestChoice(Enum):
    REST = auto()     # Heal 30% of max HP
    UPGRADE = auto()  # Upgrade a card in deck
    # DIG / TOKE / LIFT: v2 (requires specific relics)


@dataclass
class RestResult:
    """Result of visiting a rest site."""
    choice: RestChoice
    card_upgraded: str | None = None  # Card ID that was upgraded (if UPGRADE)
    hp_healed: int = 0                # HP healed (if REST)


# ---------------------------------------------------------------------------
# Rest site logic
# ---------------------------------------------------------------------------

def rest_heal(character: Character) -> int:
    """Heal 30% of max HP at a rest site. Returns amount healed."""
    heal_amount = character.player_max_hp * 30 // 100  # integer division, like real StS
    hp_before = character.player_hp
    character.heal(heal_amount)
    return character.player_hp - hp_before


def rest_upgrade(character: Character, card_id: str) -> None:
    """Upgrade a card in the character's deck.

    Finds the first non-upgraded copy of card_id and replaces it
    with the upgraded version (appends '+' suffix to the card ID).

    NOTE: In the real game, card upgrades change the card's stats.
    Our upgrade system is tracked at combat time via Card.upgraded.
    Here we mark the deck entry by appending '+'.
    """
    # Find first non-upgraded copy
    for i, card in enumerate(character.deck):
        if card == card_id:
            character.deck[i] = card_id + "+"
            log.info("  Upgraded %s → %s", card_id, card_id + "+")
            return
    log.warning("  Tried to upgrade %s but no unupgraded copy found", card_id)


def pick_rest_choice(
    character: Character,
    *,
    strategy: str = "heal_if_hurt",
) -> RestResult:
    """Choose what to do at a rest site.

    Parameters
    ----------
    character:
        Current character state.
    strategy:
        "heal_if_hurt" — rest if HP < 70% max, else upgrade best card.
        "always_heal" — always rest.
        "always_upgrade" — always upgrade (if any unupgraded cards).

    Returns
    -------
    RestResult with the chosen action.
    """
    if strategy == "always_heal":
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)

    if strategy == "always_upgrade":
        card = _best_upgrade_target(character)
        if card is not None:
            rest_upgrade(character, card)
            return RestResult(choice=RestChoice.UPGRADE, card_upgraded=card)
        # No upgrade targets — fall through to heal
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)

    # Default: "heal_if_hurt"
    hp_ratio = character.player_hp / character.player_max_hp
    if hp_ratio < 0.70:
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)
    else:
        card = _best_upgrade_target(character)
        if card is not None:
            rest_upgrade(character, card)
            return RestResult(choice=RestChoice.UPGRADE, card_upgraded=card)
        # Nothing to upgrade — heal instead
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)


def _best_upgrade_target(character: Character) -> str | None:
    """Pick the best card to upgrade from the deck.

    Priority: Bash > attacks > defends > others.
    Only considers cards that haven't been upgraded yet (no '+' suffix).
    """
    from ..combat.cards import UPGRADE_BONUSES

    # Priority order of card IDs to upgrade
    upgrade_priority = [
        "Bash",       # +2 damage, +1 vuln — huge impact
        "Strike",     # +3 damage — consistent
        "Carnage",    # +8 damage — big
        "Anger",      # +3 damage
        "BodySlam",   # +0 cost — major
        "Defend",     # +3 block — consistent
        "ShrugItOff", # +1 block
        "WarCry",     # +1 draw
        "Hemokinesis",
        "PommelStrike",
        "SwordBoomerang",
        "TwinStrike",
        "ThunderClap",
        "Clothesline",
        "HeavyBlade",
        "Uppercut",
        "Bloodletting",
        "Combust",
        "Inflame",
        "Metallicize",
        "Rage",
    ]

    # Collect unupgraded cards in deck
    unupgraded = {c for c in character.deck if not c.endswith("+")}
    # Also filter to cards that have upgrade bonuses defined
    upgradeable = {c for c in unupgraded if c in UPGRADE_BONUSES}

    for card_id in upgrade_priority:
        if card_id in upgradeable:
            return card_id

    # Fallback: any unupgraded card with an upgrade bonus
    if upgradeable:
        return sorted(upgradeable)[0]

    return None
