"""Tests for enemy intent logic.

All repeat-constraint tests are checked against the sts_lightspeed source
(MonsterSpecific.cpp, ascension 0).
"""

from __future__ import annotations

import pytest

from sts_env.combat.enemies import (
    IntentType,
    pick_intent,
    roll_hp,
)
from sts_env.combat.state import EnemyState
from sts_env.combat.rng import RNG


def _make_enemy(name: str, hp: int = 40) -> EnemyState:
    return EnemyState(name=name, hp=hp, max_hp=hp)


# ---------------------------------------------------------------------------
# Cultist
# ---------------------------------------------------------------------------

def test_cultist_turn_0_is_buff():
    enemy = _make_enemy("Cultist", 50)
    intent = pick_intent(enemy, RNG(0), turn=0)
    assert intent.intent_type == IntentType.BUFF


def test_cultist_turn_1_plus_is_attack():
    enemy = _make_enemy("Cultist", 50)
    rng = RNG(0)
    pick_intent(enemy, rng, turn=0)
    intent = pick_intent(enemy, rng, turn=1)
    assert intent.intent_type == IntentType.ATTACK
    assert intent.damage == 6


def test_cultist_always_attacks_after_turn_0():
    enemy = _make_enemy("Cultist", 50)
    rng = RNG(0)
    for turn in range(10):
        intent = pick_intent(enemy, rng, turn=turn)
        if turn == 0:
            assert intent.intent_type == IntentType.BUFF
        else:
            assert intent.intent_type == IntentType.ATTACK


def test_cultist_hp_range():
    for seed in range(30):
        hp = roll_hp("Cultist", RNG(seed))
        assert 48 <= hp <= 54


# ---------------------------------------------------------------------------
# Jaw Worm
# ---------------------------------------------------------------------------
# Source constraints (asc 0):
#   Chomp  max 1 in a row (lastMove guard)
#   Thrash max 2 in a row (lastTwoMoves guard)
#   Bellow max 1 in a row (lastMove guard)

def test_jaw_worm_first_intent_is_chomp():
    enemy = _make_enemy("JawWorm", 42)
    intent = pick_intent(enemy, RNG(0), turn=0)
    assert intent.intent_type == IntentType.ATTACK
    assert intent.damage == 11


def _check_jaw_worm_constraints(seed: int) -> None:
    enemy = _make_enemy("JawWorm", 42)
    rng = RNG(seed)
    history: list[str] = []
    for turn in range(60):
        pick_intent(enemy, rng, turn=turn)
        history.append(enemy.move_history[-1])

    max_repeat = {"Chomp": 1, "Thrash": 2, "Bellow": 1}
    for i in range(len(history)):
        move = history[i]
        run = 1
        j = i - 1
        while j >= 0 and history[j] == move:
            run += 1
            j -= 1
        assert run <= max_repeat[move], (
            f"Jaw Worm move {move!r} repeated {run} times at index {i} (seed {seed})"
        )


def test_jaw_worm_no_chomp_two_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("JawWorm", 42)
        rng = RNG(seed)
        prev = None
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            current = enemy.move_history[-1]
            if prev == "Chomp":
                assert current != "Chomp", f"Chomp followed Chomp (seed={seed}, turn={turn})"
            prev = current


def test_jaw_worm_no_bellow_two_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("JawWorm", 42)
        rng = RNG(seed)
        prev = None
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            current = enemy.move_history[-1]
            if prev == "Bellow":
                assert current != "Bellow", f"Bellow followed Bellow (seed={seed}, turn={turn})"
            prev = current


def test_jaw_worm_no_thrash_three_in_a_row():
    for seed in range(20):
        _check_jaw_worm_constraints(seed)


@pytest.mark.parametrize("seed", range(10))
def test_jaw_worm_constraints_parametrized(seed: int):
    _check_jaw_worm_constraints(seed)


def test_jaw_worm_hp_range():
    for seed in range(30):
        hp = roll_hp("JawWorm", RNG(seed))
        assert 40 <= hp <= 44


def test_jaw_worm_thrash_has_block():
    enemy = _make_enemy("JawWorm", 42)
    rng = RNG(0)
    found_thrash = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if intent.intent_type == IntentType.ATTACK_DEFEND:
            assert intent.block_gain == 5
            assert intent.damage == 7
            found_thrash = True
            break
    assert found_thrash, "No Thrash intent in 30 turns"


def test_jaw_worm_bellow_has_strength_and_block():
    enemy = _make_enemy("JawWorm", 42)
    rng = RNG(0)
    found_bellow = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if intent.intent_type == IntentType.DEFEND and intent.strength_gain > 0:
            assert intent.block_gain == 6
            assert intent.strength_gain == 3
            found_bellow = True
            break
    assert found_bellow, "No Bellow intent in 30 turns"


def test_jaw_worm_all_three_moves_appear():
    """All three Jaw Worm moves should appear within a reasonable number of turns."""
    enemy = _make_enemy("JawWorm", 42)
    rng = RNG(5)
    moves_seen: set[str] = set()
    for turn in range(40):
        pick_intent(enemy, rng, turn=turn)
        moves_seen.add(enemy.move_history[-1])
    assert moves_seen == {"Chomp", "Thrash", "Bellow"}, f"Only saw: {moves_seen}"


# ---------------------------------------------------------------------------
# Acid Slime (M)
# ---------------------------------------------------------------------------
# Source constraints (asc 0):
#   CorrosiveSpit max 2 in a row (lastTwoMoves guard)
#   Tackle        max 1 in a row (lastMove guard)
#   Lick          max 2 in a row (lastTwoMoves guard)

