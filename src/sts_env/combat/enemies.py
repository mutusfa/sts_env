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
    from .state import CombatState, EnemyState


class IntentType(Enum):
    ATTACK = auto()
    DEFEND = auto()
    BUFF = auto()
    DEBUFF = auto()        # enemy debuffs the player only
    ATTACK_DEFEND = auto()
    ATTACK_DEBUFF = auto() # enemy attacks AND debuffs the player
    SPLIT = auto()         # large slime splits into two mediums
    ESCAPE = auto()        # Looter/Mugger: enemy flees combat


@dataclass(frozen=True)
class Intent:
    intent_type: IntentType
    damage: int = 0
    hits: int = 1
    block_gain: int = 0
    strength_gain: int = 0
    # Post-resolution debuffs applied to the player after the attack resolves
    applies_weak: int = 0
    applies_frail: int = 0
    applies_vulnerable: int = 0
    applies_entangle: int = 0   # Red Slaver: player cannot play Skill cards next turn
    # Block granted to a random alive ally (Shield Gremlin pattern)
    ally_block_gain: int = 0
    # Status/curse cards added to the player's discard pile on resolution
    status_card_id: str = ""
    status_card_count: int = 0
    # If True, status cards go to draw pile instead of discard (Sentry Bolt / Dazed)
    status_to_draw: bool = False
    # Energy loss applied to the player at the start of their next turn
    energy_loss: int = 0
    # Gold stolen from the player (Looter/Mugger Mug); refunded if enemy is killed
    gold_steal: int = 0


@dataclass(frozen=True)
class EnemySpec:
    name: str
    hp_min: int
    hp_max: int


IntentPicker = Callable[["EnemyState", "RNG", int], Intent]
# Context-aware picker also receives state + own enemy_index
ContextPicker = Callable[["EnemyState", "RNG", int, "CombatState", int], Intent]
PreBattleHook = Callable[["EnemyState", "CombatState"], None]

_SPECS: dict[str, EnemySpec] = {}
_PICKERS: dict[str, IntentPicker] = {}
_CONTEXT_PICKERS: dict[str, ContextPicker] = {}
_PRE_BATTLE: dict[str, PreBattleHook] = {}


def register_enemy(
    spec: EnemySpec,
    picker: IntentPicker | None = None,
    pre_battle: PreBattleHook | None = None,
    *,
    context_picker: ContextPicker | None = None,
) -> None:
    _SPECS[spec.name] = spec
    if picker is not None:
        _PICKERS[spec.name] = picker
    if context_picker is not None:
        _CONTEXT_PICKERS[spec.name] = context_picker
    if pre_battle is not None:
        _PRE_BATTLE[spec.name] = pre_battle


def run_pre_battle(enemy: "EnemyState", state: "CombatState") -> None:
    """Call the enemy's pre-battle hook if one is registered."""
    hook = _PRE_BATTLE.get(enemy.name)
    if hook is not None:
        hook(enemy, state)


def pick_intent_with_state(
    enemy: "EnemyState",
    rng: "RNG",
    turn: int,
    state: "CombatState",
    enemy_index: int,
) -> Intent:
    """Pick intent, supplying state for context-aware enemies (e.g. ShieldGremlin)."""
    ctx = _CONTEXT_PICKERS.get(enemy.name)
    if ctx is not None:
        return ctx(enemy, rng, turn, state, enemy_index)
    return _PICKERS[enemy.name](enemy, rng, turn)


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
        return Intent(IntentType.BUFF, strength_gain=0)
    return Intent(IntentType.ATTACK, damage=6, hits=1)


def _cultist_pre_battle(enemy: "EnemyState", state: "CombatState") -> None:  # noqa: ARG001
    enemy.powers.ritual = 3
    enemy.powers.ritual_just_applied = True


register_enemy(_CULTIST, _cultist_intent, _cultist_pre_battle)


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
    "CorrosiveSpit": Intent(IntentType.ATTACK_DEBUFF, damage=7, hits=1, status_card_id="Slimed", status_card_count=1),
    "Tackle":        Intent(IntentType.ATTACK, damage=10, hits=1),
    "Lick":          Intent(IntentType.DEBUFF, applies_weak=1),
}


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


