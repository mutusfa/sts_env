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

REST_HEAL_FRACTION = 0.30


def rest_heal(character: Character) -> int:
    """Heal 30% of max HP at a rest site. Returns amount healed."""
    heal_amount = round(character.player_max_hp * REST_HEAL_FRACTION)
    if "RegalPillow" in character.relics:
        heal_amount += 15
    hp_before = character.player_hp
    character.heal(heal_amount)
    return character.player_hp - hp_before


def rest_upgrade(character: Character, card_id: str) -> None:
    """Upgrade a card in the character's deck.

    Finds the first upgradable copy matching card_id (base or deck entry)
    and appends one '+' suffix.
    """
    from ..combat.cards import apply_upgrade, find_upgrade_index

    idx = find_upgrade_index(character.deck, card_id)
    if idx is None:
        log.warning("  Tried to upgrade %s but no upgradable copy found", card_id)
        return
    before = character.deck[idx]
    character.deck[idx] = apply_upgrade(before)
    log.info("  Upgraded %s → %s", before, character.deck[idx])


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
    from . import relics as relic_mod

    can_heal = relic_mod.can_rest(character.relics)
    can_up = relic_mod.can_upgrade(character.relics)

    if strategy == "always_heal":
        if can_heal:
            healed = rest_heal(character)
            return RestResult(choice=RestChoice.REST, hp_healed=healed)
        # Can't rest — try upgrade instead
        if can_up:
            card = _best_upgrade_target(character)
            if card is not None:
                rest_upgrade(character, card)
                return RestResult(choice=RestChoice.UPGRADE, card_upgraded=card)
        # Neither option available — forced rest (shouldn't happen)
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)

    if strategy == "always_upgrade":
        if can_up:
            card = _best_upgrade_target(character)
            if card is not None:
                rest_upgrade(character, card)
                return RestResult(choice=RestChoice.UPGRADE, card_upgraded=card)
        # No upgrade targets or can't upgrade — fall through to heal
        if can_heal:
            healed = rest_heal(character)
            return RestResult(choice=RestChoice.REST, hp_healed=healed)
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)

    # Default: "heal_if_hurt"
    hp_ratio = character.player_hp / character.player_max_hp
    if hp_ratio < 0.70 and can_heal:
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)
    else:
        if can_up:
            card = _best_upgrade_target(character)
            if card is not None:
                rest_upgrade(character, card)
                return RestResult(choice=RestChoice.UPGRADE, card_upgraded=card)
        # Nothing to upgrade or can't upgrade — heal instead
        if can_heal:
            healed = rest_heal(character)
            return RestResult(choice=RestChoice.REST, hp_healed=healed)
        # Fallback
        healed = rest_heal(character)
        return RestResult(choice=RestChoice.REST, hp_healed=healed)


def _best_upgrade_target(character: Character) -> str | None:
    """Pick the best card to upgrade from the deck.

    Priority: Bash > attacks > defends > others.
    Only considers cards that are currently upgradable.
    """
    from ..combat.cards import is_upgradable

    # Priority order of card IDs to upgrade
    upgrade_priority = [
        "Bash",       # +2 damage, +1 vuln — huge impact
        "Strike",     # +3 damage — consistent
        "Carnage",    # +8 damage — big
        "Anger",      # +3 damage
        "Defend",     # +3 block — consistent
        "BodySlam",   # cost 1→0 — free block-damage
        "Hemokinesis",# +6 damage
        "HeavyBlade", # +4 damage + 1x str multiplier
        "ShrugItOff", # +1 block
        "WarCry",     # +1 draw
        "PommelStrike",
        "SwordBoomerang",
        "TwinStrike",
        "ThunderClap",
        "Clothesline",
        "Uppercut",
        "Bloodletting",
        "Combust",
        "Inflame",
        "Metallicize",
        "Rage",
    ]

    upgradeable = [c for c in character.deck if is_upgradable(c)]
    upgradeable_bases = {c.rstrip("+") for c in upgradeable}

    for card_id in upgrade_priority:
        if card_id in upgradeable_bases:
            for c in upgradeable:
                if c.rstrip("+") == card_id:
                    return c

    if upgradeable:
        return sorted(upgradeable)[0]

    return None