def test_acid_slime_m_first_intent_is_attack_or_debuff():
    """Turn 0 can be any move — Acid Slime M has no first-turn restriction.
    (Unlike Jaw Worm which always Chomps first.)
    The first move is determined purely by the initial roll.
    """
    seen_types: set = set()
    for seed in range(50):
        enemy = _make_enemy("AcidSlimeM", 30)
        intent = pick_intent(enemy, RNG(seed), turn=0)
        seen_types.add(intent.intent_type)
    # Should see attacks and debuffs (Lick) over 50 seeds
    assert IntentType.ATTACK in seen_types or IntentType.ATTACK_DEBUFF in seen_types
    assert IntentType.DEBUFF in seen_types


def test_acid_slime_m_no_tackle_two_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("AcidSlimeM", 30)
        rng = RNG(seed)
        prev = None
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            current = enemy.move_history[-1]
            if prev == "Tackle":
                assert current != "Tackle", (
                    f"Tackle followed Tackle (seed={seed}, turn={turn})"
                )
            prev = current


def _check_acid_slime_constraints(seed: int) -> None:
    enemy = _make_enemy("AcidSlimeM", 30)
    rng = RNG(seed)
    history: list[str] = []
    for turn in range(60):
        pick_intent(enemy, rng, turn=turn)
        history.append(enemy.move_history[-1])

    max_repeat = {"CorrosiveSpit": 2, "Tackle": 1, "Lick": 2}
    for i in range(len(history)):
        move = history[i]
        run = 1
        j = i - 1
        while j >= 0 and history[j] == move:
            run += 1
            j -= 1
        assert run <= max_repeat[move], (
            f"AcidSlimeM move {move!r} repeated {run} times at index {i} (seed {seed})"
        )


@pytest.mark.parametrize("seed", range(10))
def test_acid_slime_m_constraints_parametrized(seed: int):
    _check_acid_slime_constraints(seed)


def test_acid_slime_m_corrosive_spit_adds_slimed():
    """CorrosiveSpit adds 1 Slimed card to discard (not Weak)."""
    enemy = _make_enemy("AcidSlimeM", 30)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "CorrosiveSpit":
            assert intent.applies_weak == 0, "CorrosiveSpit should not apply Weak"
            assert intent.status_card_id == "Slimed"
            assert intent.status_card_count == 1
            found = True
            break
    assert found, "CorrosiveSpit not seen in 40 turns"


def test_acid_slime_m_lick_applies_weak():
    enemy = _make_enemy("AcidSlimeM", 30)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Lick":
            assert intent.applies_weak == 1
            found = True
            break
    assert found, "Lick not seen in 40 turns"


def test_acid_slime_m_tackle_does_not_apply_weak():
    enemy = _make_enemy("AcidSlimeM", 30)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Tackle":
            assert intent.applies_weak == 0
            found = True
            break
    assert found, "Tackle not seen in 40 turns"


def test_acid_slime_m_hp_range():
    for seed in range(30):
        hp = roll_hp("AcidSlimeM", RNG(seed))
        assert 28 <= hp <= 32


def test_acid_slime_m_lick_is_debuff_type():
    enemy = _make_enemy("AcidSlimeM", 30)
    rng = RNG(0)
    found_lick = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        move = enemy.move_history[-1]
        if move == "Lick":
            assert intent.intent_type == IntentType.DEBUFF
            found_lick = True
            break
    assert found_lick, "Lick move not seen in 30 turns"


def test_acid_slime_m_corrosive_spit_is_attack_debuff_type():
    enemy = _make_enemy("AcidSlimeM", 30)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "CorrosiveSpit":
            assert intent.intent_type == IntentType.ATTACK_DEBUFF
            found = True
            break
    assert found, "CorrosiveSpit not seen in 40 turns"


def test_acid_slime_m_all_three_moves_appear():
    enemy = _make_enemy("AcidSlimeM", 30)
    rng = RNG(7)
    moves_seen: set[str] = set()
    for turn in range(40):
        pick_intent(enemy, rng, turn=turn)
        moves_seen.add(enemy.move_history[-1])
    assert moves_seen == {"CorrosiveSpit", "Tackle", "Lick"}, f"Only saw: {moves_seen}"


# ---------------------------------------------------------------------------
# Spike Slime (S)
# ---------------------------------------------------------------------------
# HP 10-14, always TACKLE 5 dmg (no variation, no constraint).

def test_spike_slime_s_hp_range():
    for seed in range(30):
        hp = roll_hp("SpikeSlimeS", RNG(seed))
        assert 10 <= hp <= 14


def test_spike_slime_s_always_tackle():
    enemy = _make_enemy("SpikeSlimeS", 12)
    rng = RNG(0)
    for turn in range(10):
        intent = pick_intent(enemy, rng, turn=turn)
        assert intent.intent_type == IntentType.ATTACK
        assert intent.damage == 5


# ---------------------------------------------------------------------------
# Acid Slime (S)
# ---------------------------------------------------------------------------
# HP 8-12, alternates Tackle (3 dmg) ↔ Lick (Weak 1). First move 50/50.

def test_acid_slime_s_hp_range():
    for seed in range(30):
        hp = roll_hp("AcidSlimeS", RNG(seed))
        assert 8 <= hp <= 12