# ---------------------------------------------------------------------------
# Spike Slime (S)
# ---------------------------------------------------------------------------
# HP 10-14, always TACKLE (5 dmg).
# Source: MonsterSpecific.cpp line ~2771

_SPIKE_SLIME_S = EnemySpec("SpikeSlimeS", hp_min=10, hp_max=14)

_SSS_TACKLE = Intent(IntentType.ATTACK, damage=5, hits=1)


def _spike_slime_s_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    enemy.move_history.append("Tackle")
    return _SSS_TACKLE


register_enemy(_SPIKE_SLIME_S, _spike_slime_s_intent)


# ---------------------------------------------------------------------------
# Acid Slime (S)
# ---------------------------------------------------------------------------
# HP 8-12. Strictly alternates: first move is 50/50, then strict alternation.
# Tackle: 3 dmg. Lick: applies Weak 1.
# Source: MonsterSpecific.cpp line ~1891 — each move setMove to the other.

_ACID_SLIME_S = EnemySpec("AcidSlimeS", hp_min=8, hp_max=12)

_ASS_INTENTS: dict[str, Intent] = {
    "Tackle": Intent(IntentType.ATTACK, damage=3, hits=1),
    "Lick":   Intent(IntentType.DEBUFF, applies_weak=1),
}


def _acid_slime_s_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    if not history:
        # First move: 50/50 via a randomBoolean
        chosen = "Tackle" if rng.random() < 0.5 else "Lick"
    else:
        # Strict alternation — opposite of last move
        chosen = "Lick" if history[-1] == "Tackle" else "Tackle"
    enemy.move_history.append(chosen)
    return _ASS_INTENTS[chosen]


register_enemy(_ACID_SLIME_S, _acid_slime_s_intent)


# ---------------------------------------------------------------------------
# Red Louse
# ---------------------------------------------------------------------------
# HP 10-15.  Pre-battle: roll bite dmg 5-7 (stored in enemy.misc) and
# Curl Up 3-7.  Moves: BITE (misc dmg) / GROW (+3 str asc 0).
# Constraints (asc 0): GROW max 1 in a row; BITE max 2 in a row (lastTwoMoves).
# Source: MonsterSpecific.cpp line ~2585, Monster.cpp line ~115.

_RED_LOUSE = EnemySpec("RedLouse", hp_min=10, hp_max=15)


def _louse_pre_battle(enemy: "EnemyState", state: "CombatState") -> None:
    """Roll bite damage and Curl Up stacks."""
    enemy.misc = state.rng.randint(5, 7)
    enemy.powers.curl_up = state.rng.randint(3, 7)


def _red_louse_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll < 25:
        # Wants Grow.  Constraint (asc 0): lastMove(Grow) AND lastTwoMoves(Grow)
        # → max 2 in a row.
        if _last_move(history, "Grow") and _last_two_moves(history, "Grow"):
            chosen = "Bite"
        else:
            chosen = "Grow"
    else:
        # Wants Bite; constrained to max 2 in a row (lastTwoMoves)
        if _last_two_moves(history, "Bite"):
            chosen = "Grow"
        else:
            chosen = "Bite"

    enemy.move_history.append(chosen)
    if chosen == "Bite":
        return Intent(IntentType.ATTACK, damage=enemy.misc, hits=1)
    # Grow: strength +3 (asc 0)
    return Intent(IntentType.BUFF, strength_gain=3)


register_enemy(_RED_LOUSE, _red_louse_intent, _louse_pre_battle)


# ---------------------------------------------------------------------------
# Green Louse
# ---------------------------------------------------------------------------
# HP 11-17.  Same pre-battle as Red Louse (bite roll + Curl Up).
# Moves: BITE (misc dmg) / SPIT_WEB (Weak 2).
# Constraints: SPIT_WEB max 1 in a row (lastMove); BITE max 2 in a row.
# Source: MonsterSpecific.cpp line ~2315.

_GREEN_LOUSE = EnemySpec("GreenLouse", hp_min=11, hp_max=17)


def _green_louse_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll < 25:
        # Wants SpitWeb.  Constraint (asc 0): lastMove(SpitWeb) AND lastTwoMoves(SpitWeb)
        # → max 2 in a row.
        if _last_move(history, "SpitWeb") and _last_two_moves(history, "SpitWeb"):
            chosen = "Bite"
        else:
            chosen = "SpitWeb"
    else:
        # Wants Bite; constrained to max 2 in a row
        if _last_two_moves(history, "Bite"):
            chosen = "SpitWeb"
        else:
            chosen = "Bite"

    enemy.move_history.append(chosen)
    if chosen == "Bite":
        return Intent(IntentType.ATTACK, damage=enemy.misc, hits=1)
    return Intent(IntentType.DEBUFF, applies_weak=2)


