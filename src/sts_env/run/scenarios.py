"""Scenario definitions for multi-combat runs.

A scenario defines the sequence of encounters a player faces across floors.

Scenario 3 (v1): 3 easy hallways + 1 hard hallway + 1 elite = 5 floors.
"""

from __future__ import annotations

from ..combat.encounters import (
    act1_weak_encounter,
    act1_strong_encounter,
    _ACT1_WEAK_FACTORIES,
    _ACT1_STRONG_POOL,
)
from ..combat.rng import RNG

# Elite encounter factories
# Each returns (enemy_name_list, encounter_label) for constructing Combat

_ELITE_POOLS = [
    ("GremlinNob", "Gremlin Nob"),
    ("Lagavulin", "Lagavulin"),
    (["Sentry", "Sentry", "Sentry"], "Three Sentries"),
]


def _pick_elite(rng: RNG) -> tuple[str | list[str], str]:
    """Pick a random elite encounter."""
    return _ELITE_POOLS[rng.randint(0, len(_ELITE_POOLS) - 1)]


def scenario3_encounters(seed: int) -> list[tuple[str, str]]:
    """Return the encounter list for Scenario 3.

    Returns a list of (encounter_type, encounter_id) tuples where:
      - encounter_type: "easy" | "hard" | "elite"
      - encounter_id: a string identifier for the encounter

    Composition (5 floors):
      - 3 easy hallway fights (from Act 1 weak pool)
      - 1 hard hallway fight (from Act 1 strong pool)
      - 1 elite fight (Gremlin Nob / Lagavulin / 3 Sentries)

    The order is: easy, easy, hard, easy, elite (mirroring typical StS pacing).
    """
    rng = RNG(seed ^ 0x5C3A010)  # separate seed for scenario composition

    # Pick 3 weak encounters
    easy_encounters = []
    weak_pool = list(_ACT1_WEAK_FACTORIES)
    for _ in range(3):
        factory = weak_pool[rng.randint(0, len(weak_pool) - 1)]
        easy_encounters.append(factory.__name__)

    # Pick 1 strong encounter (use weighted selection)
    weights = [w for _, w in _ACT1_STRONG_POOL]
    total_w = sum(weights)
    roll = rng.random() * total_w
    cumulative = 0.0
    hard_encounter = _ACT1_STRONG_POOL[0][0].__name__
    for (factory, weight) in _ACT1_STRONG_POOL:
        cumulative += weight
        if roll < cumulative:
            hard_encounter = factory.__name__
            break

    # Pick 1 elite
    _, elite_name = _pick_elite(rng)

    return [
        ("easy", easy_encounters[0]),
        ("easy", easy_encounters[1]),
        ("hard", hard_encounter),
        ("easy", easy_encounters[2]),
        ("elite", elite_name),
    ]
