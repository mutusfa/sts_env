"""Seeded encounter factories for Act 1 (ascension 0).

Each factory is a plain function returning a configured :class:`Combat`.
The ``deck`` and ``player_hp`` parameters are keyword-only and default to
the Ironclad starter deck and 80 HP respectively.

Composition RNG (for encounters that pick enemies randomly) is seeded
independently of the combat RNG so that:
- ``Combat.reset()`` produces the same sequence regardless of which factory
  built the object.
- ``Combat.clone()`` remains correct — the enemy list is fixed in ``__init__``.

The composition seed is derived as ``seed ^ _COMP_SEED_SALT``.
"""

from __future__ import annotations

from .engine import Combat, IRONCLAD_STARTER
from .rng import RNG

_COMP_SEED_SALT = 0xC0FFEE


# ---------------------------------------------------------------------------
# Single-enemy encounters (replaces Combat.ironclad_starter and friends)
# ---------------------------------------------------------------------------

def cultist(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    return Combat(deck, ["Cultist"], seed, player_hp)


def jaw_worm(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    return Combat(deck, ["JawWorm"], seed, player_hp)


def acid_slime_m(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    return Combat(deck, ["AcidSlimeM"], seed, player_hp)


# ---------------------------------------------------------------------------
# Small Slimes — SpikeSlimeS + AcidSlimeS
# ---------------------------------------------------------------------------

def small_slimes(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Two small slimes: one SpikeSlimeS and one AcidSlimeS."""
    return Combat(deck, ["SpikeSlimeS", "AcidSlimeS"], seed, player_hp)


# ---------------------------------------------------------------------------
# Two Louses — seeded mix of RedLouse / GreenLouse
# ---------------------------------------------------------------------------

_LOUSE_TYPES = ["RedLouse", "GreenLouse"]


def _pick_louse(rng: RNG) -> str:
    return _LOUSE_TYPES[rng.randint(0, 1)]


def two_louses(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Two louses: each independently 50% RedLouse / 50% GreenLouse."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    enemies = [_pick_louse(comp_rng), _pick_louse(comp_rng)]
    return Combat(deck, enemies, seed, player_hp)


# ---------------------------------------------------------------------------
# Gremlin Gang — 4 picked without replacement from the STS pool
# ---------------------------------------------------------------------------
# Pool: 2×Mad, 2×Sneaky, 2×Fat, 1×Shield, 1×Wizard
# Source: MonsterGroup.cpp lines 100-124

_GREMLIN_POOL = [
    "MadGremlin", "MadGremlin",
    "SneakyGremlin", "SneakyGremlin",
    "FatGremlin", "FatGremlin",
    "ShieldGremlin",
    "GremlinWizard",
]


def gremlin_gang(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Four gremlins drawn without replacement from the STS pool."""
    pool = list(_GREMLIN_POOL)
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    enemies: list[str] = []
    last_idx = len(pool) - 1
    for _ in range(4):
        idx = comp_rng.randint(0, last_idx)
        enemies.append(pool[idx])
        pool.pop(idx)
        last_idx -= 1
    return Combat(deck, enemies, seed, player_hp)
