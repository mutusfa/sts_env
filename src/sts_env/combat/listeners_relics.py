"""Relic-triggered event listeners.

Relics subscribe at Combat.reset based on ``state.relics``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .events import Event, register_listener
from .powers import Powers

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# RedSkull: +3 Strength while HP <= 50% of max
# ---------------------------------------------------------------------------

def _red_skull_init(state: CombatState, owner: Owner, payload: dict) -> None:
    """At COMBAT_START, apply RedSkull if player starts at or below 50% HP."""
    if "RedSkull" not in state.relics:
        return
    if state.player_hp <= state.player_max_hp // 2:
        state.player_powers.strength += 3
        state.player_powers._red_skull_active = True


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


register_listener(Event.COMBAT_START, "red_skull_init", _red_skull_init)
register_listener(Event.HP_LOSS, "red_skull", _red_skull)


# ---------------------------------------------------------------------------
# Subscription table
# ---------------------------------------------------------------------------

RELIC_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {
    "RedSkull": [
        (Event.COMBAT_START, "red_skull_init"),
        (Event.HP_LOSS, "red_skull"),
    ],
}