def test_acid_slime_s_first_move_is_tackle_or_lick():
    seen = set()
    for seed in range(50):
        enemy = _make_enemy("AcidSlimeS", 10)
        intent = pick_intent(enemy, RNG(seed), turn=0)
        seen.add(enemy.move_history[-1])
    assert "Tackle" in seen
    assert "Lick" in seen


def test_acid_slime_s_alternates_tackle_lick():
    """After Tackle it must play Lick, after Lick it must play Tackle."""
    enemy = _make_enemy("AcidSlimeS", 10)
    rng = RNG(0)
    for turn in range(10):
        pick_intent(enemy, rng, turn=turn)

    history = enemy.move_history
    for i in range(1, len(history)):
        assert history[i] != history[i - 1], (
            f"AcidSlimeS played {history[i]} twice in a row at index {i}"
        )


def test_acid_slime_s_lick_applies_weak():
    enemy = _make_enemy("AcidSlimeS", 10)
    rng = RNG(0)
    found = False
    for turn in range(20):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Lick":
            assert intent.applies_weak == 1
            found = True
            break
    assert found, "Lick not seen in 20 turns"


def test_acid_slime_s_lick_is_debuff_type():
    enemy = _make_enemy("AcidSlimeS", 10)
    rng = RNG(0)
    found = False
    for turn in range(20):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Lick":
            assert intent.intent_type == IntentType.DEBUFF
            found = True
            break
    assert found, "Lick not seen in 20 turns"


def test_acid_slime_s_tackle_no_weak():
    enemy = _make_enemy("AcidSlimeS", 10)
    rng = RNG(0)
    found = False
    for turn in range(20):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Tackle":
            assert intent.applies_weak == 0
            assert intent.damage == 3
            found = True
            break
    assert found, "Tackle not seen in 20 turns"


# ---------------------------------------------------------------------------
# Red Louse
# ---------------------------------------------------------------------------
# HP 10-15.  Pre-battle: roll bite dmg 5-7 (into enemy.misc) and Curl Up 3-7.
# Moves: BITE (misc dmg), GROW (+3 str).
# Constraints asc 0: no GROW twice in a row; no BITE twice in a row.
# Source: MonsterSpecific.cpp line ~2585, Monster.cpp line ~115.

def _make_louse(name: str, hp: int = 12) -> EnemyState:
    return EnemyState(name=name, hp=hp, max_hp=hp)


def test_red_louse_hp_range():
    for seed in range(30):
        hp = roll_hp("RedLouse", RNG(seed))
        assert 10 <= hp <= 15


def test_red_louse_pre_battle_sets_misc_and_curl_up():
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    enemy = _make_louse("RedLouse")
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[enemy], rng=RNG(0), turn=0,
    )
    run_pre_battle(enemy, state)
    assert 5 <= enemy.misc <= 7, f"bite dmg out of range: {enemy.misc}"
    assert 3 <= enemy.powers.curl_up <= 7, f"curl_up out of range: {enemy.powers.curl_up}"


def test_red_louse_bite_uses_misc_damage():
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    enemy = _make_louse("RedLouse")
    rng = RNG(0)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[enemy], rng=rng, turn=0,
    )
    run_pre_battle(enemy, state)
    bite_dmg = enemy.misc
    # Seek a Bite intent
    found = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Bite":
            assert intent.damage == bite_dmg
            found = True
            break
    assert found, "Bite not seen in 30 turns"


def test_red_louse_no_grow_or_bite_three_in_a_row():
    """Both Grow and Bite are constrained to max 2 consecutive at asc 0."""
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    for seed in range(20):
        enemy = _make_louse("RedLouse")
        rng = RNG(seed)
        state = CombatState(
            player_hp=80, player_max_hp=80, player_block=0,
            player_powers=Powers(), energy=3,
            piles=Piles(draw=[]), enemies=[enemy], rng=rng, turn=0,
        )
        run_pre_battle(enemy, state)
        history: list[str] = []
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            history.append(enemy.move_history[-1])
        for move in ("Grow", "Bite"):
            for i in range(2, len(history)):
                assert not (history[i] == move and history[i-1] == move and history[i-2] == move), (
                    f"RedLouse {move} appeared 3+ in a row at index {i} (seed={seed})"
                )


# ---------------------------------------------------------------------------
# Green Louse
# ---------------------------------------------------------------------------
# HP 11-17.  Same pre-battle as Red.  Moves: BITE / SPIT_WEB (Weak 2).

def test_green_louse_hp_range():
    for seed in range(30):
        hp = roll_hp("GreenLouse", RNG(seed))
        assert 11 <= hp <= 17


def test_green_louse_spit_web_is_debuff_type():
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    enemy = _make_louse("GreenLouse", hp=14)
    rng = RNG(0)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[enemy], rng=rng, turn=0,
    )
    run_pre_battle(enemy, state)
    found = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "SpitWeb":
            assert intent.intent_type == IntentType.DEBUFF
            found = True
            break
    assert found, "SpitWeb not seen in 30 turns"


def test_green_louse_spit_web_applies_weak_2():
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    enemy = _make_louse("GreenLouse", hp=14)
    rng = RNG(0)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[enemy], rng=rng, turn=0,
    )
    run_pre_battle(enemy, state)
    found = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "SpitWeb":
            assert intent.applies_weak == 2
            found = True
            break
    assert found, "SpitWeb not seen in 30 turns"


