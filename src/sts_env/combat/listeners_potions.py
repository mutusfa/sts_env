"""Potion-triggered event listeners.

Potions that have passive combat effects subscribe during :class:`Combat`
construction based on ``state.potions``.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .events import Event, listener, unsubscribe

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# Subscription table
# ---------------------------------------------------------------------------

POTION_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {}


# ---------------------------------------------------------------------------
# Fairy in a Bottle: auto-revive at 30% max HP on lethal damage
# ---------------------------------------------------------------------------

@listener(Event.HP_LOSS, "fairy", subscriptions=[(POTION_SUBSCRIPTIONS, "FairyPotion")])
def _fairy(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player":
        return
    if state.player_hp > 0:
        return
    # Find and consume the first FairyPotion
    for i, potion_id in enumerate(state.potions):
        if potion_id == "FairyPotion":
            revive_hp = max(1, math.floor(
                state.player_max_hp * (0.6 if "SacredBark" in state.relics else 0.3)
            ))
            state.player_hp = revive_hp
            state.potions.pop(i)
            # Unsubscribe one instance
            unsubscribe(state, Event.HP_LOSS, "fairy", "player")
            return

