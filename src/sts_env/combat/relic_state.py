"""Relic active/disable helpers shared by combat and run layers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CombatState

_DEFAULT_DATA_ON_OBTAIN: dict[str, int] = {
    "MawBank": 1,
    "Omamori": 2,
    "LizardTail": 1,
    "TinyChest": 0,
    "Matryoshka": 2,
    "NeowsLament": 3,
}


def default_relic_data(relic_id: str) -> int:
    return _DEFAULT_DATA_ON_OBTAIN.get(relic_id, 1)


def relic_active(
    relic_id: str,
    *,
    owned: list[str] | frozenset[str],
    relic_data: dict[str, int],
    combat_disabled: set[str] | None = None,
) -> bool:
    if relic_id not in owned:
        return False
    if relic_data.get(relic_id, default_relic_data(relic_id)) == 0:
        return False
    if combat_disabled is not None and relic_id in combat_disabled:
        return False
    return True


def disable_relic_combat(relic_id: str, state: CombatState) -> None:
    state.relic_combat_disabled.add(relic_id)


def clear_combat_disabled(state: CombatState) -> None:
    state.relic_combat_disabled.clear()
