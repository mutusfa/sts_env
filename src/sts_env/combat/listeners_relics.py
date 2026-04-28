"""Relic-triggered event listeners.

Relics subscribe at Combat.reset based on ``state.relics``.
Per-relic counters live in ``state.relic_state`` (a dict[str, int]).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .events import Event, listener

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# Subscription table
# ---------------------------------------------------------------------------

RELIC_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {}


def _is_attack_card(payload: dict) -> bool:
    """Return True if CARD_PLAYED payload carries an Attack card."""
    card = payload.get("card")
    if card is None or card.spec is None:
        return False
    from .cards import CardType
    return card.spec.card_type == CardType.ATTACK


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
        state.relic_state["red_skull_active"] = 1


@listener(Event.HP_LOSS, "red_skull", subscriptions=[(RELIC_SUBSCRIPTIONS, "RedSkull")])
def _red_skull(state: CombatState, owner: Owner, payload: dict) -> None:
    """On HP_LOSS for player, recompute RedSkull strength bonus."""
    if "RedSkull" not in state.relics:
        return
    if owner != "player":
        return
    was_active = state.relic_state.get("red_skull_active", 0)
    should_be_active = state.player_hp <= state.player_max_hp // 2
    if should_be_active and not was_active:
        state.player_powers.strength += 3
        state.relic_state["red_skull_active"] = 1
    elif not should_be_active and was_active:
        state.player_powers.strength -= 3
        state.relic_state["red_skull_active"] = 0


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
# CentennialPuzzle: draw 3 cards the first time you lose HP each combat
# ---------------------------------------------------------------------------

@listener(Event.COMBAT_START, "centennial_puzzle_init", subscriptions=[(RELIC_SUBSCRIPTIONS, "CentennialPuzzle")])
def _centennial_puzzle_init(state: CombatState, owner: Owner, payload: dict) -> None:
    """Reset the per-combat 'used this combat' flag."""
    if owner != "player":
        return
    state.relic_state["centennial_puzzle_used"] = 0


@listener(Event.HP_LOSS, "centennial_puzzle", subscriptions=[(RELIC_SUBSCRIPTIONS, "CentennialPuzzle")])
def _centennial_puzzle(state: CombatState, owner: Owner, payload: dict) -> None:
    """Draw 3 cards the first time the player loses HP each combat."""
    if owner != "player":
        return
    if state.relic_state.get("centennial_puzzle_used", 0):
        return
    state.relic_state["centennial_puzzle_used"] = 1
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


# ---------------------------------------------------------------------------
# Shuriken: every 3 attacks in one turn → +1 Strength
# Per-turn counter, resets at TURN_END.
# ---------------------------------------------------------------------------

@listener(Event.CARD_PLAYED, "shuriken", subscriptions=[(RELIC_SUBSCRIPTIONS, "Shuriken")])
def _shuriken(state: CombatState, owner: Owner, payload: dict) -> None:
    """On CARD_PLAYED (attack only), increment counter; at 3, gain 1 Strength."""
    if "Shuriken" not in state.relics:
        return
    if not _is_attack_card(payload):
        return
    c = state.relic_state.get("shuriken", 0) + 1
    if c >= 3:
        c = 0
        state.player_powers.strength += 1
    state.relic_state["shuriken"] = c


@listener(Event.TURN_END, "shuriken_reset", subscriptions=[(RELIC_SUBSCRIPTIONS, "Shuriken")])
def _shuriken_reset(state: CombatState, owner: Owner, payload: dict) -> None:
    """Reset Shuriken counter at end of player turn."""
    if owner != "player":
        return
    state.relic_state["shuriken"] = 0


# ---------------------------------------------------------------------------
# Kunai: every 3 attacks in one turn → +1 Dexterity
# Per-turn counter, resets at TURN_END.
# ---------------------------------------------------------------------------

@listener(Event.CARD_PLAYED, "kunai", subscriptions=[(RELIC_SUBSCRIPTIONS, "Kunai")])
def _kunai(state: CombatState, owner: Owner, payload: dict) -> None:
    """On CARD_PLAYED (attack only), increment counter; at 3, gain 1 Dexterity."""
    if "Kunai" not in state.relics:
        return
    if not _is_attack_card(payload):
        return
    c = state.relic_state.get("kunai", 0) + 1
    if c >= 3:
        c = 0
        state.player_powers.dexterity += 1
    state.relic_state["kunai"] = c


@listener(Event.TURN_END, "kunai_reset", subscriptions=[(RELIC_SUBSCRIPTIONS, "Kunai")])
def _kunai_reset(state: CombatState, owner: Owner, payload: dict) -> None:
    """Reset Kunai counter at end of player turn."""
    if owner != "player":
        return
    state.relic_state["kunai"] = 0


# ---------------------------------------------------------------------------
# Pen Nib: every 10 attacks across the entire run → next attack deals double
# Per-run counter persists across combats via relic_state sync.
# The "active" flag is consumed in attack_enemy() (powers.py).
# ---------------------------------------------------------------------------

@listener(Event.CARD_PLAYED, "pen_nib", subscriptions=[(RELIC_SUBSCRIPTIONS, "PenNib")])
def _pen_nib(state: CombatState, owner: Owner, payload: dict) -> None:
    """On CARD_PLAYED (attack only), increment counter; at 10, activate double damage."""
    if "PenNib" not in state.relics:
        return
    if not _is_attack_card(payload):
        return
    c = state.relic_state.get("pen_nib", 0) + 1
    if c >= 10:
        c = 0
        state.relic_state["pen_nib_active"] = 1
    state.relic_state["pen_nib"] = c


# ---------------------------------------------------------------------------
# Nunchaku: every 10 attacks across the entire run → gain 1 energy
# Per-run counter persists across combats via relic_state sync.
# ---------------------------------------------------------------------------

@listener(Event.CARD_PLAYED, "nunchaku", subscriptions=[(RELIC_SUBSCRIPTIONS, "Nunchaku")])
def _nunchaku(state: CombatState, owner: Owner, payload: dict) -> None:
    """On CARD_PLAYED (attack only), increment counter; at 10, gain 1 energy."""
    if "Nunchaku" not in state.relics:
        return
    if not _is_attack_card(payload):
        return
    c = state.relic_state.get("nunchaku", 0) + 1
    if c >= 10:
        c = 0
        state.energy += 1
    state.relic_state["nunchaku"] = c