register_enemy(_GREEN_LOUSE, _green_louse_intent, _louse_pre_battle)


# ---------------------------------------------------------------------------
# Fat Gremlin
# ---------------------------------------------------------------------------
# HP 13-17, always SMASH (4 dmg + Weak 1 to player).
# Source: MonsterSpecific.cpp line ~2291

_FAT_GREMLIN = EnemySpec("FatGremlin", hp_min=13, hp_max=17)

_FG_SMASH = Intent(IntentType.ATTACK_DEBUFF, damage=4, hits=1, applies_weak=1)


def _fat_gremlin_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    enemy.move_history.append("Smash")
    return _FG_SMASH


register_enemy(_FAT_GREMLIN, _fat_gremlin_intent)


# ---------------------------------------------------------------------------
# Mad Gremlin
# ---------------------------------------------------------------------------
# HP 20-24.  Pre-battle: Angry 1.  Always SCRATCH (4 dmg).
# Source: MonsterSpecific.cpp line ~2507, preBattleAction line ~158.

_MAD_GREMLIN = EnemySpec("MadGremlin", hp_min=20, hp_max=24)

_MG_SCRATCH = Intent(IntentType.ATTACK, damage=4, hits=1)


def _mad_gremlin_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    enemy.move_history.append("Scratch")
    return _MG_SCRATCH


def _mad_gremlin_pre_battle(enemy: "EnemyState", state: "CombatState") -> None:  # noqa: ARG001
    enemy.powers.angry = 1


register_enemy(_MAD_GREMLIN, _mad_gremlin_intent, _mad_gremlin_pre_battle)


# ---------------------------------------------------------------------------
# Sneaky Gremlin
# ---------------------------------------------------------------------------
# HP 10-14, always PUNCTURE (9 dmg).
# Source: MonsterSpecific.cpp line ~2747

_SNEAKY_GREMLIN = EnemySpec("SneakyGremlin", hp_min=10, hp_max=14)

_SG_PUNCTURE = Intent(IntentType.ATTACK, damage=9, hits=1)


def _sneaky_gremlin_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    enemy.move_history.append("Puncture")
    return _SG_PUNCTURE


register_enemy(_SNEAKY_GREMLIN, _sneaky_gremlin_intent)


# ---------------------------------------------------------------------------
# Shield Gremlin
# ---------------------------------------------------------------------------
# HP 12-15.  PROTECT: give 7 block to a random alive ally.
# When alone (no live ally at intent-pick time): SHIELD_BASH (6 dmg).
# Requires state context to determine liveness of allies → uses context_picker.
# Source: MonsterSpecific.cpp line ~2699.

_SHIELD_GREMLIN = EnemySpec("ShieldGremlin", hp_min=12, hp_max=15)

_SGREM_PROTECT = Intent(IntentType.BUFF, ally_block_gain=7)
_SGREM_BASH = Intent(IntentType.ATTACK, damage=6, hits=1)


def _shield_gremlin_picker(
    enemy: "EnemyState",
    rng: "RNG",  # noqa: ARG001
    turn: int,  # noqa: ARG001
    state: "CombatState",
    enemy_index: int,
) -> Intent:
    has_live_ally = any(
        e.alive for i, e in enumerate(state.enemies) if i != enemy_index
    )
    if has_live_ally:
        enemy.move_history.append("Protect")
        return _SGREM_PROTECT
    else:
        enemy.move_history.append("ShieldBash")
        return _SGREM_BASH


register_enemy(_SHIELD_GREMLIN, context_picker=_shield_gremlin_picker)


# ---------------------------------------------------------------------------
# Gremlin Wizard
# ---------------------------------------------------------------------------
# HP 21-25.  Charges for 3 turns (enemy.misc counts 1→2→3), then fires
# ULTIMATE_BLAST (25 dmg) and resets the counter to 0.
# Source: MonsterSpecific.cpp line ~2438.