def test_green_louse_all_moves_appear():
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    enemy = _make_louse("GreenLouse", hp=14)
    rng = RNG(5)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[enemy], rng=rng, turn=0,
    )
    run_pre_battle(enemy, state)
    moves_seen: set[str] = set()
    for turn in range(40):
        pick_intent(enemy, rng, turn=turn)
        moves_seen.add(enemy.move_history[-1])
    assert moves_seen == {"Bite", "SpitWeb"}, f"Only saw: {moves_seen}"


def test_green_louse_no_spit_web_or_bite_three_in_a_row():
    """Both SpitWeb and Bite are constrained to max 2 consecutive at asc 0."""
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    for seed in range(20):
        enemy = _make_louse("GreenLouse", hp=14)
        rng = RNG(seed)
        state = CombatState(
            player_hp=80, player_max_hp=80, player_block=0,
            player_powers=Powers(), energy=3,
            piles=Piles(draw=[]), enemies=[enemy], rng=rng, turn=0,
        )
        run_pre_battle(enemy, state)
        history: list[str] = []
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            history.append(enemy.move_history[-1])
        for move in ("SpitWeb", "Bite"):
            for i in range(2, len(history)):
                assert not (history[i] == move and history[i-1] == move and history[i-2] == move), (
                    f"GreenLouse {move} appeared 3+ in a row at index {i} (seed={seed})"
                )


# ---------------------------------------------------------------------------
# Fat Gremlin
# ---------------------------------------------------------------------------
# HP 13-17, always SMASH (4 dmg + Weak 1).

def test_fat_gremlin_hp_range():
    for seed in range(30):
        hp = roll_hp("FatGremlin", RNG(seed))
        assert 13 <= hp <= 17


def test_fat_gremlin_always_smash():
    enemy = _make_enemy("FatGremlin", 15)
    rng = RNG(0)
    for turn in range(6):
        intent = pick_intent(enemy, rng, turn=turn)
        assert intent.intent_type == IntentType.ATTACK_DEBUFF
        assert intent.damage == 4
        assert intent.applies_weak == 1


# ---------------------------------------------------------------------------
# Mad Gremlin
# ---------------------------------------------------------------------------
# HP 20-24, pre-battle Angry 1, always SCRATCH (4 dmg).

def test_mad_gremlin_hp_range():
    for seed in range(30):
        hp = roll_hp("MadGremlin", RNG(seed))
        assert 20 <= hp <= 24


def test_mad_gremlin_always_scratch():
    enemy = _make_enemy("MadGremlin", 22)
    rng = RNG(0)
    for turn in range(6):
        intent = pick_intent(enemy, rng, turn=turn)
        assert intent.intent_type == IntentType.ATTACK
        assert intent.damage == 4


def test_mad_gremlin_pre_battle_sets_angry():
    from sts_env.combat.enemies import run_pre_battle
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    enemy = _make_enemy("MadGremlin", 22)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[enemy], rng=RNG(0), turn=0,
    )
    run_pre_battle(enemy, state)
    assert enemy.powers.angry == 1


# ---------------------------------------------------------------------------
# Sneaky Gremlin
# ---------------------------------------------------------------------------
# HP 10-14, always PUNCTURE (9 dmg).

def test_sneaky_gremlin_hp_range():
    for seed in range(30):
        hp = roll_hp("SneakyGremlin", RNG(seed))
        assert 10 <= hp <= 14


def test_sneaky_gremlin_always_puncture():
    enemy = _make_enemy("SneakyGremlin", 12)
    rng = RNG(0)
    for turn in range(6):
        intent = pick_intent(enemy, rng, turn=turn)
        assert intent.intent_type == IntentType.ATTACK
        assert intent.damage == 9


# ---------------------------------------------------------------------------
# Shield Gremlin
# ---------------------------------------------------------------------------
# HP 12-15. PROTECT: ally_block_gain 7 to a random alive ally.
# When alone (no live ally at intent-pick time): SHIELD_BASH (6 dmg instead).

def test_shield_gremlin_hp_range():
    for seed in range(30):
        hp = roll_hp("ShieldGremlin", RNG(seed))
        assert 12 <= hp <= 15


def test_shield_gremlin_protect_with_ally():
    """With a live ally present, ShieldGremlin picks PROTECT (ally_block_gain)."""
    from sts_env.combat.enemies import pick_intent_with_state
    from sts_env.combat.state import CombatState, EnemyState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    ally = EnemyState(name="MadGremlin", hp=20, max_hp=20)
    shield = _make_enemy("ShieldGremlin", 14)
    rng = RNG(0)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[shield, ally], rng=rng, turn=0,
    )
    intent = pick_intent_with_state(shield, rng, turn=0, state=state, enemy_index=0)
    assert intent.ally_block_gain == 7
    assert intent.damage == 0


def test_shield_gremlin_shield_bash_when_alone():
    """With no live ally, ShieldGremlin picks SHIELD_BASH (6 dmg)."""
    from sts_env.combat.enemies import pick_intent_with_state
    from sts_env.combat.state import CombatState
    from sts_env.combat.deck import Piles
    from sts_env.combat.powers import Powers
    shield = _make_enemy("ShieldGremlin", 14)
    rng = RNG(0)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[shield], rng=rng, turn=0,
    )
    intent = pick_intent_with_state(shield, rng, turn=0, state=state, enemy_index=0)
    assert intent.intent_type == IntentType.ATTACK
    assert intent.damage == 6
    assert intent.ally_block_gain == 0


