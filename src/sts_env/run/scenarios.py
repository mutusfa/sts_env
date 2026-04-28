"""Scenario definitions for multi-combat runs.

A scenario defines the sequence of encounters a player faces across floors.

Scenario 3 (v1): 3 easy hallways + 1 hard hallway + 1 elite = 5 floors.
Act 1 scenario: 3 easy + 2 hard + 2 elite + 1 boss = 8 floors.
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

# Boss encounter pool is now managed by EncounterQueue (encounter_queue.py)


def _pick_elite(rng: RNG) -> tuple[str | list[str], str]:
    """Pick a random elite encounter."""
    return _ELITE_POOLS[rng.randint(0, len(_ELITE_POOLS) - 1)]


def _pick_easy(rng: RNG, weak_pool: list) -> str:
    """Pick a random easy encounter from the weak pool."""
    factory = weak_pool[rng.randint(0, len(weak_pool) - 1)]
    return factory.__name__


def _pick_hard(rng: RNG) -> str:
    """Pick a random hard encounter from the strong pool (weighted)."""
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
    return hard_encounter


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

    weak_pool = list(_ACT1_WEAK_FACTORIES)

    easy_encounters = [_pick_easy(rng, weak_pool) for _ in range(3)]
    hard_encounter = _pick_hard(rng)
    _, elite_name = _pick_elite(rng)

    return [
        ("easy", easy_encounters[0]),
        ("easy", easy_encounters[1]),
        ("hard", hard_encounter),
        ("easy", easy_encounters[2]),
        ("elite", elite_name),
    ]


def act1_encounters(seed: int) -> list[tuple[str, str]]:
    """Return the encounter list for a full Act 1 scenario.

    Returns a list of (encounter_type, encounter_id) tuples where:
      - encounter_type: "easy" | "hard" | "elite" | "boss"
      - encounter_id: a string identifier for the encounter

    Uses a pre-generated EncounterQueue for faithful encounter ordering:
    first 3 hallway fights are weak (easy), subsequent ones are strong (hard).
    Elites are consumed from a separate queue.

    Composition (8 floors):
      - 3 easy hallway fights (from the front of the monster queue)
      - 2 hard hallway fights (further in the monster queue)
      - 2 elite fights (from the elite queue)
      - 1 boss fight (pre-selected)

    Order: easy, easy, hard, elite, easy, hard, elite, boss.
    This mirrors typical StS Act 1 pacing.
    """
    from .encounter_queue import EncounterQueue
    rng = RNG(seed ^ 0xA7C1B020)  # separate seed for act1 composition
    queue = EncounterQueue(rng)

    # Consume encounters from the queue in a typical StS pacing order.
    # The first 3 from the monster queue are weak, everything after is strong.
    easy_encounters = [queue.next_monster() for _ in range(3)]
    hard_encounters = [queue.next_monster() for _ in range(2)]
    elite_encounters = [queue.next_elite() for _ in range(2)]
    boss_encounter = queue.get_boss()

    return [
        ("easy", easy_encounters[0]),
        ("easy", easy_encounters[1]),
        ("hard", hard_encounters[0]),
        ("elite", elite_encounters[0]),
        ("easy", easy_encounters[2]),
        ("hard", hard_encounters[1]),
        ("elite", elite_encounters[1]),
        ("boss", boss_encounter),
    ]
