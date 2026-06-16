"""Player healing with event emission."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .events import Event, emit

if TYPE_CHECKING:
    from .state import CombatState


def heal_player(state: CombatState, amount: int) -> None:
    if amount <= 0:
        return
    hp_before = state.player_hp
    state.player_hp = min(state.player_max_hp, state.player_hp + amount)
    if state.player_hp > hp_before:
        emit(state, Event.HP_GAIN, "player", hp_before=hp_before)