_GREMLIN_WIZARD = EnemySpec("GremlinWizard", hp_min=21, hp_max=25)

_GW_CHARGING = Intent(IntentType.BUFF)
_GW_BLAST = Intent(IntentType.ATTACK, damage=25, hits=1)


def _gremlin_wizard_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001, ARG002
    if enemy.misc < 3:
        enemy.misc += 1
        enemy.move_history.append("Charging")
        return _GW_CHARGING
    else:
        enemy.misc = 0
        enemy.move_history.append("UltimateBlast")
        return _GW_BLAST


register_enemy(_GREMLIN_WIZARD, _gremlin_wizard_intent)


# ---------------------------------------------------------------------------
# Spike Slime (M)
# ---------------------------------------------------------------------------
# HP 28-32.  FlameTackle (8 dmg + 1 Slimed), Lick (Frail 1).
# Constraints asc 0: FlameTackle max 2 in a row, Lick max 2 in a row.
# Source: MonsterSpecific.cpp line ~2822

_SPIKE_SLIME_M = EnemySpec("SpikeSlimeM", hp_min=28, hp_max=32)

_SSM_INTENTS: dict[str, Intent] = {
    "FlameTackle": Intent(IntentType.ATTACK_DEBUFF, damage=8, hits=1, status_card_id="Slimed", status_card_count=1),
    "Lick":        Intent(IntentType.DEBUFF, applies_frail=1),
}


def _spike_slime_m_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll < 30:
        if _last_two_moves(history, "FlameTackle"):
            chosen = "Lick"
        else:
            chosen = "FlameTackle"
    else:
        if _last_two_moves(history, "Lick"):
            chosen = "FlameTackle"
        else:
            chosen = "Lick"

    enemy.move_history.append(chosen)
    return _SSM_INTENTS[chosen]


register_enemy(_SPIKE_SLIME_M, _spike_slime_m_intent)


# ---------------------------------------------------------------------------
# Spike Slime (L)
# ---------------------------------------------------------------------------
# HP 64-70.  FlameTackle (16 dmg + 2 Slimed), Lick (Frail 2).
# Splits at <=50% HP.
# Constraints asc 0: FlameTackle max 2 in a row, Lick max 1 in a row.
# Source: MonsterSpecific.cpp line ~2801

_SPIKE_SLIME_L = EnemySpec("SpikeSlimeL", hp_min=64, hp_max=70)

_SSL_INTENTS: dict[str, Intent] = {
    "FlameTackle": Intent(IntentType.ATTACK_DEBUFF, damage=16, hits=1, status_card_id="Slimed", status_card_count=2),
    "Lick":        Intent(IntentType.DEBUFF, applies_frail=2),
}


def _spike_slime_l_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll < 30:
        if _last_two_moves(history, "FlameTackle"):
            chosen = "Lick"
        else:
            chosen = "FlameTackle"
    else:
        # Lick: constrained to max 1 in a row (lastMove check)
        if _last_move(history, "Lick"):
            chosen = "FlameTackle"
        else:
            chosen = "Lick"

    enemy.move_history.append(chosen)
    return _SSL_INTENTS[chosen]


register_enemy(_SPIKE_SLIME_L, _spike_slime_l_intent)


# ---------------------------------------------------------------------------
# Acid Slime (L)
# ---------------------------------------------------------------------------
# HP 65-69.  CorrosiveSpit (11 dmg + 2 Slimed), Tackle (16 dmg), Lick (Weak 2).
# Splits at <=50% HP.
# Constraints asc 0: CorrosiveSpit max 2 in a row, Tackle max 1 in a row, Lick max 1 in a row.
# Source: MonsterSpecific.cpp line ~2016 (asc 0 branch)
#
# Fallbacks (asc 0):
#   From CorrosiveSpit: Tackle (50%) or Lick (50%)
#   From Tackle:        CorrosiveSpit (40%) or Lick (60%)
#   From Lick:          CorrosiveSpit (40%) or Tackle (60%)

_ACID_SLIME_L = EnemySpec("AcidSlimeL", hp_min=65, hp_max=69)

_AL_INTENTS: dict[str, Intent] = {
    "CorrosiveSpit": Intent(IntentType.ATTACK_DEBUFF, damage=11, hits=1, status_card_id="Slimed", status_card_count=2),
    "Tackle":        Intent(IntentType.ATTACK, damage=16, hits=1),
    "Lick":          Intent(IntentType.DEBUFF, applies_weak=2),
}


