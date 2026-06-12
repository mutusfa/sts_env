"""Relic-triggered event listeners.

Relics subscribe during :class:`Combat` construction based on ``state.relics``.
Per-relic counters live in ``state.relic_state``; charges/disable in ``relic_data``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .relic_state import disable_relic_combat, relic_active
from .healing import heal_player
from .events import Event, listener

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


RELIC_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {}


def _active(state: CombatState, relic_id: str) -> bool:
    return relic_active(
        relic_id,
        owned=state.relics,
        relic_data=state.relic_data,
        combat_disabled=state.relic_combat_disabled,
    )


def _is_attack_card(payload: dict) -> bool:
    card = payload.get("card")
    if card is None or card.spec is None:
        return False
    from .cards import CardType
    return card.spec.card_type == CardType.ATTACK


# ---------------------------------------------------------------------------
# RedSkull
# ---------------------------------------------------------------------------

def _red_skull_update(state: CombatState) -> None:
    if not _active(state, "RedSkull"):
        return
    was_active = state.relic_state.get("red_skull_active", 0)
    should_be_active = state.player_hp <= state.player_max_hp // 2
    if should_be_active and not was_active:
        state.player_powers.strength += 3
        state.relic_state["red_skull_active"] = 1
    elif not should_be_active and was_active:
        state.player_powers.strength -= 3
        state.relic_state["red_skull_active"] = 0


@listener(Event.COMBAT_START_PRE_DRAW, "red_skull_init", subscriptions=[(RELIC_SUBSCRIPTIONS, "RedSkull")])
def _red_skull_init(state: CombatState, owner: Owner, payload: dict) -> None:
    _red_skull_update(state)


@listener(Event.HP_LOSS, "red_skull", subscriptions=[(RELIC_SUBSCRIPTIONS, "RedSkull")])
def _red_skull_hp_loss(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player":
        return
    _red_skull_update(state)


@listener(Event.HP_GAIN, "red_skull_heal", subscriptions=[(RELIC_SUBSCRIPTIONS, "RedSkull")])
def _red_skull_heal(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player":
        return
    _red_skull_update(state)


# ---------------------------------------------------------------------------
# Pre-draw combat start
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START_PRE_DRAW, "anchor", subscriptions=[(RELIC_SUBSCRIPTIONS, "Anchor")])
def _anchor(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "Anchor"):
        state.player_block += 10


@listener(Event.COMBAT_START_PRE_DRAW, "lantern", subscriptions=[(RELIC_SUBSCRIPTIONS, "Lantern")])
def _lantern(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "Lantern"):
        state.energy += 1


@listener(Event.COMBAT_START_PRE_DRAW, "vajra", subscriptions=[(RELIC_SUBSCRIPTIONS, "Vajra")])
def _vajra(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "Vajra"):
        state.player_powers.strength += 1


@listener(Event.COMBAT_START_PRE_DRAW, "preserved_insect", subscriptions=[(RELIC_SUBSCRIPTIONS, "PreservedInsect")])
def _preserved_insect(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "PreservedInsect") or not state.is_elite:
        return
    for enemy in state.enemies:
        if enemy.name != "Empty" and enemy.hp > 0:
            enemy.hp = max(1, (enemy.max_hp * 3) // 4)


@listener(Event.COMBAT_START_PRE_DRAW, "blood_vial", subscriptions=[(RELIC_SUBSCRIPTIONS, "BloodVial")])
def _blood_vial(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "BloodVial"):
        heal_player(state, 2)


@listener(Event.COMBAT_START_PRE_DRAW, "bronze_scales", subscriptions=[(RELIC_SUBSCRIPTIONS, "BronzeScales")])
def _bronze_scales(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "BronzeScales"):
        state.player_powers.thorns += 3


@listener(Event.COMBAT_START_PRE_DRAW, "pantograph", subscriptions=[(RELIC_SUBSCRIPTIONS, "Pantograph")])
def _pantograph(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "Pantograph") and state.is_boss:
        heal_player(state, 25)


# ---------------------------------------------------------------------------
# Post-draw combat start
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "bag_of_marbles", subscriptions=[(RELIC_SUBSCRIPTIONS, "BagOfMarbles")])
def _bag_of_marbles(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "BagOfMarbles"):
        return
    for enemy in state.enemies:
        if enemy.name != "Empty" and enemy.hp > 0:
            enemy.powers.vulnerable += 1


@listener(Event.COMBAT_START, "bag_of_preparation", subscriptions=[(RELIC_SUBSCRIPTIONS, "BagOfPreparation")])
def _bag_of_preparation(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "BagOfPreparation"):
        state.piles.draw_cards(2, state.rng, state=state)


# ---------------------------------------------------------------------------
# Turn start
# ---------------------------------------------------------------------------

@listener(Event.TURN_START, "ring_of_serpents", subscriptions=[(RELIC_SUBSCRIPTIONS, "RingOfSerpents")])
def _ring_of_serpents(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or not _active(state, "RingOfSerpents"):
        return
    state.piles.draw_cards(1, state.rng, state=state)


@listener(Event.TURN_START, "busted_crown", subscriptions=[(RELIC_SUBSCRIPTIONS, "BustedCrown")])
def _busted_crown(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or not _active(state, "BustedCrown"):
        return
    state.energy += 1


@listener(Event.TURN_START, "coffee_dripper", subscriptions=[(RELIC_SUBSCRIPTIONS, "CoffeeDripper")])
def _coffee_dripper(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or not _active(state, "CoffeeDripper"):
        return
    state.energy += 1


@listener(Event.TURN_START, "fusion_hammer", subscriptions=[(RELIC_SUBSCRIPTIONS, "FusionHammer")])
def _fusion_hammer(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or not _active(state, "FusionHammer"):
        return
    state.energy += 1


@listener(Event.TURN_START, "happy_flower", subscriptions=[(RELIC_SUBSCRIPTIONS, "HappyFlower")])
def _happy_flower(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or not _active(state, "HappyFlower"):
        return
    c = state.relic_state.get("happy_flower", 0) + 1
    if c >= 3:
        c = 0
        state.energy += 1
    state.relic_state["happy_flower"] = c


# ---------------------------------------------------------------------------
# Turn end
# ---------------------------------------------------------------------------

@listener(Event.TURN_END, "orichalcum", subscriptions=[(RELIC_SUBSCRIPTIONS, "Orichalcum")])
def _orichalcum(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or not _active(state, "Orichalcum"):
        return
    if state.player_block <= 0:
        state.player_block += 6


# ---------------------------------------------------------------------------
# HP loss / revival
# ---------------------------------------------------------------------------

@listener(Event.HP_LOSS, "centennial_puzzle", subscriptions=[(RELIC_SUBSCRIPTIONS, "CentennialPuzzle")])
def _centennial_puzzle(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or not _active(state, "CentennialPuzzle"):
        return
    state.piles.draw_cards(3, state.rng, state=state)
    disable_relic_combat("CentennialPuzzle", state)


@listener(Event.HP_LOSS, "lizard_tail", subscriptions=[(RELIC_SUBSCRIPTIONS, "LizardTail")])
def _lizard_tail(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or state.player_hp > 0:
        return
    if not _active(state, "LizardTail"):
        return
    heal_player(state, state.player_max_hp // 2)
    disable_relic_combat("LizardTail", state)
    state.relic_data["LizardTail"] = 0


# ---------------------------------------------------------------------------
# Potions
# ---------------------------------------------------------------------------

@listener(Event.POTION_USED, "toy_ornithopter", subscriptions=[(RELIC_SUBSCRIPTIONS, "ToyOrnithopter")])
def _toy_ornithopter(state: CombatState, owner: Owner, payload: dict) -> None:
    if _active(state, "ToyOrnithopter"):
        heal_player(state, 5)


# ---------------------------------------------------------------------------
# Card played
# ---------------------------------------------------------------------------

@listener(Event.CARD_PLAYED, "shuriken", subscriptions=[(RELIC_SUBSCRIPTIONS, "Shuriken")])
def _shuriken(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "Shuriken") or not _is_attack_card(payload):
        return
    c = state.relic_state.get("shuriken", 0) + 1
    if c >= 3:
        c = 0
        state.player_powers.strength += 1
    state.relic_state["shuriken"] = c


@listener(Event.TURN_END, "shuriken_reset", subscriptions=[(RELIC_SUBSCRIPTIONS, "Shuriken")])
def _shuriken_reset(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner == "player":
        state.relic_state["shuriken"] = 0


@listener(Event.CARD_PLAYED, "kunai", subscriptions=[(RELIC_SUBSCRIPTIONS, "Kunai")])
def _kunai(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "Kunai") or not _is_attack_card(payload):
        return
    c = state.relic_state.get("kunai", 0) + 1
    if c >= 3:
        c = 0
        state.player_powers.dexterity += 1
    state.relic_state["kunai"] = c


@listener(Event.TURN_END, "kunai_reset", subscriptions=[(RELIC_SUBSCRIPTIONS, "Kunai")])
def _kunai_reset(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner == "player":
        state.relic_state["kunai"] = 0


@listener(Event.CARD_PLAYED, "ornamental_fan", subscriptions=[(RELIC_SUBSCRIPTIONS, "OrnamentalFan")])
def _ornamental_fan(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "OrnamentalFan") or not _is_attack_card(payload):
        return
    c = state.relic_state.get("ornamental_fan", 0) + 1
    if c >= 3:
        c = 0
        state.player_block += 4
    state.relic_state["ornamental_fan"] = c


@listener(Event.TURN_END, "ornamental_fan_reset", subscriptions=[(RELIC_SUBSCRIPTIONS, "OrnamentalFan")])
def _ornamental_fan_reset(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner == "player":
        state.relic_state["ornamental_fan"] = 0


@listener(Event.CARD_PLAYED, "pen_nib", subscriptions=[(RELIC_SUBSCRIPTIONS, "PenNib")])
def _pen_nib(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "PenNib") or not _is_attack_card(payload):
        return
    c = state.relic_state.get("pen_nib", 0) + 1
    if c >= 10:
        c = 0
        state.relic_state["pen_nib_active"] = 1
    state.relic_state["pen_nib"] = c


@listener(Event.CARD_PLAYED, "nunchaku", subscriptions=[(RELIC_SUBSCRIPTIONS, "Nunchaku")])
def _nunchaku(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "Nunchaku") or not _is_attack_card(payload):
        return
    c = state.relic_state.get("nunchaku", 0) + 1
    if c >= 10:
        c = 0
        state.energy += 1
    state.relic_state["nunchaku"] = c


@listener(Event.CARD_PLAYED, "ink_bottle", subscriptions=[(RELIC_SUBSCRIPTIONS, "InkBottle")])
def _ink_bottle(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "InkBottle"):
        return
    c = state.relic_state.get("ink_bottle", 0) + 1
    if c >= 10:
        c = 0
        state.piles.draw_cards(1, state.rng, state=state)
    state.relic_state["ink_bottle"] = c


# ---------------------------------------------------------------------------
# Shuffle
# ---------------------------------------------------------------------------

@listener(Event.DECK_SHUFFLED, "sundial", subscriptions=[(RELIC_SUBSCRIPTIONS, "Sundial")])
def _sundial(state: CombatState, owner: Owner, payload: dict) -> None:
    if not _active(state, "Sundial"):
        return
    c = state.relic_state.get("sundial", 0) + 1
    if c >= 3:
        c = 0
        state.energy += 2
    state.relic_state["sundial"] = c
