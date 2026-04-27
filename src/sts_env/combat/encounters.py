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


def spike_slime_m(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    return Combat(deck, ["SpikeSlimeM"], seed, player_hp)


def acid_slime_l(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """AcidSlimeL with a pre-allocated Empty slot for the split."""
    return Combat(deck, ["AcidSlimeL", "Empty"], seed, player_hp)


def spike_slime_l(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """SpikeSlimeL with a pre-allocated Empty slot for the split."""
    return Combat(deck, ["SpikeSlimeL", "Empty"], seed, player_hp)


_LARGE_SLIME_TYPES = ["AcidSlimeL", "SpikeSlimeL"]


def large_slime(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """A randomly-selected large slime (50/50 AcidSlimeL or SpikeSlimeL) with Empty slot."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    chosen = _LARGE_SLIME_TYPES[comp_rng.randint(0, 1)]
    return Combat(deck, [chosen, "Empty"], seed, player_hp)


# ---------------------------------------------------------------------------
# Small Slimes — SpikeSlimeS + AcidSlimeS
# ---------------------------------------------------------------------------

def small_slimes(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """One small + one medium slime: (SpikeSlimeS+AcidSlimeM) or (AcidSlimeS+SpikeSlimeM).

    Source: MonsterGroup.cpp SMALL_SLIMES case — randomBoolean picks the pair.
    """
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    if comp_rng.random() < 0.5:
        enemies = ["SpikeSlimeS", "AcidSlimeM"]
    else:
        enemies = ["AcidSlimeS", "SpikeSlimeM"]
    return Combat(deck, enemies, seed, player_hp)


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


# ---------------------------------------------------------------------------
# Single-enemy: Blue Slaver, Red Slaver, Looter
# ---------------------------------------------------------------------------

def blue_slaver(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    return Combat(deck, ["BlueSlaver"], seed, player_hp)


def red_slaver(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    return Combat(deck, ["RedSlaver"], seed, player_hp)


def looter(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    return Combat(deck, ["Looter"], seed, player_hp)


# ---------------------------------------------------------------------------
# Two Fungi Beasts
# ---------------------------------------------------------------------------

def two_fungi_beasts(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Two Fungi Beasts (both start with SporeCloud 2)."""
    return Combat(deck, ["FungiBeast", "FungiBeast"], seed, player_hp)


# ---------------------------------------------------------------------------
# Three Louses — each independently 50/50 Red/Green
# ---------------------------------------------------------------------------

def three_louse(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Three louses, each independently 50/50 RedLouse / GreenLouse."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    enemies = [_pick_louse(comp_rng), _pick_louse(comp_rng), _pick_louse(comp_rng)]
    return Combat(deck, enemies, seed, player_hp)


# ---------------------------------------------------------------------------
# Lots of Slimes — Fisher-Yates shuffle of [SpikeSlimeS×3, AcidSlimeS×2]
# ---------------------------------------------------------------------------
# Source: MonsterGroup.cpp LOTS_OF_SLIMES case

def lots_of_slimes(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Five slimes drawn from [SpikeSlimeS×3, AcidSlimeS×2] in random order."""
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    pool = ["SpikeSlimeS", "SpikeSlimeS", "SpikeSlimeS", "AcidSlimeS", "AcidSlimeS"]
    enemies: list[str] = []
    for i in range(4, -1, -1):
        idx = comp_rng.randint(0, i)
        enemies.append(pool[idx])
        pool.pop(idx)
    return Combat(deck, enemies, seed, player_hp)


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


def exordium_thugs(
    seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80
) -> Combat:
    """One weak wildlife + one strong humanoid.

    Source: MonsterGroup.cpp EXORDIUM_THUGS (createWeakWildlife + createStrongHumanoid).
    """
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    ww = _weak_wildlife(comp_rng)
    sh = _strong_humanoid(comp_rng)
    return Combat(deck, [ww, sh], seed, player_hp)


def exordium_wildlife(
    seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80
) -> Combat:
    """One strong wildlife + one weak wildlife.

    Source: MonsterGroup.cpp EXORDIUM_WILDLIFE (createStrongWildlife + createWeakWildlife).
    """
    comp_rng = RNG(seed ^ _COMP_SEED_SALT)
    sw = _strong_wildlife(comp_rng)
    ww = _weak_wildlife(comp_rng)
    return Combat(deck, [sw, ww], seed, player_hp)


# ---------------------------------------------------------------------------
# Slime Boss — Act 1 boss encounter
# ---------------------------------------------------------------------------

def slime_boss(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Slime Boss with a pre-allocated Empty slot for the split."""
    return Combat(deck, ["SlimeBoss", "Empty"], seed, player_hp)


# ---------------------------------------------------------------------------
# Guardian — Act 1 boss encounter
# ---------------------------------------------------------------------------

def guardian(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Guardian boss: 240 HP, cycles ChargingUp / FierceStrike / VentSteam / Whirlwind."""
    return Combat(deck, ["Guardian"], seed, player_hp)


# ---------------------------------------------------------------------------
# Hexaghost — Act 1 boss encounter
# ---------------------------------------------------------------------------

def hexaghost(seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80) -> Combat:
    """Hexaghost boss: 250 HP, 6-turn cycle (Activate/Divider/Sear/Inflate/Sear/Inferno)."""
    return Combat(deck, ["Hexaghost"], seed, player_hp)


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


def act1_weak_encounter(
    seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80
) -> Combat:
    """Pick uniformly from the Act 1 weak (starting) encounter pool.

    Pool: Cultist, JawWorm, TwoLouses, SmallSlimes.
    Source: MonsterEncounterPool::weakEnemies[0].
    """
    pool_rng = RNG(seed ^ _ACT1_POOL_SALT)
    factory = _ACT1_WEAK_FACTORIES[pool_rng.randint(0, 3)]
    return factory(seed, deck=deck, player_hp=player_hp)


def act1_strong_encounter(
    seed: int, *, deck: list[str] = IRONCLAD_STARTER, player_hp: int = 80
) -> Combat:
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
            return factory(seed, deck=deck, player_hp=player_hp)
    return _ACT1_STRONG_POOL[-1][0](seed, deck=deck, player_hp=player_hp)