def _acid_slime_l_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
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
        if _last_move(history, "Lick"):
            chosen = "CorrosiveSpit" if rng.random() < 0.4 else "Tackle"
        else:
            chosen = "Lick"

    enemy.move_history.append(chosen)
    return _AL_INTENTS[chosen]


register_enemy(_ACID_SLIME_L, _acid_slime_l_intent)


# ---------------------------------------------------------------------------
# Blue Slaver
# ---------------------------------------------------------------------------
# HP 46-50.  Stab (12 dmg) / Rake (7 dmg + Weak 1).
# Roll >= 40 → wants Stab (if not 2× in a row); else → Rake (if not 2× in a row); else → Stab.
# Source: MonsterSpecific.cpp line ~2048 (ascension 0)

_BLUE_SLAVER = EnemySpec("BlueSlaver", hp_min=46, hp_max=50)

_BS_INTENTS: dict[str, Intent] = {
    "Stab": Intent(IntentType.ATTACK, damage=12, hits=1),
    "Rake": Intent(IntentType.ATTACK_DEBUFF, damage=7, hits=1, applies_weak=1),
}


def _blue_slaver_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll >= 40 and not _last_two_moves(history, "Stab"):
        chosen = "Stab"
    elif not _last_two_moves(history, "Rake"):
        chosen = "Rake"
    else:
        chosen = "Stab"

    enemy.move_history.append(chosen)
    return _BS_INTENTS[chosen]


register_enemy(_BLUE_SLAVER, _blue_slaver_intent)


# ---------------------------------------------------------------------------
# Red Slaver
# ---------------------------------------------------------------------------
# HP 46-50.  Stab (13 dmg) / Entangle (player entangled 1 turn) / Scrape (8 dmg + Vul 1).
# Turn 0 always Stab.  Entangle: roll >= 75 if not yet used (misc tracks use).
# After Entangle used: roll >= 50 and not 2× Stab → Stab; else if not 2× Scrape → Scrape;
# else → Stab.
# Source: MonsterSpecific.cpp line ~2775

_RED_SLAVER = EnemySpec("RedSlaver", hp_min=46, hp_max=50)

_RS_INTENTS: dict[str, Intent] = {
    "Stab":    Intent(IntentType.ATTACK, damage=13, hits=1),
    "Entangle": Intent(IntentType.DEBUFF, applies_entangle=1),
    "Scrape":  Intent(IntentType.ATTACK_DEBUFF, damage=8, hits=1, applies_vulnerable=1),
}


def _red_slaver_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    used_entangle = bool(enemy.misc)

    if not history:
        enemy.move_history.append("Stab")
        return _RS_INTENTS["Stab"]

    roll = rng.randint(0, 99)

    if roll >= 75 and not used_entangle:
        chosen = "Entangle"
        enemy.misc = 1  # Mark Entangle as used
    elif roll >= 50 and used_entangle and not _last_two_moves(history, "Stab"):
        chosen = "Stab"
    elif not _last_two_moves(history, "Scrape"):
        chosen = "Scrape"
    else:
        chosen = "Stab"

    enemy.move_history.append(chosen)
    return _RS_INTENTS[chosen]


register_enemy(_RED_SLAVER, _red_slaver_intent)


# ---------------------------------------------------------------------------
# Fungi Beast
# ---------------------------------------------------------------------------
# HP 22-28.  Bite (6 dmg, 60%) / Grow (+3 str, 40%).
# Bite max 2 in a row; Grow max 1 in a row.
# Pre-battle: SporeCloud 2 (on death → apply Vulnerable 2 to player).
# Source: MonsterSpecific.cpp line ~2296

_FUNGI_BEAST = EnemySpec("FungiBeast", hp_min=22, hp_max=28)

_FB_INTENTS: dict[str, Intent] = {
    "Bite": Intent(IntentType.ATTACK, damage=6, hits=1),
    "Grow": Intent(IntentType.BUFF, strength_gain=3),
}


def _fungi_beast_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    roll = rng.randint(0, 99)

    if roll < 60:
        if _last_two_moves(history, "Bite"):
            chosen = "Grow"
        else:
            chosen = "Bite"
    elif _last_move(history, "Grow"):
        chosen = "Bite"
    else:
        chosen = "Grow"

    enemy.move_history.append(chosen)
    return _FB_INTENTS[chosen]