# ---------------------------------------------------------------------------
# Gremlin Wizard
# ---------------------------------------------------------------------------
# HP 21-25. Charges for 3 turns (misc counter 1→2→3), then ULTIMATE_BLAST 25 dmg.
# After blast, resets counter and charges again.
# Source: MonsterSpecific.cpp line ~2438.

def test_gremlin_wizard_hp_range():
    for seed in range(30):
        hp = roll_hp("GremlinWizard", RNG(seed))
        assert 21 <= hp <= 25


def test_gremlin_wizard_charges_three_turns_then_blasts():
    """Turns 0-2: CHARGING intent. Turn 3: ULTIMATE_BLAST (25 dmg). Then resets."""
    enemy = _make_enemy("GremlinWizard", 23)
    rng = RNG(0)
    intents = [pick_intent(enemy, rng, turn=t) for t in range(7)]
    # Turns 0,1,2 → CHARGING; turn 3 → BLAST; turns 4,5,6 → CHARGING again
    for t in (0, 1, 2, 4, 5, 6):
        assert intents[t].intent_type == IntentType.BUFF, (
            f"Expected CHARGING at turn {t}, got {intents[t].intent_type}"
        )
    assert intents[3].intent_type == IntentType.ATTACK
    assert intents[3].damage == 25


def test_gremlin_wizard_misc_increments_during_charging():
    enemy = _make_enemy("GremlinWizard", 23)
    rng = RNG(0)
    assert enemy.misc == 0
    pick_intent(enemy, rng, turn=0)
    assert enemy.misc == 1
    pick_intent(enemy, rng, turn=1)
    assert enemy.misc == 2
    pick_intent(enemy, rng, turn=2)
    assert enemy.misc == 3
    pick_intent(enemy, rng, turn=3)  # blast → resets
    assert enemy.misc == 0


# ---------------------------------------------------------------------------
# Spike Slime (M)
# ---------------------------------------------------------------------------
# HP 28-32.  FlameTackle (8 dmg + 1 Slimed to discard), Lick (Frail 1).
# Constraints asc 0: FlameTackle max 2 in a row, Lick max 2 in a row.
# Source: MonsterSpecific.cpp line ~2822

def test_spike_slime_m_hp_range():
    for seed in range(30):
        hp = roll_hp("SpikeSlimeM", RNG(seed))
        assert 28 <= hp <= 32, f"SpikeSlimeM HP {hp} out of range (seed={seed})"


def test_spike_slime_m_flame_tackle_damage_and_slimed():
    enemy = _make_enemy("SpikeSlimeM", 30)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "FlameTackle":
            assert intent.intent_type == IntentType.ATTACK_DEBUFF
            assert intent.damage == 8
            assert intent.status_card_id == "Slimed"
            assert intent.status_card_count == 1
            found = True
            break
    assert found, "FlameTackle not seen in 40 turns"


def test_spike_slime_m_lick_applies_frail():
    enemy = _make_enemy("SpikeSlimeM", 30)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Lick":
            assert intent.intent_type == IntentType.DEBUFF
            assert intent.applies_frail == 1
            found = True
            break
    assert found, "Lick not seen in 40 turns"


def test_spike_slime_m_no_flame_tackle_three_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("SpikeSlimeM", 30)
        rng = RNG(seed)
        history: list[str] = []
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            history.append(enemy.move_history[-1])
        for i in range(2, len(history)):
            assert not (history[i] == "FlameTackle" and history[i-1] == "FlameTackle" and history[i-2] == "FlameTackle"), (
                f"SpikeSlimeM FlameTackle 3 in a row at index {i} (seed={seed})"
            )


def test_spike_slime_m_no_lick_three_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("SpikeSlimeM", 30)
        rng = RNG(seed)
        history: list[str] = []
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            history.append(enemy.move_history[-1])
        for i in range(2, len(history)):
            assert not (history[i] == "Lick" and history[i-1] == "Lick" and history[i-2] == "Lick"), (
                f"SpikeSlimeM Lick 3 in a row at index {i} (seed={seed})"
            )


def test_spike_slime_m_all_moves_appear():
    enemy = _make_enemy("SpikeSlimeM", 30)
    rng = RNG(5)
    moves_seen: set[str] = set()
    for turn in range(40):
        pick_intent(enemy, rng, turn=turn)
        moves_seen.add(enemy.move_history[-1])
    assert moves_seen == {"FlameTackle", "Lick"}, f"Only saw: {moves_seen}"


# ---------------------------------------------------------------------------
# Spike Slime (L)
# ---------------------------------------------------------------------------
# HP 64-70.  FlameTackle (16 dmg + 2 Slimed), Lick (Frail 2).
# Splits at <= 50% HP.
# Constraints asc 0: FlameTackle max 2 in a row, Lick max 1 in a row.
# Source: MonsterSpecific.cpp line ~2801

def test_spike_slime_l_hp_range():
    for seed in range(30):
        hp = roll_hp("SpikeSlimeL", RNG(seed))
        assert 64 <= hp <= 70, f"SpikeSlimeL HP {hp} out of range (seed={seed})"


def test_spike_slime_l_flame_tackle_damage_and_slimed():
    enemy = _make_enemy("SpikeSlimeL", 67)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "FlameTackle":
            assert intent.intent_type == IntentType.ATTACK_DEBUFF
            assert intent.damage == 16
            assert intent.status_card_id == "Slimed"
            assert intent.status_card_count == 2
            found = True
            break
    assert found, "FlameTackle not seen in 40 turns"


