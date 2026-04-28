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

# ---------------------------------------------------------------------------
# Boss relics (registered as specs; combat-internal effects TBD)
# ---------------------------------------------------------------------------

# RedSkull: +3 Strength while HP <= 50% (combat-internal, needs engine hook)
_register(RelicSpec("RedSkull"))

# CentennialPuzzle: draw 3 cards first time you lose HP each combat (combat-internal)
_register(RelicSpec("CentennialPuzzle"))

# JuzuBracelet: normal enemies no longer attack (combat-internal — simplifies encounters)
_register(RelicSpec("JuzuBracelet"))

# Orichalcum: if you end turn with 0 block, gain 6 block (combat-internal)
_register(RelicSpec("Orichalcum"))

# CeramicFish: gain 9 gold whenever you add a card to your deck
def _ceramic_fish_on_card_add(run_state: "RunState") -> None:
    run_state.gold += 9

# Register CeramicFish with combat-end hook as a proxy for card-add events
# (simplified: the runner calls this explicitly after card rewards)
_register(RelicSpec("CeramicFish"))

# TinyHouse: gain 50 gold, +3 max HP, gain 5 cards (simplified: just gold + HP)
_register(RelicSpec("TinyHouse"))

# BustedCrown: +1 energy per turn, but card rewards offer 1 card instead of 3 (combat-internal + run-layer)
_register(RelicSpec("BustedCrown"))

# CoffeeDripper: can't rest at rest sites (affects rest site logic)
_register(RelicSpec("CoffeeDripper"))

# FusionHammer: can't upgrade cards at rest sites (affects rest site logic)
_register(RelicSpec("FusionHammer"))

# RingOfSerpents: draw 1 additional card each turn (combat-internal)
_register(RelicSpec("RingOfSerpents"))

# Anchor: gain 10 block at start of combat (combat-internal)
_register(RelicSpec("Anchor"))

# BagOfMarbles: apply 1 Vulnerable to all enemies at start of combat (combat-internal)
_register(RelicSpec("BagOfMarbles"))

# Lantern: gain 1 energy at start of combat (combat-internal)
_register(RelicSpec("Lantern"))

# Vajra: gain 1 strength at start of combat (combat-internal)
_register(RelicSpec("Vajra"))

# PreservedInsect: reduce enemy HP by 25% for elite encounters (combat-internal)
_register(RelicSpec("PreservedInsect"))

# ToyOrnithopter: heal 5 HP when a potion is used (combat-internal)
_register(RelicSpec("ToyOrnithopter"))


# ---------------------------------------------------------------------------
# Helper: check if a relic restricts rest site options
# ---------------------------------------------------------------------------

def can_rest(relics: list[str]) -> bool:
    """Return False if CoffeeDripper prevents resting."""
    return "CoffeeDripper" not in relics


def can_upgrade(relics: list[str]) -> bool:
    """Return False if FusionHammer prevents upgrading."""
    return "FusionHammer" not in relics