def _fungi_beast_pre_battle(enemy: "EnemyState", state: "CombatState") -> None:  # noqa: ARG001
    enemy.powers.spore_cloud = 2


register_enemy(_FUNGI_BEAST, _fungi_beast_intent, _fungi_beast_pre_battle)


# ---------------------------------------------------------------------------
# Looter
# ---------------------------------------------------------------------------
# HP 44-48.  Fixed script (asc 0): Mug(10) → Mug(10) → [SmokeBomb(6blk) | Lunge(12)] →
#   SmokeBomb(6blk) [if Lunge taken] → Escape.
# Source: MonsterSpecific.cpp line ~899

_LOOTER = EnemySpec("Looter", hp_min=44, hp_max=48)

_LO_MUG        = Intent(IntentType.ATTACK, damage=10, hits=1, gold_steal=15)
_LO_SMOKE_BOMB = Intent(IntentType.DEFEND, block_gain=6)
_LO_LUNGE      = Intent(IntentType.ATTACK, damage=12, hits=1)
_LO_ESCAPE     = Intent(IntentType.ESCAPE)


def _looter_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history

    if not history or (len(history) == 1 and history[-1] == "Mug"):
        enemy.move_history.append("Mug")
        return _LO_MUG

    last = history[-1]
    if last == "Mug":  # Third call: second Mug resolved → branch
        chosen = "SmokeBomb" if rng.random() < 0.5 else "Lunge"
        enemy.move_history.append(chosen)
        return _LO_SMOKE_BOMB if chosen == "SmokeBomb" else _LO_LUNGE
    elif last == "Lunge":
        enemy.move_history.append("SmokeBomb")
        return _LO_SMOKE_BOMB
    else:  # last == "SmokeBomb"
        enemy.move_history.append("Escape")
        return _LO_ESCAPE


register_enemy(_LOOTER, _looter_intent)


# ---------------------------------------------------------------------------
# Mugger
# ---------------------------------------------------------------------------
# HP 48-52.  Same script as Looter but SmokeBomb gives 11 block and Lunge deals 16 dmg.
# Source: MonsterSpecific.cpp line ~944

_MUGGER = EnemySpec("Mugger", hp_min=48, hp_max=52)

_MU_MUG        = Intent(IntentType.ATTACK, damage=10, hits=1, gold_steal=20)
_MU_SMOKE_BOMB = Intent(IntentType.DEFEND, block_gain=11)
_MU_LUNGE      = Intent(IntentType.ATTACK, damage=16, hits=1)
_MU_ESCAPE     = Intent(IntentType.ESCAPE)


def _mugger_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history

    if not history or (len(history) == 1 and history[-1] == "Mug"):
        enemy.move_history.append("Mug")
        return _MU_MUG

    last = history[-1]
    if last == "Mug":
        chosen = "SmokeBomb" if rng.random() < 0.5 else "Lunge"
        enemy.move_history.append(chosen)
        return _MU_SMOKE_BOMB if chosen == "SmokeBomb" else _MU_LUNGE
    elif last == "Lunge":
        enemy.move_history.append("SmokeBomb")
        return _MU_SMOKE_BOMB
    else:  # last == "SmokeBomb"
        enemy.move_history.append("Escape")
        return _MU_ESCAPE


register_enemy(_MUGGER, _mugger_intent)


# ---------------------------------------------------------------------------
# Gremlin Nob (Elite)
# ---------------------------------------------------------------------------
# HP 82-86.  Turn 0: Bellow (lose 2 energy next turn, Nob gains Angry).
# Turn 1+: Rush (14 dmg).  If player plays a Skill, Nob gains 2 Strength.
#
# Simplified: always Rush after turn 0. The "skill played → gain strength"
# mechanic would require a trigger system; we skip it for now.
# Source: MonsterSpecific.cpp line ~2363

_GREMLIN_NOB = EnemySpec("GremlinNob", hp_min=82, hp_max=86)

_GN_BELLOW = Intent(IntentType.BUFF, strength_gain=0, energy_loss=2)  # Angry applied via pre_battle; energy_loss on player next turn
_GN_RUSH = Intent(IntentType.ATTACK, damage=14, hits=1)


