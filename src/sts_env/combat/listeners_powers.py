"""Power-triggered event listeners.

Each handler corresponds to a power that subscribes to an event.
Handlers are owner-agnostic: they resolve the powers bag for the given
owner (``"player"`` or enemy index) and operate on it.

Subscription table: ``POWER_SUBSCRIPTIONS[power_attr] = [(Event, handler_name)]``
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .events import Event, register_listener

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# BLOCK_GAINED handlers
# ---------------------------------------------------------------------------

def _juggernaut(state: CombatState, owner: Owner, payload: dict) -> None:
    from .powers import calc_damage, apply_damage
    powers = state.player_powers
    amount = payload.get("amount", 0)
    if powers.juggernaut <= 0 or amount <= 0:
        return
    alive = [e for e in state.enemies if e.alive and e.name != "Empty"]
    if not alive:
        return
    target = alive[state.rng.randint(0, len(alive) - 1)]
    raw = calc_damage(powers.juggernaut, powers, target.powers)
    nb, nhp = apply_damage(raw, target.block, target.hp)
    target.block = nb
    target.hp = nhp


register_listener(Event.BLOCK_GAINED, "juggernaut", _juggernaut)


# ---------------------------------------------------------------------------
# CARD_PLAYED handlers
# ---------------------------------------------------------------------------

def _rage(state: CombatState, owner: Owner, payload: dict) -> None:
    from .cards import CardType
    powers = state.player_powers
    card_spec = payload.get("card_spec")
    if card_spec is None or card_spec.card_type != CardType.ATTACK:
        return
    if powers.rage_block <= 0:
        return
    block_gain = powers.rage_block
    state.player_block += block_gain
    from .events import emit
    emit(state, Event.BLOCK_GAINED, "player", amount=block_gain)


register_listener(Event.CARD_PLAYED, "rage", _rage)


# ---------------------------------------------------------------------------
# CARD_EXHAUSTED handlers
# ---------------------------------------------------------------------------

def _sentinel(state: CombatState, owner: Owner, payload: dict) -> None:
    card = payload.get("card")
    if card is None:
        return
    from .cards import get_spec
    spec = get_spec(card.card_id)
    if spec.card_id != "Sentinel":
        return
    gain = 2 + (1 if card.upgraded else 0)
    state.energy += gain


def _dark_embrace(state: CombatState, owner: Owner, payload: dict) -> None:
    if state.player_powers.dark_embrace <= 0:
        return
    state.piles.draw_cards(state.player_powers.dark_embrace, state.rng)


def _feel_no_pain(state: CombatState, owner: Owner, payload: dict) -> None:
    if state.player_powers.feel_no_pain <= 0:
        return
    state.player_block += state.player_powers.feel_no_pain


register_listener(Event.CARD_EXHAUSTED, "sentinel", _sentinel)
register_listener(Event.CARD_EXHAUSTED, "dark_embrace", _dark_embrace)
register_listener(Event.CARD_EXHAUSTED, "feel_no_pain", _feel_no_pain)


# ---------------------------------------------------------------------------
# TURN_START handlers (duration ticks first, then behavioural)
# ---------------------------------------------------------------------------

def _tick_vulnerable(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.vulnerable > 0:
        powers.vulnerable -= 1


def _tick_weak(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.weak > 0:
        powers.weak -= 1


def _tick_frail(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.frail > 0:
        powers.frail -= 1


def _clear_entangled(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None:
        powers.entangled = False


def _demon_form(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.demon_form > 0:
        powers.strength += powers.demon_form


def _brutality(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None or powers.brutality <= 0:
        return
    # Only player has HP to lose
    if owner == "player":
        state.player_hp = max(0, state.player_hp - 1)
        state.piles.draw_cards(1, state.rng)


def _berserk(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.berserk_energy > 0:
        state.energy += powers.berserk_energy


# Duration ticks registered first (ordering matters)
register_listener(Event.TURN_START, "tick_vulnerable", _tick_vulnerable)
register_listener(Event.TURN_START, "tick_weak", _tick_weak)
register_listener(Event.TURN_START, "tick_frail", _tick_frail)
register_listener(Event.TURN_START, "clear_entangled", _clear_entangled)
# Behavioural listeners after ticks
register_listener(Event.TURN_START, "demon_form", _demon_form)
register_listener(Event.TURN_START, "brutality", _brutality)
register_listener(Event.TURN_START, "berserk", _berserk)


# ---------------------------------------------------------------------------
# TURN_END handlers
# ---------------------------------------------------------------------------

def _metallicize(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None or powers.metallicize <= 0:
        return
    if owner == "player":
        state.player_block += powers.metallicize


def _strength_loss(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None or powers.strength_loss_eot <= 0:
        return
    powers.strength -= powers.strength_loss_eot
    powers.strength_loss_eot = 0


def _dex_loss(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None or powers.dexterity_loss_eot <= 0:
        return
    powers.dexterity -= powers.dexterity_loss_eot
    powers.dexterity_loss_eot = 0


def _ritual(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None:
        return
    if powers.ritual_just_applied:
        powers.ritual_just_applied = False
    elif powers.ritual > 0:
        powers.strength += powers.ritual


register_listener(Event.TURN_END, "metallicize", _metallicize)
register_listener(Event.TURN_END, "strength_loss", _strength_loss)
register_listener(Event.TURN_END, "dex_loss", _dex_loss)
register_listener(Event.TURN_END, "ritual", _ritual)


# ---------------------------------------------------------------------------
# Subscription table for auto-subscribe when powers are gained
# ---------------------------------------------------------------------------

POWER_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {
    "juggernaut": [(Event.BLOCK_GAINED, "juggernaut")],
    "rage_block": [(Event.CARD_PLAYED, "rage")],
    "dark_embrace": [(Event.CARD_EXHAUSTED, "dark_embrace")],
    "feel_no_pain": [(Event.CARD_EXHAUSTED, "feel_no_pain")],
    "metallicize": [(Event.TURN_END, "metallicize")],
    "demon_form": [(Event.TURN_START, "demon_form")],
    "brutality": [(Event.TURN_START, "brutality")],
    "berserk_energy": [(Event.TURN_START, "berserk")],
    "ritual": [(Event.TURN_END, "ritual")],
    "vulnerable": [(Event.TURN_START, "tick_vulnerable")],
    "weak": [(Event.TURN_START, "tick_weak")],
    "frail": [(Event.TURN_START, "tick_frail")],
    "entangled": [(Event.TURN_START, "clear_entangled")],
    "strength_loss_eot": [(Event.TURN_END, "strength_loss")],
    "dexterity_loss_eot": [(Event.TURN_END, "dex_loss")],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_powers(state: CombatState, owner: Owner):
    """Return the Powers bag for the given owner, or None."""
    if owner == "player":
        return state.player_powers
    idx = owner
    if isinstance(idx, int) and 0 <= idx < len(state.enemies):
        return state.enemies[idx].powers
    return None
