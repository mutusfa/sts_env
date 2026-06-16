"""Run-layer relic state persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..combat.relic_state import default_relic_data

if TYPE_CHECKING:
    from ..combat.state import CombatState
    from .character import Character


def init_relic_on_obtain(relic_id: str, character: Character) -> None:
    if relic_id not in character.relic_data:
        character.relic_data[relic_id] = default_relic_data(relic_id)


def disable_relic_run(relic_id: str, character: Character) -> None:
    character.relic_data[relic_id] = 0


def sync_relic_data_to_character(character: Character, state: CombatState) -> None:
    character.relic_state = dict(state.relic_state)
    character.relic_data = dict(state.relic_data)