def _gremlin_nob_pre_battle(enemy: "EnemyState", state: "CombatState") -> None:
    """Apply Angry 1 on spawn and set skill_played_str for Skill-punish."""
    enemy.powers.angry = 1
    enemy.skill_played_str = 2


def _gremlin_nob_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    if turn == 0:
        enemy.move_history.append("Bellow")
        return _GN_BELLOW
    enemy.move_history.append("Rush")
    return _GN_RUSH


register_enemy(_GREMLIN_NOB, _gremlin_nob_intent, _gremlin_nob_pre_battle)


# ---------------------------------------------------------------------------
# Lagavulin (Elite)
# ---------------------------------------------------------------------------
# HP 109-111.  Starts asleep for 3 turns (or until attacked).
# While sleeping: -1 player strength at end of each turn + 8 metallicize (block).
# Awake cycle: Attack (18 dmg) → Siphon Soul (-1 str, -1 dex to player) → Attack (18 dmg).
# Source: MonsterSpecific.cpp line ~2483

_LAGAVULIN = EnemySpec("Lagavulin", hp_min=109, hp_max=111)

_LAG_SLEEP = Intent(IntentType.DEFEND, block_gain=0)  # block from metallicize
_LAG_ATTACK = Intent(IntentType.ATTACK, damage=18, hits=1)
_LAG_SIPHON = Intent(IntentType.DEBUFF)  # -1 str -1 dex applied via context


def _lagavulin_pre_battle(enemy: "EnemyState", state: "CombatState") -> None:
    """Start asleep with 8 metallicize. Sleep lasts 3 turns or until attacked."""
    enemy.powers.asleep = True
    enemy.powers.enemy_metallicize = 8
    enemy.misc = 3  # sleep turns remaining


def _lagavulin_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    if enemy.powers.asleep:
        enemy.move_history.append("Sleep")
        return _LAG_SLEEP

    # Awake cycle: Attack → Siphon → Attack → repeat
    # Use move history to determine position in cycle
    # Count awake moves
    awake_moves = [m for m in enemy.move_history if m in ("Attack", "SiphonSoul")]
    if not awake_moves:
        # First awake move
        enemy.move_history.append("Attack")
        return _LAG_ATTACK

    last_awake = awake_moves[-1]
    if last_awake == "Attack":
        enemy.move_history.append("SiphonSoul")
        return _LAG_SIPHON
    else:
        enemy.move_history.append("Attack")
        return _LAG_ATTACK


register_enemy(_LAGAVULIN, _lagavulin_intent, _lagavulin_pre_battle)


# ---------------------------------------------------------------------------
# Sentry (Elite — appears as group of 3)
# ---------------------------------------------------------------------------
# HP 38-42 each.  Cycle: Beam (9 dmg) / Bolt (add 1 Dazed to discard).
# Each sentry alternates independently.
# Source: MonsterSpecific.cpp line ~2659

_SENTRY = EnemySpec("Sentry", hp_min=38, hp_max=42)

_SENTRY_BEAM = Intent(IntentType.ATTACK, damage=9, hits=1)
_SENTRY_BOLT = Intent(IntentType.DEBUFF, status_card_id="Dazed", status_card_count=1, status_to_draw=True)


def _sentry_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    history = enemy.move_history
    if not history or history[-1] == "Bolt":
        enemy.move_history.append("Beam")
        return _SENTRY_BEAM
    else:
        enemy.move_history.append("Bolt")
        return _SENTRY_BOLT


register_enemy(_SENTRY, _sentry_intent)


# ---------------------------------------------------------------------------
# Slime Boss (Act 1 Boss)
# ---------------------------------------------------------------------------
# HP 140.  Fixed 3-turn cycle: Goop Spray → Preparing → Slam, repeating.
#
#   Goop Spray: Add 3 Slimed status cards to the player's discard pile.
#               Intent type: DEBUFF. No damage, no block.
#   Preparing:  Does nothing (telegraph for Slam). Intent type: BUFF.
#   Slam:       Deal 35 damage. Intent type: ATTACK.
#
# Splits at ≤50% HP (≤70 HP) into AcidSlimeM + SpikeSlimeM.
# Source: MonsterSpecific.cpp line ~2540 (ascension 0)

