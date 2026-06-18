"""Run-layer relic hooks (room enter, mystery rooms, shop gold spend)."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from ..combat.rng import RNG
from .map import RoomType
from ..combat.relic_state import relic_active
from .relic_state import disable_relic_run

if TYPE_CHECKING:
    from .character import Character


class MysteryOutcome(Enum):
    MONSTER = auto()
    SHOP = auto()
    TREASURE = auto()
    EVENT = auto()


# C++ room outcome chances (getEventRoomOutcomeHelper).
_MONSTER_CHANCE = 0.10
_SHOP_CHANCE = 0.03
_TREASURE_CHANCE = 0.03


def apply_egg_upgrade(card_id: str, relics: list[str] | set[str]) -> str:
    """Return card_id with '+' suffix when an egg relic would auto-upgrade it.

    Used at offer time (rewards, shop) so agents see the upgraded card ID
    they will receive, without tracking egg state themselves.
    """
    if not card_id or card_id.endswith("+"):
        return card_id
    from ..combat.cards import CardType, get_spec

    try:
        spec = get_spec(card_id)
    except KeyError:
        return card_id
    if spec.card_type == CardType.ATTACK and "MoltenEgg" in relics:
        return card_id + "+"
    if spec.card_type == CardType.SKILL and "FrozenEgg" in relics:
        return card_id + "+"
    if spec.card_type == CardType.POWER and "ToxicEgg" in relics:
        return card_id + "+"
    return card_id


def _upgrade_random_card(character: Character, card_type: str) -> None:
    from ..combat.cards import CardType, apply_upgrade, get_spec, is_upgradable

    type_map = {
        "attack": CardType.ATTACK,
        "skill": CardType.SKILL,
    }
    want = type_map[card_type]
    candidates = [
        i for i, cid in enumerate(character.deck)
        if is_upgradable(cid) and get_spec(cid.rstrip("+")).card_type == want
    ]
    if not candidates:
        return
    idx = candidates[0]
    character.deck[idx] = apply_upgrade(character.deck[idx])


def apply_relic_on_obtain(character: Character, relic_id: str) -> None:
    """Immediate effects when a relic is acquired (C++ obtainRelic)."""
    if relic_id == "Whetstone":
        _upgrade_random_card(character, "attack")
    elif relic_id == "WarPaint":
        _upgrade_random_card(character, "skill")
    elif relic_id == "Strawberry":
        character.player_max_hp += 7
        character.heal(7)
    elif relic_id == "TinyHouse":
        character.player_max_hp += 5
        character.heal(5)
        character.gold += 50
        _upgrade_random_card(character, "attack")
    elif relic_id == "OldCoin":
        character.gold += 300


def spend_gold_at_shop(character: Character, amount: int) -> None:
    """Deduct gold from a shop purchase and apply shop-specific relic effects."""
    if amount <= 0:
        return
    character.gold = max(0, character.gold - amount)
    if "MawBank" in character.relics:
        disable_relic_run("MawBank", character)


def relics_on_enter_room(character: Character, room_type: RoomType) -> None:
    """Apply relic effects when entering a new map room (C++ relicsOnEnterRoom)."""
    if relic_active(
        "MawBank",
        owned=character.relics,
        relic_data=character.relic_data,
    ):
        character.gold += 12

    if room_type == RoomType.SHOP and "MealTicket" in character.relics:
        character.heal(15)


def resolve_mystery_room(
    rng: RNG,
    character: Character,
    *,
    last_room_was_shop: bool = False,
) -> MysteryOutcome:
    """Roll a ?-room outcome (C++ getEventRoomOutcomeHelper).

    Used for mystery-room mechanics; fixed-map EVENT nodes bypass this.
    """
    if "TinyChest" in character.relics:
        visits = character.relic_data.get("TinyChest", 0)
        if visits == 3:
            character.relic_data["TinyChest"] = 0
            return MysteryOutcome.TREASURE
        character.relic_data["TinyChest"] = visits + 1

    roll = rng.random()
    shop_cutoff = _MONSTER_CHANCE + (0.0 if last_room_was_shop else _SHOP_CHANCE)
    treasure_cutoff = shop_cutoff + _TREASURE_CHANCE

    if roll < _MONSTER_CHANCE:
        outcome = MysteryOutcome.MONSTER
    elif roll < shop_cutoff:
        outcome = MysteryOutcome.SHOP
    elif roll < treasure_cutoff:
        outcome = MysteryOutcome.TREASURE
    else:
        outcome = MysteryOutcome.EVENT

    if outcome == MysteryOutcome.MONSTER and "JuzuBracelet" in character.relics:
        outcome = MysteryOutcome.EVENT

    return outcome
