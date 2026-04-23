"""Enemy definitions for Act 1 (v1 scope: Cultist, Jaw Worm, Acid Slime M).

Reference: sts_lightspeed/src/combat/MonsterSpecific.cpp (ascension 0).

Each enemy has:
  - An EnemySpec: static data (name, hp range).
  - A pick_intent function: (enemy_state, rng, turn) -> Intent

Intent represents what the enemy will do this turn.

RNG note: sts_lightspeed uses two separate RNGs per combat (aiRng for move
selection and a second randomBoolean RNG for fallback ties). We use a single
RNG and consume two values when a fallback is needed. Sequences will differ
from sts_lightspeed for the same seed, but the statistical distribution and
max-repeat constraints match exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .rng import RNG
    from .state import EnemyState


class IntentType(Enum):
    ATTACK = auto()
    DEFEND = auto()
    BUFF = auto()
    ATTACK_DEFEND = auto()


@dataclass(frozen=True)
class Intent:
    intent_type: IntentType
    damage: int = 0
    hits: int = 1
    block_gain: int = 0
    strength_gain: int = 0


@dataclass(frozen=True)
class EnemySpec:
    name: str
    hp_min: int
    hp_max: int


IntentPicker = Callable[["EnemyState", "RNG", int], Intent]

_SPECS: dict[str, EnemySpec] = {}
_PICKERS: dict[str, IntentPicker] = {}


def register_enemy(spec: EnemySpec, picker: IntentPicker) -> None:
    _SPECS[spec.name] = spec
    _PICKERS[spec.name] = picker


def get_spec(name: str) -> EnemySpec:
    return _SPECS[name]


def pick_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:
    return _PICKERS[enemy.name](enemy, rng, turn)


def roll_hp(name: str, rng: "RNG") -> int:
    spec = _SPECS[name]
    return rng.randint(spec.hp_min, spec.hp_max)


# ---------------------------------------------------------------------------
# Cultist
# ---------------------------------------------------------------------------
# Turn 0: Incantation (ritual 3 — permanent effect, applied each start of turn)
# Turn 1+: Dark Strike (6 damage), no move limit.
# Source: MonsterSpecific.cpp line ~2282

_CULTIST = EnemySpec("Cultist", hp_min=48, hp_max=54)


def _cultist_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    if turn == 0:
        return Intent(IntentType.BUFF, strength_gain=0)  # ritual 3 applied in engine
    return Intent(IntentType.ATTACK, damage=6, hits=1)


register_enemy(_CULTIST, _cultist_intent)


# ---------------------------------------------------------------------------
# Jaw Worm
# ---------------------------------------------------------------------------
# Source: MonsterSpecific.cpp line ~2452 (ascension 0)
#
# Move weights (base probability, roll 0-99):
#   roll < 25 → wants Chomp   (25%)
#   roll < 55 → wants Thrash  (30%)
#   roll >= 55 → wants Bellow  (45%)
#
# Constraints (fallback uses second RNG value):
#   Chomp:  cannot follow Chomp directly  (lastMove check → max 1 in a row)
#   Thrash: cannot follow two Thrash      (lastTwoMoves check → max 2 in a row)
#   Bellow: cannot follow Bellow directly (lastMove check → max 1 in a row)
#
# Fallback probabilities when constraint fires:
#   From Chomp bucket:  Bellow with p=0.5625, Thrash otherwise
#   From Thrash bucket: Chomp with p=0.357,   Bellow otherwise
#   From Bellow bucket: Chomp with p=0.416,   Thrash otherwise

_JAW_WORM = EnemySpec("JawWorm", hp_min=40, hp_max=44)

_JW_INTENTS: dict[str, Intent] = {
    "Chomp":  Intent(IntentType.ATTACK, damage=11, hits=1),
    "Thrash": Intent(IntentType.ATTACK_DEFEND, damage=7, hits=1, block_gain=5),
    "Bellow": Intent(IntentType.DEFEND, block_gain=6, strength_gain=3),
}


def _last_move(history: list[str], move: str) -> bool:
    return bool(history) and history[-1] == move


def _last_two_moves(history: list[str], move: str) -> bool:
    return len(history) >= 2 and history[-1] == move and history[-2] == move


def _jaw_worm_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:
    if turn == 0:
        enemy.move_history.append("Chomp")
        return _JW_INTENTS["Chomp"]

    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll < 25:
        if _last_move(history, "Chomp"):
            # Fallback: Bellow (56.25%) or Thrash (43.75%)
            chosen = "Bellow" if rng.random() < 0.5625 else "Thrash"
        else:
            chosen = "Chomp"

    elif roll < 55:
        if _last_two_moves(history, "Thrash"):
            # Fallback: Chomp (35.7%) or Bellow (64.3%)
            chosen = "Chomp" if rng.random() < 0.357 else "Bellow"
        else:
            chosen = "Thrash"

    else:
        if _last_move(history, "Bellow"):
            # Fallback: Chomp (41.6%) or Thrash (58.4%)
            chosen = "Chomp" if rng.random() < 0.416 else "Thrash"
        else:
            chosen = "Bellow"

    enemy.move_history.append(chosen)
    return _JW_INTENTS[chosen]


register_enemy(_JAW_WORM, _jaw_worm_intent)


# ---------------------------------------------------------------------------
# Acid Slime (M)
# ---------------------------------------------------------------------------
# Source: MonsterSpecific.cpp line ~1905 (ascension 0)
#
# Move weights (roll 0-99):
#   roll < 30 → wants CorrosiveSpit (30%)
#   roll < 70 → wants Tackle        (40%)
#   roll >= 70 → wants Lick          (30%)
#
# Constraints:
#   CorrosiveSpit: cannot follow two CorrosiveSpit (lastTwoMoves → max 2 in a row)
#   Tackle:        cannot follow Tackle directly   (lastMove → max 1 in a row)
#   Lick:          cannot follow two Lick          (lastTwoMoves → max 2 in a row)
#
# Fallbacks:
#   From CorrosiveSpit: Tackle (50%) or Lick (50%)
#   From Tackle:        CorrosiveSpit (40%) or Lick (60%)
#   From Lick:          CorrosiveSpit (40%) or Tackle (60%)
#
# First turn: no special case — first roll decides (unlike Jaw Worm)

_ACID_SLIME_M = EnemySpec("AcidSlimeM", hp_min=28, hp_max=32)

_AS_INTENTS: dict[str, Intent] = {
    "CorrosiveSpit": Intent(IntentType.ATTACK, damage=7, hits=1),
    "Tackle":        Intent(IntentType.ATTACK, damage=10, hits=1),
    "Lick":          Intent(IntentType.BUFF),
}

_AS_APPLIES_WEAK = {"CorrosiveSpit", "Lick"}


def _acid_slime_m_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll < 30:
        if _last_two_moves(history, "CorrosiveSpit"):
            chosen = "Tackle" if rng.random() < 0.5 else "Lick"
        else:
            chosen = "CorrosiveSpit"

    elif roll < 70:
        if _last_move(history, "Tackle"):
            chosen = "CorrosiveSpit" if rng.random() < 0.4 else "Lick"
        else:
            chosen = "Tackle"

    else:
        if _last_two_moves(history, "Lick"):
            chosen = "CorrosiveSpit" if rng.random() < 0.4 else "Tackle"
        else:
            chosen = "Lick"

    enemy.move_history.append(chosen)
    return _AS_INTENTS[chosen]


register_enemy(_ACID_SLIME_M, _acid_slime_m_intent)


def move_applies_weak(enemy_name: str, move_name: str) -> bool:
    """Return True if the given move applies Weak to the player."""
    if enemy_name == "AcidSlimeM":
        return move_name in _AS_APPLIES_WEAK
    return False


def move_name_for_last_intent(enemy: "EnemyState") -> str | None:
    if enemy.move_history:
        return enemy.move_history[-1]
    return None