def test_spike_slime_l_lick_applies_frail_2():
    enemy = _make_enemy("SpikeSlimeL", 67)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Lick":
            assert intent.intent_type == IntentType.DEBUFF
            assert intent.applies_frail == 2
            found = True
            break
    assert found, "Lick not seen in 40 turns"


def test_spike_slime_l_no_flame_tackle_three_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("SpikeSlimeL", 67)
        rng = RNG(seed)
        history: list[str] = []
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            history.append(enemy.move_history[-1])
        for i in range(2, len(history)):
            assert not (history[i] == "FlameTackle" and history[i-1] == "FlameTackle" and history[i-2] == "FlameTackle"), (
                f"SpikeSlimeL FlameTackle 3 in a row at index {i} (seed={seed})"
            )


def test_spike_slime_l_no_lick_two_in_a_row():
    """SpikeSlimeL Lick constrained to max 1 in a row (asc 0)."""
    for seed in range(20):
        enemy = _make_enemy("SpikeSlimeL", 67)
        rng = RNG(seed)
        prev = None
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            current = enemy.move_history[-1]
            if prev == "Lick":
                assert current != "Lick", (
                    f"SpikeSlimeL Lick followed Lick (seed={seed}, turn={turn})"
                )
            prev = current


# ---------------------------------------------------------------------------
# Acid Slime (L)
# ---------------------------------------------------------------------------
# HP 65-69.  CorrosiveSpit (11 dmg + 2 Slimed), Tackle (16 dmg), Lick (Weak 2).
# Splits at <= 50% HP.
# Constraints asc 0: CorrosiveSpit max 2 in a row, Tackle max 1 in a row, Lick max 1 in a row.
# Source: MonsterSpecific.cpp line ~1978, 2016+

def test_acid_slime_l_hp_range():
    for seed in range(30):
        hp = roll_hp("AcidSlimeL", RNG(seed))
        assert 65 <= hp <= 69, f"AcidSlimeL HP {hp} out of range (seed={seed})"


def test_acid_slime_l_corrosive_spit_damage_and_slimed():
    enemy = _make_enemy("AcidSlimeL", 67)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "CorrosiveSpit":
            assert intent.intent_type == IntentType.ATTACK_DEBUFF
            assert intent.damage == 11
            assert intent.status_card_id == "Slimed"
            assert intent.status_card_count == 2
            found = True
            break
    assert found, "CorrosiveSpit not seen in 40 turns"


def test_acid_slime_l_tackle_damage():
    enemy = _make_enemy("AcidSlimeL", 67)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Tackle":
            assert intent.intent_type == IntentType.ATTACK
            assert intent.damage == 16
            assert intent.status_card_count == 0
            found = True
            break
    assert found, "Tackle not seen in 40 turns"


def test_acid_slime_l_lick_applies_weak_2():
    enemy = _make_enemy("AcidSlimeL", 67)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Lick":
            assert intent.intent_type == IntentType.DEBUFF
            assert intent.applies_weak == 2
            found = True
            break
    assert found, "Lick not seen in 40 turns"


def test_acid_slime_l_no_tackle_two_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("AcidSlimeL", 67)
        rng = RNG(seed)
        prev = None
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            current = enemy.move_history[-1]
            if prev == "Tackle":
                assert current != "Tackle", (
                    f"AcidSlimeL Tackle followed Tackle (seed={seed}, turn={turn})"
                )
            prev = current


def test_acid_slime_l_no_lick_two_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("AcidSlimeL", 67)
        rng = RNG(seed)
        prev = None
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            current = enemy.move_history[-1]
            if prev == "Lick":
                assert current != "Lick", (
                    f"AcidSlimeL Lick followed Lick (seed={seed}, turn={turn})"
                )
            prev = current


def test_acid_slime_l_no_corrosive_spit_three_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("AcidSlimeL", 67)
        rng = RNG(seed)
        history: list[str] = []
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
            history.append(enemy.move_history[-1])
        for i in range(2, len(history)):
            assert not (history[i] == "CorrosiveSpit" and history[i-1] == "CorrosiveSpit" and history[i-2] == "CorrosiveSpit"), (
                f"AcidSlimeL CorrosiveSpit 3 in a row at index {i} (seed={seed})"
            )


def test_acid_slime_l_all_moves_appear():
    enemy = _make_enemy("AcidSlimeL", 67)
    rng = RNG(7)
    moves_seen: set[str] = set()
    for turn in range(40):
        pick_intent(enemy, rng, turn=turn)
        moves_seen.add(enemy.move_history[-1])
    assert moves_seen == {"CorrosiveSpit", "Tackle", "Lick"}, f"Only saw: {moves_seen}"


# ===========================================================================
# Blue Slaver
# ===========================================================================

def test_blue_slaver_hp_range():
    for seed in range(30):
        hp = roll_hp("BlueSlaver", RNG(seed))
        assert 46 <= hp <= 50, f"BlueSlaver HP {hp} out of range (seed={seed})"


def test_blue_slaver_stab_damage():
    enemy = _make_enemy("BlueSlaver", 48)
    rng = RNG(0)
    found = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Stab":
            assert intent.intent_type == IntentType.ATTACK
            assert intent.damage == 12
            assert intent.applies_weak == 0
            found = True
            break
    assert found, "Stab not seen in 30 turns"


def test_blue_slaver_rake_is_attack_debuff():
    enemy = _make_enemy("BlueSlaver", 48)
    rng = RNG(0)
    found = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Rake":
            assert intent.intent_type == IntentType.ATTACK_DEBUFF
            assert intent.damage == 7
            assert intent.applies_weak == 1
            found = True
            break
    assert found, "Rake not seen in 30 turns"


