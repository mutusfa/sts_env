"""Seeded encounter factories for Act 1 (ascension 0).

Each factory takes ``(seed, character)`` and returns a configured
:class:`Combat`.  ``character`` is a :class:`PlayerState` carrying the
player's deck, HP, relics, potions, and gold for this encounter.

Composition RNG (for encounters that pick enemies randomly) is seeded
independently of the combat RNG so that:
- ``Combat.reset()`` produces the same sequence regardless of which factory
  built the object.
- ``Combat.clone()`` remains correct — the enemy list is fixed in ``__init__``.

The composition seed is derived as ``seed ^ _COMP_SEED_SALT``.
"""

from __future__ import annotations

from .engine import Combat, IRONCLAD_STARTER
from .player_state import PlayerState
from .rng import RNG

_COMP_SEED_SALT = 0xC0FFEE


# ---------------------------------------------------------------------------
# Single-enemy encounters
# ---------------------------------------------------------------------------

def cultist(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    return Combat(character, ["Cultist"], seed, is_elite)


def jaw_worm(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    return Combat(character, ["JawWorm"], seed, is_elite)


def acid_slime_m(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    return Combat(character, ["AcidSlimeM"], seed, is_elite)


def spike_slime_m(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    return Combat(character, ["SpikeSlimeM"], seed, is_elite)


def acid_slime_l(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """AcidSlimeL with a pre-allocated Empty slot for the split."""
    return Combat(character, ["AcidSlimeL", "Empty"], seed, is_elite)


def spike_slime_l(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """SpikeSlimeL with a pre-allocated Empty slot for the split."""
    return Combat(character, ["SpikeSlimeL", "Empty"], seed, is_elite)


_LARGE_SLIME_TYPES = ["AcidSlimeL", "SpikeSlimeL"]


def large_slime(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """A randomly-selected large slime (50/50 AcidSlimeL or SpikeSlimeL) with Empty slot."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    chosen = _LARGE_SLIME_TYPES[comp_rng.randint(0, 1)]
    return Combat(character, [chosen, "Empty"], seed, is_elite)


# ---------------------------------------------------------------------------
# Small Slimes — SpikeSlimeS + AcidSlimeS
# ---------------------------------------------------------------------------

def small_slimes(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """One small + one medium slime: (SpikeSlimeS+AcidSlimeM) or (AcidSlimeS+SpikeSlimeM).

    Source: MonsterGroup.cpp SMALL_SLIMES case — randomBoolean picks the pair.
    """
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    if comp_rng.random() < 0.5:
        enemies = ["SpikeSlimeS", "AcidSlimeM"]
    else:
        enemies = ["AcidSlimeS", "SpikeSlimeM"]
    return Combat(character, enemies, seed, is_elite)


# ---------------------------------------------------------------------------
# Two Louses — seeded mix of RedLouse / GreenLouse
# ---------------------------------------------------------------------------

_LOUSE_TYPES = ["RedLouse", "GreenLouse"]


def _pick_louse(rng: RNG) -> str:
    return _LOUSE_TYPES[rng.randint(0, 1)]


def two_louses(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Two louses: each independently 50% RedLouse / 50% GreenLouse."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    enemies = [_pick_louse(comp_rng), _pick_louse(comp_rng)]
    return Combat(character, enemies, seed, is_elite)


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


def gremlin_gang(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
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
    return Combat(character, enemies, seed, is_elite)


# ---------------------------------------------------------------------------
# Single-enemy: Blue Slaver, Red Slaver, Looter
# ---------------------------------------------------------------------------

def blue_slaver(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    return Combat(character, ["BlueSlaver"], seed, is_elite)


def red_slaver(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    return Combat(character, ["RedSlaver"], seed, is_elite)


def looter(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    return Combat(character, ["Looter"], seed, is_elite)


# ---------------------------------------------------------------------------
# Two Fungi Beasts
# ---------------------------------------------------------------------------

def two_fungi_beasts(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Two Fungi Beasts (both start with SporeCloud 2)."""
    return Combat(character, ["FungiBeast", "FungiBeast"], seed, is_elite)


def three_fungi_beasts_event(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Mushrooms event: three Fungi Beasts."""
    return Combat(character, ["FungiBeast", "FungiBeast", "FungiBeast"], seed, is_elite)


def lagavulin_event(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Dead Adventurer event: Lagavulin starts awake (no sleep, no metallicize).

    Much harder than the normal elite Lagavulin which starts sleeping for 3 turns.
    """
    return Combat(character, ["Lagavulin_awake"], seed, is_elite)


# ---------------------------------------------------------------------------
# Three Louses — each independently 50/50 Red/Green
# ---------------------------------------------------------------------------

def three_louse(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Three louses, each independently 50/50 RedLouse / GreenLouse."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    enemies = [_pick_louse(comp_rng), _pick_louse(comp_rng), _pick_louse(comp_rng)]
    return Combat(character, enemies, seed, is_elite)


# ---------------------------------------------------------------------------
# Lots of Slimes — Fisher-Yates shuffle of [SpikeSlimeS×3, AcidSlimeS×2]
# ---------------------------------------------------------------------------
# Source: MonsterGroup.cpp LOTS_OF_SLIMES case

def lots_of_slimes(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Five slimes drawn from [SpikeSlimeS×3, AcidSlimeS×2] in random order."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    pool = ["SpikeSlimeS", "SpikeSlimeS", "SpikeSlimeS", "AcidSlimeS", "AcidSlimeS"]
    enemies: list[str] = []
    for i in range(4, -1, -1):
        idx = comp_rng.randint(0, i)
        enemies.append(pool[idx])
        pool.pop(idx)
    return Combat(character, enemies, seed, is_elite)


# ---------------------------------------------------------------------------
# Exordium Thugs / Exordium Wildlife — composition helpers
# ---------------------------------------------------------------------------
# Source: MonsterGroup.cpp createWeakWildlife / createStrongHumanoid / createStrongWildlife
#
# createWeakWildlife:  1-of [Louse(50/50R/G), SpikeSlimeM, AcidSlimeM]  (random(2))
# createStrongHumanoid: 1-of [Cultist, Slaver(50/50R/G), Looter]        (random(2))
# createStrongWildlife: 1-of [FungiBeast, JawWorm]                       (random(1))
#
# RNG call order mirrors MonsterGroup.cpp: any getLouse/getSlaver call comes
# BEFORE the uniform index pick, because temp[] is constructed left-to-right.


def _pick_slaver(rng: RNG) -> str:
    return "RedSlaver" if rng.randint(0, 1) == 0 else "BlueSlaver"


def _weak_wildlife(comp_rng: RNG) -> str:
    """Pick one weak-wildlife enemy: Louse(50/50), SpikeSlimeM, or AcidSlimeM."""
    louse = _pick_louse(comp_rng)           # consume RNG for getLouse before index roll
    idx = comp_rng.randint(0, 2)
    if idx == 0:
        return louse
    elif idx == 1:
        return "SpikeSlimeM"
    else:
        return "AcidSlimeM"


def _strong_humanoid(comp_rng: RNG) -> str:
    """Pick one strong-humanoid enemy: Cultist, Slaver(50/50), or Looter."""
    slaver = _pick_slaver(comp_rng)         # consume RNG for getSlaver before index roll
    idx = comp_rng.randint(0, 2)
    if idx == 0:
        return "Cultist"
    elif idx == 1:
        return slaver
    else:
        return "Looter"


def _strong_wildlife(comp_rng: RNG) -> str:
    """Pick one strong-wildlife enemy: FungiBeast or JawWorm."""
    return "FungiBeast" if comp_rng.randint(0, 1) == 0 else "JawWorm"


def exordium_thugs(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """One weak wildlife + one strong humanoid.

    Source: MonsterGroup.cpp EXORDIUM_THUGS (createWeakWildlife + createStrongHumanoid).
    """
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    ww = _weak_wildlife(comp_rng)
    sh = _strong_humanoid(comp_rng)
    return Combat(character, [ww, sh], seed, is_elite)


def exordium_wildlife(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """One strong wildlife + one weak wildlife.

    Source: MonsterGroup.cpp EXORDIUM_WILDLIFE (createStrongWildlife + createWeakWildlife).
    """
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    sw = _strong_wildlife(comp_rng)
    ww = _weak_wildlife(comp_rng)
    return Combat(character, [sw, ww], seed, is_elite)


# ---------------------------------------------------------------------------
# Elites — Act 1
# ---------------------------------------------------------------------------

def gremlin_nob(seed: int, character: PlayerState, *, is_elite: bool = True) -> Combat:
    return Combat(character, ["GremlinNob"], seed, is_elite)


def lagavulin(seed: int, character: PlayerState, *, is_elite: bool = True) -> Combat:
    return Combat(character, ["Lagavulin"], seed, is_elite)


def three_sentries(seed: int, character: PlayerState, *, is_elite: bool = True) -> Combat:
    return Combat(character, ["Sentry", "Sentry", "Sentry"], seed, is_elite)


# ---------------------------------------------------------------------------
# Bosses — Act 1
# ---------------------------------------------------------------------------

def slime_boss(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Slime Boss with a pre-allocated Empty slot for the split."""
    return Combat(character, ["SlimeBoss", "Empty"], seed, is_elite)


def guardian(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Guardian boss: 240 HP, cycles ChargingUp / FierceStrike / VentSteam / Whirlwind."""
    return Combat(character, ["Guardian"], seed, is_elite)


def hexaghost(seed: int, character: PlayerState, *, is_elite: bool = False) -> Combat:
    """Hexaghost boss: 250 HP, 6-turn cycle (Activate/Divider/Sear/Inflate/Sear/Inferno)."""
    return Combat(character, ["Hexaghost"], seed, is_elite)


# ---------------------------------------------------------------------------
# Act 1 pool-selection helpers
# ---------------------------------------------------------------------------
# Source: MonsterEncounters.h MonsterEncounterPool namespace
#
# weakEnemies[0]   = [CULTIST, JAW_WORM, TWO_LOUSE, SMALL_SLIMES]  (uniform 1/4)
# strongEnemies[0] = [GREMLIN_GANG, LOTS_OF_SLIMES, RED_SLAVER,
#                     EXORDIUM_THUGS, EXORDIUM_WILDLIFE, BLUE_SLAVER,
#                     LOOTER, LARGE_SLIME, THREE_LOUSE, TWO_FUNGI_BEASTS]
# strongWeights[0] = [1, 1, 1, 1.5, 1.5, 2, 2, 2, 2, 2] / 16

_ACT1_POOL_SALT = 0xDECADE

_ACT1_WEAK_FACTORIES = [cultist, jaw_worm, two_louses, small_slimes]

_ACT1_STRONG_POOL: list[tuple] = [
    (gremlin_gang,      1.0),
    (lots_of_slimes,    1.0),
    (red_slaver,        1.0),
    (exordium_thugs,    1.5),
    (exordium_wildlife, 1.5),
    (blue_slaver,       2.0),
    (looter,            2.0),
    (large_slime,       2.0),
    (three_louse,       2.0),
    (two_fungi_beasts,  2.0),
]
_ACT1_STRONG_TOTAL = sum(w for _, w in _ACT1_STRONG_POOL)

_ACT1_ELITE_POOL: list[tuple] = [
    (gremlin_nob,    "Gremlin Nob"),
    (lagavulin,      "Lagavulin"),
    (three_sentries, "Three Sentries"),
]


def act1_weak_encounter(seed: int, character: PlayerState) -> Combat:
    """Pick uniformly from the Act 1 weak (starting) encounter pool.

    Pool: Cultist, JawWorm, TwoLouses, SmallSlimes.
    Source: MonsterEncounterPool::weakEnemies[0].
    """
    pool_rng = RNG(seed ^ _ACT1_POOL_SALT)
    factory = _ACT1_WEAK_FACTORIES[pool_rng.randint(0, 3)]
    return factory(seed, character)


def act1_strong_encounter(seed: int, character: PlayerState) -> Combat:
    """Pick from the Act 1 strong encounter pool using C++ weights.

    Weights: GremlinGang/LotsOfSlimes/RedSlaver 1×, ExordiumThugs/Wildlife 1.5×,
    BlueSlave/Looter/LargeSlime/ThreeLouse/TwoFungiBeasts 2× (total 16).
    Source: MonsterEncounterPool::strongEnemies[0] / strongWeights[0].
    """
    pool_rng = RNG(seed ^ _ACT1_POOL_SALT)
    r = pool_rng.random() * _ACT1_STRONG_TOTAL
    cumulative = 0.0
    for factory, weight in _ACT1_STRONG_POOL:
        cumulative += weight
        if r < cumulative:
            return factory(seed, character)
    return _ACT1_STRONG_POOL[-1][0](seed, character)