_SLIME_BOSS = EnemySpec("SlimeBoss", hp_min=140, hp_max=140)

_SB_GOOP_SPRAY = Intent(IntentType.DEBUFF, status_card_id="Slimed", status_card_count=3)
_SB_PREPARING = Intent(IntentType.BUFF)
_SB_SLAM = Intent(IntentType.ATTACK, damage=35, hits=1)

_SB_CYCLE = [_SB_GOOP_SPRAY, _SB_PREPARING, _SB_SLAM]


def _slime_boss_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    idx = turn % len(_SB_CYCLE)
    move_names = ["GoopSpray", "Preparing", "Slam"]
    enemy.move_history.append(move_names[idx])
    return _SB_CYCLE[idx]


register_enemy(_SLIME_BOSS, _slime_boss_intent)


# ---------------------------------------------------------------------------
# Hexaghost (Act 1 Boss)
# ---------------------------------------------------------------------------
# HP 250.  Fixed 6-turn cycle:
#   Turn 0: Activate  — BUFF (telegraphs Divider)
#   Turn 1: Divider   — ATTACK 6×6 (6 damage, 6 hits)
#   Turn 2: Sear       — ATTACK 6×2 + add 1 Burn to discard
#   Turn 3: Inflate    — BUFF (+2 Strength)
#   Turn 4: Sear       — ATTACK 6×2 + add 1 Burn to discard
#   Turn 5: Inferno    — ATTACK 2×6 + add 3 Burn to discard
# Then repeats from Activate.
# Source: MonsterSpecific.cpp line ~2391 (ascension 0)

_HEXAGHOST = EnemySpec("Hexaghost", hp_min=250, hp_max=250)

_HG_ACTIVATE = Intent(IntentType.BUFF)
_HG_DIVIDER  = Intent(IntentType.ATTACK, damage=6, hits=6)
_HG_SEAR     = Intent(IntentType.ATTACK_DEBUFF, damage=6, hits=2,
                       status_card_id="Burn", status_card_count=1)
_HG_INFLATE  = Intent(IntentType.BUFF, strength_gain=2)
_HG_INFERNO  = Intent(IntentType.ATTACK_DEBUFF, damage=2, hits=6,
                       status_card_id="Burn", status_card_count=3)

_HG_CYCLE = [_HG_ACTIVATE, _HG_DIVIDER, _HG_SEAR, _HG_INFLATE, _HG_SEAR, _HG_INFERNO]
_HG_NAMES = ["Activate", "Divider", "Sear", "Inflate", "Sear", "Inferno"]


def _hexaghost_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    idx = turn % len(_HG_CYCLE)
    enemy.move_history.append(_HG_NAMES[idx])
    return _HG_CYCLE[idx]


register_enemy(_HEXAGHOST, _hexaghost_intent)


# ---------------------------------------------------------------------------
# Guardian — Act 1 boss
# ---------------------------------------------------------------------------
# HP: 240 (fixed)
# Attack-stance cycle (repeats):
#   Charging Up  — DEFEND (gains 9 block)
#   Fierce Strike — ATTACK 32 damage
#   Vent Steam   — DEBUFF (2 Weak + 2 Vulnerable to player)
#   Whirlwind    — ATTACK 5×4 (5 damage, 4 hits)
# Source: MonsterSpecific.cpp (ascension 0)

_GUARDIAN = EnemySpec("Guardian", hp_min=240, hp_max=240)

_GU_CHARGING = Intent(IntentType.DEFEND, block_gain=9)
_GU_FIERCE = Intent(IntentType.ATTACK, damage=32, hits=1)
_GU_VENT = Intent(IntentType.DEBUFF, applies_weak=2, applies_vulnerable=2)
_GU_WHIRLWIND = Intent(IntentType.ATTACK, damage=5, hits=4)

_GU_CYCLE = [_GU_CHARGING, _GU_FIERCE, _GU_VENT, _GU_WHIRLWIND]


def _guardian_intent(enemy: "EnemyState", rng: "RNG", turn: int) -> Intent:  # noqa: ARG001
    idx = turn % len(_GU_CYCLE)
    names = ["ChargingUp", "FierceStrike", "VentSteam", "Whirlwind"]
    enemy.move_history.append(names[idx])
    return _GU_CYCLE[idx]


register_enemy(_GUARDIAN, _guardian_intent)