def test_blue_slaver_no_rake_three_in_a_row():
    for seed in range(30):
        enemy = _make_enemy("BlueSlaver", 48)
        rng = RNG(seed)
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
        history = enemy.move_history
        for i in range(2, len(history)):
            assert not (
                history[i] == "Rake"
                and history[i - 1] == "Rake"
                and history[i - 2] == "Rake"
            ), f"BlueSlaver Rake 3× in a row at turn {i} (seed={seed})"


def test_blue_slaver_both_moves_appear():
    enemy = _make_enemy("BlueSlaver", 48)
    rng = RNG(0)
    seen: set[str] = set()
    for turn in range(40):
        pick_intent(enemy, rng, turn=turn)
        seen.add(enemy.move_history[-1])
    assert "Stab" in seen
    assert "Rake" in seen


# ===========================================================================
# Red Slaver
# ===========================================================================

def test_red_slaver_hp_range():
    for seed in range(30):
        hp = roll_hp("RedSlaver", RNG(seed))
        assert 46 <= hp <= 50, f"RedSlaver HP {hp} out of range (seed={seed})"


def test_red_slaver_first_move_is_stab():
    for seed in range(10):
        enemy = _make_enemy("RedSlaver", 48)
        intent = pick_intent(enemy, RNG(seed), turn=0)
        assert intent.intent_type == IntentType.ATTACK
        assert intent.damage == 13
        assert enemy.move_history[-1] == "Stab"


def test_red_slaver_entangle_is_debuff():
    enemy = _make_enemy("RedSlaver", 48)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Entangle":
            assert intent.intent_type == IntentType.DEBUFF
            assert intent.applies_entangle == 1
            found = True
            break
    assert found, "Entangle not seen in 40 turns"


def test_red_slaver_entangle_used_at_most_once():
    for seed in range(20):
        enemy = _make_enemy("RedSlaver", 48)
        rng = RNG(seed)
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
        entangle_count = enemy.move_history.count("Entangle")
        assert entangle_count <= 1, (
            f"RedSlaver used Entangle {entangle_count}× (seed={seed})"
        )


def test_red_slaver_scrape_applies_vulnerable():
    enemy = _make_enemy("RedSlaver", 48)
    rng = RNG(0)
    found = False
    for turn in range(40):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Scrape":
            assert intent.intent_type == IntentType.ATTACK_DEBUFF
            assert intent.damage == 8
            assert intent.applies_vulnerable == 1
            found = True
            break
    assert found, "Scrape not seen in 40 turns"


def test_red_slaver_no_scrape_three_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("RedSlaver", 48)
        rng = RNG(seed)
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
        history = enemy.move_history
        for i in range(2, len(history)):
            assert not (
                history[i] == "Scrape"
                and history[i - 1] == "Scrape"
                and history[i - 2] == "Scrape"
            ), f"RedSlaver Scrape 3× in a row at turn {i} (seed={seed})"


# ===========================================================================
# Fungi Beast
# ===========================================================================

def test_fungi_beast_hp_range():
    for seed in range(30):
        hp = roll_hp("FungiBeast", RNG(seed))
        assert 22 <= hp <= 28, f"FungiBeast HP {hp} out of range (seed={seed})"


def test_fungi_beast_bite_damage():
    enemy = _make_enemy("FungiBeast", 25)
    rng = RNG(0)
    found = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Bite":
            assert intent.intent_type == IntentType.ATTACK
            assert intent.damage == 6
            found = True
            break
    assert found, "Bite not seen in 30 turns"


def test_fungi_beast_grow_is_buff():
    enemy = _make_enemy("FungiBeast", 25)
    rng = RNG(0)
    found = False
    for turn in range(30):
        intent = pick_intent(enemy, rng, turn=turn)
        if enemy.move_history[-1] == "Grow":
            assert intent.intent_type == IntentType.BUFF
            assert intent.strength_gain == 3
            found = True
            break
    assert found, "Grow not seen in 30 turns"


def test_fungi_beast_no_bite_three_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("FungiBeast", 25)
        rng = RNG(seed)
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
        history = enemy.move_history
        for i in range(2, len(history)):
            assert not (
                history[i] == "Bite"
                and history[i - 1] == "Bite"
                and history[i - 2] == "Bite"
            ), f"FungiBeast Bite 3× in a row at turn {i} (seed={seed})"


def test_fungi_beast_no_grow_two_in_a_row():
    for seed in range(20):
        enemy = _make_enemy("FungiBeast", 25)
        rng = RNG(seed)
        for turn in range(40):
            pick_intent(enemy, rng, turn=turn)
        history = enemy.move_history
        for i in range(1, len(history)):
            assert not (
                history[i] == "Grow" and history[i - 1] == "Grow"
            ), f"FungiBeast Grow 2× in a row at turn {i} (seed={seed})"


def test_fungi_beast_spore_cloud_set_in_pre_battle():
    from sts_env.combat.state import CombatState, EnemyState
    from sts_env.combat.powers import Powers
    from sts_env.combat.deck import Piles
    from sts_env.combat.enemies import run_pre_battle

    enemy = _make_enemy("FungiBeast", 25)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3, piles=Piles(draw=[]),
        enemies=[enemy], rng=RNG(0),
    )
    run_pre_battle(enemy, state)
    assert enemy.powers.spore_cloud == 2


