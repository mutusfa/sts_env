"""Potion-triggered event listeners.

Potions that have passive combat effects subscribe at Combat.reset based
on ``state.potions``.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .events import Event, register_listener, unsubscribe

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# Fairy in a Bottle: auto-revive at 30% max HP on lethal damage
# ---------------------------------------------------------------------------

def _fairy(state: CombatState, owner: Owner, payload: dict) -> None:
    if owner != "player":
        return
    if state.player_hp > 0:
        return
    # Find and consume the first FairyInABottle
    for i, potion_id in enumerate(state.potions):
        if potion_id == "FairyInABottle":
            revive_hp = max(1, math.floor(state.player_max_hp * 0.3))
            state.player_hp = revive_hp
            state.potions.pop(i)
            # Unsubscribe one instance
            unsubscribe(state, Event.HP_LOSS, "fairy", "player")
            return


register_listener(Event.HP_LOSS, "fairy", _fairy)


# ---------------------------------------------------------------------------
# Subscription table
# ---------------------------------------------------------------------------

POTION_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {
    "FairyInABottle": [(Event.HP_LOSS, "fairy")],
}
