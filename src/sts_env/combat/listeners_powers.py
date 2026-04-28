"""Power-triggered event listeners.

Each handler corresponds to a power that subscribes to an event.
Handlers are owner-agnostic: they resolve the powers bag for the given
owner (``"player"`` or enemy index) and operate on it.

Subscription table: ``POWER_SUBSCRIPTIONS[power_attr] = [(Event, handler_name)]``
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .cards import CardType, TargetType
from .events import Event, listener

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# Subscription table for auto-subscribe when powers are gained
# ---------------------------------------------------------------------------

POWER_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {}


# ---------------------------------------------------------------------------
# BLOCK_GAINED handlers
# ---------------------------------------------------------------------------

@listener(Event.BLOCK_GAINED, "juggernaut", subscriptions=[(POWER_SUBSCRIPTIONS, "juggernaut")])
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


# ---------------------------------------------------------------------------
# CARD_PLAYED handlers
# ---------------------------------------------------------------------------

@listener(Event.CARD_PLAYED, "rage", subscriptions=[(POWER_SUBSCRIPTIONS, "rage_block")])
def _rage(state: CombatState, owner: Owner, payload: dict) -> None:
    from .cards import CardType
    from .engine import gain_player_block
    powers = state.player_powers
    card = payload.get("card")
    if card is None or card.spec.card_type != CardType.ATTACK:
        return
    if powers.rage_block <= 0:
        return
    gain_player_block(state, powers.rage_block, source="card")


# ---------------------------------------------------------------------------
# CARD_EXHAUSTED handlers
# ---------------------------------------------------------------------------

@listener(Event.CARD_EXHAUSTED, "sentinel", subscriptions=[(POWER_SUBSCRIPTIONS, "sentinel")])
def _sentinel(state: CombatState, owner: Owner, payload: dict) -> None:
    card = payload.get("card")
    if card is None:
        return
    if card.spec.card_id != "Sentinel":
        return
    gain = 2 + (1 if card.upgraded else 0)
    state.energy += gain


@listener(Event.CARD_EXHAUSTED, "dark_embrace", subscriptions=[(POWER_SUBSCRIPTIONS, "dark_embrace")])
def _dark_embrace(state: CombatState, owner: Owner, payload: dict) -> None:
    if state.player_powers.dark_embrace <= 0:
        return
    state.piles.draw_cards(state.player_powers.dark_embrace, state.rng)


@listener(Event.CARD_EXHAUSTED, "feel_no_pain", subscriptions=[(POWER_SUBSCRIPTIONS, "feel_no_pain")])
def _feel_no_pain(state: CombatState, owner: Owner, payload: dict) -> None:
    from .engine import gain_player_block
    if state.player_powers.feel_no_pain <= 0:
        return
    gain_player_block(state, state.player_powers.feel_no_pain, source="power")


# ---------------------------------------------------------------------------
# TURN_START handlers (duration ticks first, then behavioural)
# ---------------------------------------------------------------------------

# Duration ticks registered first (ordering matters)
@listener(Event.TURN_START, "tick_vulnerable", subscriptions=[(POWER_SUBSCRIPTIONS, "vulnerable")])
def _tick_vulnerable(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.vulnerable > 0:
        powers.vulnerable -= 1


@listener(Event.TURN_START, "tick_weak", subscriptions=[(POWER_SUBSCRIPTIONS, "weak")])
def _tick_weak(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.weak > 0:
        powers.weak -= 1


@listener(Event.TURN_START, "tick_frail", subscriptions=[(POWER_SUBSCRIPTIONS, "frail")])
def _tick_frail(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.frail > 0:
        powers.frail -= 1


@listener(Event.TURN_START, "clear_entangled", subscriptions=[(POWER_SUBSCRIPTIONS, "entangled")])
def _clear_entangled(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None:
        powers.entangled = False


# Behavioural listeners after ticks
@listener(Event.TURN_START, "demon_form", subscriptions=[(POWER_SUBSCRIPTIONS, "demon_form")])
def _demon_form(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.demon_form > 0:
        powers.strength += powers.demon_form


@listener(Event.TURN_START, "brutality", subscriptions=[(POWER_SUBSCRIPTIONS, "brutality")])
def _brutality(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None or powers.brutality <= 0:
        return
    # Only player has HP to lose
    if owner == "player":
        state.player_hp = max(0, state.player_hp - 1)
        state.piles.draw_cards(1, state.rng)


@listener(Event.TURN_START, "berserk", subscriptions=[(POWER_SUBSCRIPTIONS, "berserk_energy")])
def _berserk(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is not None and powers.berserk_energy > 0:
        state.energy += powers.berserk_energy


# ---------------------------------------------------------------------------
# TURN_END handlers
# ---------------------------------------------------------------------------

@listener(Event.TURN_END, "metallicize", subscriptions=[(POWER_SUBSCRIPTIONS, "metallicize")])
def _metallicize(state: CombatState, owner: Owner, payload: dict) -> None:
    from .engine import gain_player_block
    powers = _get_powers(state, owner)
    if powers is None or powers.metallicize <= 0:
        return
    if owner == "player":
        gain_player_block(state, powers.metallicize, source="power")


@listener(Event.TURN_END, "strength_loss", subscriptions=[(POWER_SUBSCRIPTIONS, "strength_loss_eot")])
def _strength_loss(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None or powers.strength_loss_eot <= 0:
        return
    powers.strength -= powers.strength_loss_eot
    powers.strength_loss_eot = 0


@listener(Event.TURN_END, "dex_loss", subscriptions=[(POWER_SUBSCRIPTIONS, "dexterity_loss_eot")])
def _dex_loss(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None or powers.dexterity_loss_eot <= 0:
        return
    powers.dexterity -= powers.dexterity_loss_eot
    powers.dexterity_loss_eot = 0


@listener(Event.TURN_END, "ritual", subscriptions=[(POWER_SUBSCRIPTIONS, "ritual")])
def _ritual(state: CombatState, owner: Owner, payload: dict) -> None:
    powers = _get_powers(state, owner)
    if powers is None:
        return
    if powers.ritual_just_applied:
        powers.ritual_just_applied = False
    elif powers.ritual > 0:
        powers.strength += powers.ritual


@listener(Event.TURN_END, "bomb_fuse_tick", subscriptions=[(POWER_SUBSCRIPTIONS, "bomb_fuses")])
def _bomb_fuse_tick(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player":
        return
    fuses = state.player_powers.bomb_fuses
    if not fuses:
        return
    from .powers import apply_damage
    remaining = []
    for turns_left, dmg in fuses:
        turns_left -= 1
        if turns_left <= 0:
            for ei, enemy in enumerate(state.enemies):
                if enemy.hp > 0 and enemy.name != "Empty":
                    nb, nhp = apply_damage(dmg, enemy.block, enemy.hp)
                    enemy.block = nb
                    enemy.hp = nhp
        else:
            remaining.append((turns_left, dmg))
    state.player_powers.bomb_fuses = remaining


@listener(Event.TURN_END, "tick_no_card_block", subscriptions=[(POWER_SUBSCRIPTIONS, "no_card_block_turns")])
def _tick_no_card_block(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner == "player" and state.player_powers.no_card_block_turns > 0:
        state.player_powers.no_card_block_turns -= 1


@listener(Event.TURN_END, "reset_panache_counter", subscriptions=[(POWER_SUBSCRIPTIONS, "panache_damage")])
def _reset_panache_counter(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner == "player":
        state.player_powers.cards_played_this_turn = 0


@listener(Event.TURN_END, "reset_strength_loss_this_turn", subscriptions=[])
def _reset_strength_loss_this_turn(state: CombatState, owner: Owner, payload: dict) -> None:
    """Restore per-turn enemy strength loss at end of enemy turn."""
    if isinstance(owner, int) and 0 <= owner < len(state.enemies):
        enemy = state.enemies[owner]
        if enemy.powers.strength_loss_this_turn > 0:
            enemy.powers.strength += enemy.powers.strength_loss_this_turn
            enemy.powers.strength_loss_this_turn = 0


@listener(Event.TURN_START, "magnetism", subscriptions=[(POWER_SUBSCRIPTIONS, "magnetism")])
def _magnetism(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or state.player_powers.magnetism <= 0:
        return
    from .card_pools import colorless_pool
    pool_cards = colorless_pool()
    if not pool_cards:
        return
    card_id = state.rng.choice(pool_cards)
    from .card import Card
    state.piles.spawn_to_hand(Card(card_id), state)
    from .events import emit as _emit
    _emit(state, Event.CARD_CREATED, "player", card=state.piles.hand[-1])


@listener(Event.TURN_START, "mayhem", subscriptions=[(POWER_SUBSCRIPTIONS, "mayhem")])
def _mayhem(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player" or state.player_powers.mayhem <= 0:
        return
    # Play the top card of the draw pile automatically
    if not state.piles.draw:
        if not state.piles.discard:
            return
        state.piles.shuffle_draw_from_discard(state.rng)
    if not state.piles.draw:
        return
    from .cards import get_spec, _apply_spec, _SPECS, CardType
    from .card import Card
    top_card = state.piles.draw.pop(0)
    top_spec = get_spec(top_card.card_id.rstrip("+"))
    if not top_spec.playable:
        state.piles.move_to_discard(top_card)
        return
    if top_spec.target == TargetType.SINGLE_ENEMY:
        alive = [e for e in state.enemies if e.hp > 0 and e.name != "Empty"]
        if alive:
            ti = state.enemies.index(alive[state.rng.randint(0, len(alive) - 1)])
        else:
            ti = 0
    else:
        ti = 0
    up = 1 if top_card.upgraded else 0
    _apply_spec(state, top_spec, ti, up)
    if top_spec.custom is not None:
        top_spec.custom(state, -1, ti, up)
    if top_spec.exhausts:
        state.piles.move_to_exhaust(top_card)
    else:
        state.piles.move_to_discard(top_card)
    from .events import Event, emit as _emit
    _emit(state, Event.CARD_PLAYED, "player", card=top_card)
    if top_spec.exhausts:
        _emit(state, Event.CARD_EXHAUSTED, "player", card=top_card)


@listener(Event.CARD_PLAYED, "panache", subscriptions=[(POWER_SUBSCRIPTIONS, "panache_damage")])
def _panache(state: CombatState, owner: Owner, payload: dict) -> None:
    if state.player_powers.panache_damage <= 0:
        return
    state.player_powers.cards_played_this_turn += 1
    if state.player_powers.cards_played_this_turn % 5 == 0:
        from .powers import calc_damage, apply_damage
        dmg = state.player_powers.panache_damage
        for ei, enemy in enumerate(state.enemies):
            if enemy.hp > 0 and enemy.name != "Empty":
                raw = calc_damage(dmg, state.player_powers, enemy.powers)
                nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
                enemy.block = nb
                enemy.hp = nhp


# ---------------------------------------------------------------------------
# CARD_CREATED handlers
# ---------------------------------------------------------------------------

@listener(Event.CARD_CREATED, "corruption_stamp_skill", subscriptions=[])
def _corruption_stamp_skill(state: CombatState, owner: Owner, payload: dict) -> None:
    """Stamp newly created skills with Corruption's effects (cost=0, exhausts)."""
    from .cards import CardType
    if not state.player_powers.corruption:
        return
    card = payload.get("card")
    if card is None:
        return
    # Corruption only affects skills
    if card.spec.card_type != CardType.SKILL:
        return
    # X-cost skills keep spending all energy; only apply exhaust + flag
    if not card.spec.x_cost:
        card.cost_override = 0
        card.cost_override_duration = "combat"
    card.exhausts_override = True
    card.corrupted = True


# ---------------------------------------------------------------------------
# DEBUFF_APPLIED handlers
# ---------------------------------------------------------------------------

@listener(Event.DEBUFF_APPLIED, "sadistic_nature", subscriptions=[(POWER_SUBSCRIPTIONS, "sadistic_nature")])
def _sadistic_nature(state: CombatState, owner: Owner, payload: dict) -> None:
    if state.player_powers.sadistic_nature <= 0:
        return
    if not isinstance(owner, int):
        return
    from .powers import calc_damage, apply_damage
    enemy = state.enemies[owner]
    dmg = calc_damage(state.player_powers.sadistic_nature, state.player_powers, enemy.powers)
    nb, nhp = apply_damage(dmg, enemy.block, enemy.hp)
    enemy.block = nb
    enemy.hp = nhp


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
