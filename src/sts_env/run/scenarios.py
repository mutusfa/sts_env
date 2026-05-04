"""Scenario definitions for multi-combat runs.

A scenario defines the sequence of encounters a player faces across floors.

Scenario 3 (v1): 3 easy hallways + 1 hard hallway + 1 elite = 5 floors.
Act 1 scenario: 3 easy + 2 hard + 2 elite + 1 boss = 8 floors.
"""

from __future__ import annotations

from ..combat.rng import RNG
from .encounter_queue import (
    WEAK_POOL,
    STRONG_POOL,
    STRONG_WEIGHTS,
    ELITE_POOL,
    weighted_pick,
)


def _pick_elite(rng: RNG) -> str:
    """Pick a random elite encounter label."""
    return ELITE_POOL[rng.randint(0, len(ELITE_POOL) - 1)]


def _pick_easy(rng: RNG) -> str:
    """Pick a random easy encounter from the weak pool (uniform)."""
    return WEAK_POOL[rng.randint(0, len(WEAK_POOL) - 1)]


def _pick_hard(rng: RNG) -> str:
    """Pick a random hard encounter from the strong pool (weighted)."""
    return weighted_pick(rng, STRONG_POOL, STRONG_WEIGHTS)


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

    easy_encounters = [_pick_easy(rng) for _ in range(3)]
    hard_encounter = _pick_hard(rng)
    elite_name = _pick_elite(rng)

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
