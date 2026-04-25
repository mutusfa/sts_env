"""Relic system for the Slay the Spire environment.

Simple registry pattern (mirrors cards.py and potions.py).

Each relic has:
  - A RelicSpec (static metadata: relic_id).
  - Handler functions called at specific hooks.

Currently implemented:
  - BurningBlood: heal 6 HP after winning combat (Ironclad starter relic).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .state import RunState


@dataclass(frozen=True)
class RelicSpec:
    relic_id: str


# Hook: called after winning a combat (before next floor starts)
CombatEndHook = Callable[["RunState"], None]

_SPECS: dict[str, RelicSpec] = {}
_COMBAT_END_HOOKS: dict[str, CombatEndHook] = {}


def _register(spec: RelicSpec, *, on_combat_end: CombatEndHook | None = None) -> None:
    _SPECS[spec.relic_id] = spec
    if on_combat_end is not None:
        _COMBAT_END_HOOKS[spec.relic_id] = on_combat_end


def get_spec(relic_id: str) -> RelicSpec:
    return _SPECS[relic_id]


def on_combat_end(run_state: "RunState") -> None:
    """Call on_combat_end hooks for all relics the player has."""
    for relic_id in run_state.relics:
        hook = _COMBAT_END_HOOKS.get(relic_id)
        if hook is not None:
            hook(run_state)


# ---------------------------------------------------------------------------
# Relic definitions
# ---------------------------------------------------------------------------

# BurningBlood: Ironclad starter relic. Heal 6 HP after winning combat.
def _burning_blood_on_combat_end(run_state: "RunState") -> None:
    run_state.heal(6)


_register(
    RelicSpec("BurningBlood"),
    on_combat_end=_burning_blood_on_combat_end,
)
