"""Relic-triggered event listeners.

Relics subscribe at Combat.reset based on ``state.relics``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .events import Event, listener
from .powers import Powers

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# Subscription table
# ---------------------------------------------------------------------------

RELIC_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {}


# ---------------------------------------------------------------------------
# RedSkull: +3 Strength while HP <= 50% of max
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "red_skull_init", subscriptions=[(RELIC_SUBSCRIPTIONS, "RedSkull")])
def _red_skull_init(state: CombatState, owner: Owner, payload: dict) -> None:
    """At COMBAT_START, apply RedSkull if player starts at or below 50% HP."""
    if "RedSkull" not in state.relics:
        return
    if state.player_hp <= state.player_max_hp // 2:
        state.player_powers.strength += 3
        state.player_powers._red_skull_active = True


@listener(Event.HP_LOSS, "red_skull", subscriptions=[(RELIC_SUBSCRIPTIONS, "RedSkull")])
def _red_skull(state: CombatState, owner: Owner, payload: dict) -> None:
    """On HP_LOSS for player, recompute RedSkull strength bonus."""
    if "RedSkull" not in state.relics:
        return
    if owner != "player":
        return
    was_active = getattr(state.player_powers, "_red_skull_active", False)
    should_be_active = state.player_hp <= state.player_max_hp // 2
    if should_be_active and not was_active:
        state.player_powers.strength += 3
        state.player_powers._red_skull_active = True
    elif not should_be_active and was_active:
        state.player_powers.strength -= 3
        state.player_powers._red_skull_active = False


# ---------------------------------------------------------------------------
# Orichalcum: if you end your turn with 0 Block, gain 6 Block
# ---------------------------------------------------------------------------

@listener(Event.TURN_END, "orichalcum", subscriptions=[(RELIC_SUBSCRIPTIONS, "Orichalcum")])
def _orichalcum(state: CombatState, owner: Owner, payload: dict) -> None:
    """Gain 6 block at end of player turn if block is 0."""
    if owner != "player":
        return
    if state.player_block <= 0:
        state.player_block += 6


# ---------------------------------------------------------------------------
# RingOfSerpents: draw 1 additional card each turn
# ---------------------------------------------------------------------------

@listener(Event.TURN_START, "ring_of_serpents", subscriptions=[(RELIC_SUBSCRIPTIONS, "RingOfSerpents")])
def _ring_of_serpents(state: CombatState, owner: Owner, payload: dict) -> None:
    """Draw 1 extra card at start of player turn."""
    if owner != "player":
        return
    state.piles.draw_cards(1, state.rng)


# ---------------------------------------------------------------------------
# BustedCrown: +1 energy each turn
# ---------------------------------------------------------------------------

@listener(Event.TURN_START, "busted_crown", subscriptions=[(RELIC_SUBSCRIPTIONS, "BustedCrown")])
def _busted_crown(state: CombatState, owner: Owner, payload: dict) -> None:
    """Gain 1 energy at start of player turn."""
    if owner != "player":
        return
    state.energy += 1


# ---------------------------------------------------------------------------
# CentennialPuzzle: draw 1 card the first time you're attacked each combat
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "centennial_puzzle_init", subscriptions=[(RELIC_SUBSCRIPTIONS, "CentennialPuzzle")])
def _centennial_puzzle_init(state: CombatState, owner: Owner, payload: dict) -> None:
    """Reset the per-combat 'attacked this combat' flag."""
    if owner != "player":
        return
    state.player_powers._centennial_puzzle_used = False


@listener(Event.HP_LOSS, "centennial_puzzle", subscriptions=[(RELIC_SUBSCRIPTIONS, "CentennialPuzzle")])
def _centennial_puzzle(state: CombatState, owner: Owner, payload: dict) -> None:
    """Draw 3 cards the first time the player loses HP each combat (any source)."""
    if owner != "player":
        return
    if getattr(state.player_powers, "_centennial_puzzle_used", False):
        return
    state.player_powers._centennial_puzzle_used = True
    state.piles.draw_cards(3, state.rng)


# ---------------------------------------------------------------------------
# Anchor: gain 10 block at start of combat
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "anchor", subscriptions=[(RELIC_SUBSCRIPTIONS, "Anchor")])
def _anchor(state: CombatState, owner: Owner, payload: dict) -> None:
    """Gain 10 block at the start of combat."""
    state.player_block += 10


# ---------------------------------------------------------------------------
# BagOfMarbles: apply 1 Vulnerable to all enemies at start of combat
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "bag_of_marbles", subscriptions=[(RELIC_SUBSCRIPTIONS, "BagOfMarbles")])
def _bag_of_marbles(state: CombatState, owner: Owner, payload: dict) -> None:
    """Apply 1 Vulnerable to all enemies at the start of combat."""
    for enemy in state.enemies:
        if enemy.name != "Empty" and enemy.hp > 0:
            enemy.powers.vulnerable += 1


# ---------------------------------------------------------------------------
# Lantern: gain 1 energy at start of combat
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "lantern", subscriptions=[(RELIC_SUBSCRIPTIONS, "Lantern")])
def _lantern(state: CombatState, owner: Owner, payload: dict) -> None:
    """Gain 1 energy at the start of combat."""
    state.energy += 1


# ---------------------------------------------------------------------------
# Vajra: gain 1 strength at start of combat
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "vajra", subscriptions=[(RELIC_SUBSCRIPTIONS, "Vajra")])
def _vajra(state: CombatState, owner: Owner, payload: dict) -> None:
    """Gain 1 strength at the start of combat."""
    state.player_powers.strength += 1


# ---------------------------------------------------------------------------
# PreservedInsect: reduce enemy HP by 25% for elite encounters
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "preserved_insect", subscriptions=[(RELIC_SUBSCRIPTIONS, "PreservedInsect")])
def _preserved_insect(state: CombatState, owner: Owner, payload: dict) -> None:
    """Reduce enemy HP by 25% at the start of elite combats."""
    if not state.is_elite:
        return
    for enemy in state.enemies:
        if enemy.name != "Empty" and enemy.hp > 0:
            reduction = enemy.max_hp // 4
            enemy.hp = max(1, enemy.hp - reduction)


# ---------------------------------------------------------------------------
# ToyOrnithopter: heal 5 HP when a potion is used
# ---------------------------------------------------------------------------

@listener(Event.POTION_USED, "toy_ornithopter", subscriptions=[(RELIC_SUBSCRIPTIONS, "ToyOrnithopter")])
def _toy_ornithopter(state: CombatState, owner: Owner, payload: dict) -> None:
    """Heal 5 HP when a potion is used."""
    state.player_hp = min(state.player_max_hp, state.player_hp + 5)