# ===========================================================================
# Looter
# ===========================================================================

def test_looter_hp_range():
    for seed in range(30):
        hp = roll_hp("Looter", RNG(seed))
        assert 44 <= hp <= 48, f"Looter HP {hp} out of range (seed={seed})"


def test_looter_first_two_moves_are_mug():
    enemy = _make_enemy("Looter", 46)
    rng = RNG(0)
    for turn in range(2):
        intent = pick_intent(enemy, rng, turn=turn)
        assert intent.intent_type == IntentType.ATTACK
        assert intent.damage == 10
        assert enemy.move_history[-1] == "Mug"


def test_looter_branches_after_two_mugs():
    for seed in range(20):
        enemy = _make_enemy("Looter", 46)
        rng = RNG(seed)
        pick_intent(enemy, rng, turn=0)  # Mug
        pick_intent(enemy, rng, turn=1)  # Mug
        intent = pick_intent(enemy, rng, turn=2)  # SmokeBomb or Lunge
        assert enemy.move_history[-1] in {"SmokeBomb", "Lunge"}


def test_looter_smoke_bomb_gives_block():
    found = False
    for seed in range(20):
        enemy = _make_enemy("Looter", 46)
        rng = RNG(seed)
        pick_intent(enemy, rng, turn=0)
        pick_intent(enemy, rng, turn=1)
        intent = pick_intent(enemy, rng, turn=2)
        if enemy.move_history[-1] == "SmokeBomb":
            assert intent.intent_type == IntentType.DEFEND
            assert intent.block_gain == 6
            found = True
            break
    assert found, "SmokeBomb not reached in 20 seeds"


def test_looter_lunge_is_attack():
    found = False
    for seed in range(20):
        enemy = _make_enemy("Looter", 46)
        rng = RNG(seed)
        pick_intent(enemy, rng, turn=0)
        pick_intent(enemy, rng, turn=1)
        intent = pick_intent(enemy, rng, turn=2)
        if enemy.move_history[-1] == "Lunge":
            assert intent.intent_type == IntentType.ATTACK
            assert intent.damage == 12
            found = True
            break
    assert found, "Lunge not reached in 20 seeds"


def test_looter_escape_follows_smoke_bomb():
    from sts_env.combat.enemies import IntentType
    found = False
    for seed in range(20):
        enemy = _make_enemy("Looter", 46)
        rng = RNG(seed)
        pick_intent(enemy, rng, turn=0)
        pick_intent(enemy, rng, turn=1)
        intent3 = pick_intent(enemy, rng, turn=2)
        if enemy.move_history[-1] == "SmokeBomb":
            intent4 = pick_intent(enemy, rng, turn=3)
            assert enemy.move_history[-1] == "Escape"
            assert intent4.intent_type == IntentType.ESCAPE
            found = True
            break
    assert found, "SmokeBomb→Escape path not found in 20 seeds"


def test_looter_escape_follows_lunge_then_smoke_bomb():
    from sts_env.combat.enemies import IntentType
    found = False
    for seed in range(20):
        enemy = _make_enemy("Looter", 46)
        rng = RNG(seed)
        pick_intent(enemy, rng, turn=0)
        pick_intent(enemy, rng, turn=1)
        intent3 = pick_intent(enemy, rng, turn=2)
        if enemy.move_history[-1] == "Lunge":
            intent4 = pick_intent(enemy, rng, turn=3)
            assert enemy.move_history[-1] == "SmokeBomb"
            intent5 = pick_intent(enemy, rng, turn=4)
            assert enemy.move_history[-1] == "Escape"
            assert intent5.intent_type == IntentType.ESCAPE
            found = True
            break
    assert found, "Lunge→SmokeBomb→Escape path not found in 20 seeds"


# ===========================================================================
# Mugger
# ===========================================================================

def test_mugger_hp_range():
    for seed in range(30):
        hp = roll_hp("Mugger", RNG(seed))
        assert 48 <= hp <= 52, f"Mugger HP {hp} out of range (seed={seed})"


def test_mugger_first_two_moves_are_mug():
    enemy = _make_enemy("Mugger", 50)
    rng = RNG(0)
    for turn in range(2):
        intent = pick_intent(enemy, rng, turn=turn)
        assert intent.intent_type == IntentType.ATTACK
        assert intent.damage == 10
        assert enemy.move_history[-1] == "Mug"


def test_mugger_smoke_bomb_higher_block_than_looter():
    found = False
    for seed in range(20):
        enemy = _make_enemy("Mugger", 50)
        rng = RNG(seed)
        pick_intent(enemy, rng, turn=0)
        pick_intent(enemy, rng, turn=1)
        intent = pick_intent(enemy, rng, turn=2)
        if enemy.move_history[-1] == "SmokeBomb":
            assert intent.block_gain == 11  # Mugger has 11 block vs Looter's 6
            found = True
            break
    assert found, "SmokeBomb not reached in 20 seeds"


def test_mugger_lunge_higher_damage_than_looter():
    found = False
    for seed in range(20):
        enemy = _make_enemy("Mugger", 50)
        rng = RNG(seed)
        pick_intent(enemy, rng, turn=0)
        pick_intent(enemy, rng, turn=1)
        intent = pick_intent(enemy, rng, turn=2)
        if enemy.move_history[-1] == "Lunge":
            assert intent.damage == 16  # Mugger has 16 dmg vs Looter's 12
            found = True
            break
    assert found, "Lunge not reached in 20 seeds"
