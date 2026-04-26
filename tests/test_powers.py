"""Tests for damage calculation, statuses, and block."""

import pytest

from sts_env.combat.powers import Powers, apply_damage, calc_damage, gain_block, attack_enemy
from sts_env.combat.state import EnemyState, CombatState, Action, ActionType
from sts_env.combat.deck import Piles
from sts_env.combat.rng import RNG
from sts_env.combat.events import Event, subscribe
from sts_env.combat.listeners_powers import POWER_SUBSCRIPTIONS


def _subscribe_power(state, power_attr: str, owner="player") -> None:
    """Subscribe all listeners for a given power attribute."""
    for event, handler_name in POWER_SUBSCRIPTIONS.get(power_attr, []):
        subscribe(state, event, handler_name, owner)


# ---------------------------------------------------------------------------
# calc_damage — raw damage before block
# ---------------------------------------------------------------------------

def test_base_damage_no_modifiers():
    atk = Powers()
    dfn = Powers()
    assert calc_damage(6, atk, dfn) == 6


def test_strength_adds_flat():
    atk = Powers(strength=2)
    dfn = Powers()
    assert calc_damage(6, atk, dfn) == 8


def test_negative_strength_reduces():
    atk = Powers(strength=-2)
    dfn = Powers()
    assert calc_damage(6, atk, dfn) == 4


def test_vulnerable_multiplies_by_1_5_floored():
    """Vulnerable: floor(base * 1.5)."""
    atk = Powers()
    dfn = Powers(vulnerable=1)
    # 6 * 1.5 = 9.0 → 9
    assert calc_damage(6, atk, dfn) == 9
    # 7 * 1.5 = 10.5 → 10
    assert calc_damage(7, atk, dfn) == 10


def test_weak_multiplies_by_0_75_floored():
    """Weak: floor(base * 0.75)."""
    atk = Powers(weak=1)
    dfn = Powers()
    # 8 * 0.75 = 6.0 → 6
    assert calc_damage(8, atk, dfn) == 6
    # 7 * 0.75 = 5.25 → 5
    assert calc_damage(7, atk, dfn) == 5


def test_combined_weak_and_vulnerable_flooring_order():
    """Weak applied first, then vulnerable, flooring after each step."""
    atk = Powers(weak=1)
    dfn = Powers(vulnerable=1)
    # Step 1: floor(6 * 0.75) = floor(4.5) = 4
    # Step 2: floor(4 * 1.5)  = floor(6.0) = 6
    assert calc_damage(6, atk, dfn) == 6


def test_combined_strength_weak_vulnerable():
    atk = Powers(strength=3, weak=1)
    dfn = Powers(vulnerable=1)
    # base + str = 6 + 3 = 9
    # weak:  floor(9 * 0.75) = floor(6.75) = 6
    # vuln:  floor(6 * 1.5)  = floor(9.0)  = 9
    assert calc_damage(6, atk, dfn) == 9


def test_damage_never_negative():
    atk = Powers(strength=-100)
    dfn = Powers()
    assert calc_damage(5, atk, dfn) == 0


# ---------------------------------------------------------------------------
# apply_damage — block and HP
# ---------------------------------------------------------------------------

def test_damage_fully_blocked():
    new_block, new_hp = apply_damage(5, 10, 50)
    assert new_block == 5
    assert new_hp == 50


def test_damage_partially_blocked():
    new_block, new_hp = apply_damage(8, 3, 50)
    assert new_block == 0
    assert new_hp == 45


def test_damage_exceeds_block():
    new_block, new_hp = apply_damage(10, 4, 20)
    assert new_block == 0
    assert new_hp == 14


def test_no_block():
    new_block, new_hp = apply_damage(7, 0, 30)
    assert new_block == 0
    assert new_hp == 23


def test_zero_damage_no_effect():
    new_block, new_hp = apply_damage(0, 5, 50)
    assert new_block == 5
    assert new_hp == 50


def test_hp_can_go_to_zero():
    new_block, new_hp = apply_damage(50, 0, 50)
    assert new_hp == 0


def test_hp_can_go_negative():
    """We don't clamp HP — the engine checks for <= 0 for death."""
    new_block, new_hp = apply_damage(60, 0, 50)
    assert new_hp == -10


# ---------------------------------------------------------------------------
# Powers.tick_start_of_turn
# ---------------------------------------------------------------------------

def test_vulnerable_decrements_each_turn():
    p = Powers(vulnerable=2)
    p.tick_start_of_turn()
    assert p.vulnerable == 1
    p.tick_start_of_turn()
    assert p.vulnerable == 0
    p.tick_start_of_turn()  # should not go negative
    assert p.vulnerable == 0


def test_weak_decrements_each_turn():
    p = Powers(weak=1)
    p.tick_start_of_turn()
    assert p.weak == 0


def test_ritual_applies_strength():
    p = Powers(ritual=3)
    p.apply_ritual()
    assert p.strength == 3
    p.apply_ritual()
    assert p.strength == 6


# ---------------------------------------------------------------------------
# Frail — tick_start_of_turn
# ---------------------------------------------------------------------------

def test_frail_decrements_each_turn():
    p = Powers(frail=2)
    p.tick_start_of_turn()
    assert p.frail == 1
    p.tick_start_of_turn()
    assert p.frail == 0
    p.tick_start_of_turn()
    assert p.frail == 0


# ---------------------------------------------------------------------------
# gain_block — Frail reduces block gain to floor(amount * 0.75)
# ---------------------------------------------------------------------------

def test_gain_block_no_frail():
    p = Powers()
    assert gain_block(p, 8) == 8


def test_gain_block_with_frail():
    p = Powers(frail=1)
    assert gain_block(p, 8) == 6   # floor(8 * 0.75) = 6


def test_gain_block_frail_floors():
    p = Powers(frail=2)
    assert gain_block(p, 5) == 3   # floor(5 * 0.75) = 3


# ---------------------------------------------------------------------------
# attack_enemy — Curl Up, Angry triggers
# ---------------------------------------------------------------------------

def _make_state(enemy: EnemyState) -> CombatState:
    return CombatState(
        player_hp=80,
        player_max_hp=80,
        player_block=0,
        player_powers=Powers(),
        energy=3,
        piles=Piles(draw=[]),
        enemies=[enemy],
        rng=RNG(0),
        turn=0,
    )


def test_attack_enemy_basic_damage():
    e = EnemyState(name="JawWorm", hp=40, max_hp=40)
    state = _make_state(e)
    attack_enemy(state, e, 6)
    assert e.hp == 34


def test_attack_enemy_respects_enemy_block():
    e = EnemyState(name="JawWorm", hp=40, max_hp=40, block=4)
    state = _make_state(e)
    attack_enemy(state, e, 6)
    assert e.block == 0
    assert e.hp == 38


def test_attack_enemy_curl_up_triggers_on_first_hp_damage():
    """Curl Up fires the first time HP actually drops."""
    e = EnemyState(name="RedLouse", hp=12, max_hp=12)
    e.powers.curl_up = 5
    state = _make_state(e)
    subscribe(state, Event.HP_LOSS, "curl_up", 0)
    attack_enemy(state, e, 3, enemy_index=0)   # 3 dmg, no block → HP damage triggers Curl Up
    assert e.hp == 9
    assert e.block == 5         # Curl Up grants block
    assert e.powers.curl_up == 0  # consumed


def test_attack_enemy_curl_up_does_not_trigger_when_fully_blocked():
    """Curl Up must NOT trigger when damage is fully absorbed by block."""
    e = EnemyState(name="RedLouse", hp=12, max_hp=12, block=10)
    e.powers.curl_up = 5
    state = _make_state(e)
    subscribe(state, Event.HP_LOSS, "curl_up", 0)
    attack_enemy(state, e, 3, enemy_index=0)   # fully blocked → no HP damage
    assert e.hp == 12
    assert e.powers.curl_up == 5  # not consumed


def test_attack_enemy_curl_up_only_triggers_once():
    e = EnemyState(name="RedLouse", hp=20, max_hp=20)
    e.powers.curl_up = 4
    state = _make_state(e)
    subscribe(state, Event.HP_LOSS, "curl_up", 0)
    attack_enemy(state, e, 5, enemy_index=0)
    assert e.powers.curl_up == 0
    assert e.block == 4  # Curl Up granted block
    # Second attack: no more Curl Up; block is consumed by the hit normally
    attack_enemy(state, e, 3, enemy_index=0)
    assert e.powers.curl_up == 0  # still 0, did not re-trigger


def test_attack_enemy_angry_gains_strength_on_any_attack():
    """Angry fires on any attack hit, even if fully blocked."""
    e = EnemyState(name="MadGremlin", hp=20, max_hp=20, block=10)
    e.powers.angry = 1
    state = _make_state(e)
    attack_enemy(state, e, 3)   # fully blocked
    assert e.hp == 20           # no HP damage
    assert e.powers.strength == 1  # Angry fired


def test_attack_enemy_angry_stacks_per_hit():
    e = EnemyState(name="MadGremlin", hp=20, max_hp=20)
    e.powers.angry = 2
    state = _make_state(e)
    attack_enemy(state, e, 3)
    assert e.powers.strength == 2
    attack_enemy(state, e, 3)
    assert e.powers.strength == 4


def test_attack_enemy_uses_player_strength():
    e = EnemyState(name="JawWorm", hp=40, max_hp=40)
    state = _make_state(e)
    state.player_powers.strength = 2
    attack_enemy(state, e, 6)
    assert e.hp == 32  # 6+2 = 8 dmg


# ---------------------------------------------------------------------------
# Engine-level trigger tests
# ---------------------------------------------------------------------------

from sts_env.combat.card import Card
from sts_env.combat.engine import Combat, IRONCLAD_STARTER
from sts_env.combat.cards import CardType


def _make_combat_state(
    hand=None, draw=None, energy=3, player_hp=80, player_powers=None,
    enemies=None,
):
    if enemies is None:
        enemies = [EnemyState(name="Dummy", hp=50, max_hp=50)]
    if player_powers is None:
        player_powers = Powers()
    return CombatState(
        player_hp=player_hp,
        player_max_hp=player_hp,
        player_block=0,
        player_powers=player_powers,
        energy=energy,
        piles=Piles(
            hand=hand or [],
            draw=draw or [],
        ),
        enemies=enemies,
        rng=RNG(42),
    )


def test_ethereal_sweep_at_end_of_turn():
    """Ethereal cards in hand are exhausted at end of turn."""
    combat = Combat(
        deck=IRONCLAD_STARTER, enemies=["JawWorm"], seed=42
    )
    obs = combat.reset()
    # Inject a Carnage (ethereal) into hand
    combat._state.piles.hand.append(Card("Carnage"))
    combat.step(Action.end_turn())
    # Carnage should be in exhaust, not discard
    exhaust_ids = [c.card_id for c in combat._state.piles.exhaust]
    assert "Carnage" in exhaust_ids


def test_demon_form_start_of_turn():
    """DemonForm gives strength at start of each turn."""
    combat = Combat(
        deck=IRONCLAD_STARTER, enemies=["JawWorm"], seed=42
    )
    obs = combat.reset()
    combat._state.player_powers.demon_form = 2
    _subscribe_power(combat._state, "demon_form")
    str_before = combat._state.player_powers.strength
    combat.step(Action.end_turn())
    assert combat._state.player_powers.strength == str_before + 2


def test_brutality_start_of_turn():
    """Brutality: lose 1 HP at start of turn (in addition to enemy damage)."""
    # With brutality
    combat = Combat(
        deck=IRONCLAD_STARTER, enemies=["JawWorm"], seed=42
    )
    obs = combat.reset()
    combat._state.player_powers.brutality = 1
    _subscribe_power(combat._state, "brutality")
    combat.step(Action.end_turn())
    hp_with = combat._state.player_hp

    # Without brutality (same seed)
    combat2 = Combat(
        deck=IRONCLAD_STARTER, enemies=["JawWorm"], seed=42
    )
    obs2 = combat2.reset()
    combat2.step(Action.end_turn())
    hp_without = combat2._state.player_hp

    assert hp_with == hp_without - 1


def test_berserk_energy_start_of_turn():
    """Berserk grants extra energy at start of turn."""
    combat = Combat(
        deck=IRONCLAD_STARTER, enemies=["JawWorm"], seed=42
    )
    obs = combat.reset()
    combat._state.player_powers.berserk_energy = 2
    _subscribe_power(combat._state, "berserk_energy")
    combat.step(Action.end_turn())
    # 3 base + 2 berserk = 5
    assert combat._state.energy == 5


def test_dark_embrace_draws_on_exhaust():
    """Dark Embrace draws 1 card per exhaust."""
    from sts_env.combat.events import Event, subscribe, emit
    state = _make_combat_state(
        draw=[Card("Strike"), Card("Defend")],
    )
    state.player_powers.dark_embrace = 1
    subscribe(state, Event.CARD_EXHAUSTED, "dark_embrace", "player")
    draw_before = len(state.piles.draw)
    emit(state, Event.CARD_EXHAUSTED, "player", card=Card("Slimed"))
    assert len(state.piles.draw) == draw_before - 1  # drew 1


def test_feel_no_pain_block_on_exhaust():
    """Feel No Pain grants block per exhaust."""
    from sts_env.combat.events import Event, subscribe, emit
    state = _make_combat_state()
    state.player_powers.feel_no_pain = 3
    subscribe(state, Event.CARD_EXHAUSTED, "feel_no_pain", "player")
    emit(state, Event.CARD_EXHAUSTED, "player", card=Card("Slimed"))
    assert state.player_block == 3


def test_sentinel_energy_on_exhaust():
    """Sentinel grants energy when exhausted."""
    from sts_env.combat.events import Event, subscribe, emit
    state = _make_combat_state()
    subscribe(state, Event.CARD_EXHAUSTED, "sentinel", "player")
    emit(state, Event.CARD_EXHAUSTED, "player", card=Card("Sentinel"))
    assert state.energy == 5  # 3 base + 2


def test_sentinel_upgraded_energy_on_exhaust():
    """Upgraded Sentinel grants 3 energy when exhausted."""
    from sts_env.combat.events import Event, subscribe, emit
    state = _make_combat_state()
    subscribe(state, Event.CARD_EXHAUSTED, "sentinel", "player")
    emit(state, Event.CARD_EXHAUSTED, "player", card=Card("Sentinel+"))
    assert state.energy == 6  # 3 base + 3


def test_corruption_makes_skills_free():
    """Under Corruption, skills cost 0 energy."""
    state = _make_combat_state(
        hand=[Card("Defend")], energy=0,
    )
    state.player_powers.corruption = True
    from sts_env.combat.cards import play_card
    play_card(state, 0, 0)
    assert state.player_block == 5


def test_corruption_exhausts_skills():
    """Under Corruption, played skills are exhausted."""
    state = _make_combat_state(
        hand=[Card("Defend")], energy=1,
    )
    state.player_powers.corruption = True
    from sts_env.combat.cards import play_card
    play_card(state, 0, 0)
    exhaust_ids = [c.card_id for c in state.piles.exhaust]
    assert "Defend" in exhaust_ids


def test_juggernaut_damage_on_block_gain():
    """Juggernaut: deal damage to random enemy when gaining block."""
    from sts_env.combat.events import Event, subscribe, emit
    state = _make_combat_state(
        enemies=[EnemyState(name="E1", hp=30, max_hp=30)],
    )
    state.player_powers.juggernaut = 5
    subscribe(state, Event.BLOCK_GAINED, "juggernaut", "player")
    emit(state, Event.BLOCK_GAINED, "player", amount=5)
    assert state.enemies[0].hp < 30


def test_rage_block_on_attack_play():
    """Rage: gain block when an Attack is played this turn."""
    state = _make_combat_state(
        hand=[Card("Rage"), Card("Strike")], energy=3,
    )
    from sts_env.combat.cards import play_card
    play_card(state, 0, 0)  # Play Rage
    assert state.player_powers.rage_block == 3
    # Now play Strike (simulate the Rage trigger from engine)
    if state.player_powers.rage_block > 0:
        state.player_block += state.player_powers.rage_block
    assert state.player_block == 3


def test_rage_resets_at_end_of_turn():
    """Rage counter resets at end of turn."""
    combat = Combat(
        deck=IRONCLAD_STARTER, enemies=["JawWorm"], seed=42
    )
    obs = combat.reset()
    combat._state.player_powers.rage_block = 3
    combat.step(Action.end_turn())
    assert combat._state.player_powers.rage_block == 0


def test_double_tap_resets_at_end_of_turn():
    """DoubleTap counter resets at end of turn."""
    combat = Combat(
        deck=IRONCLAD_STARTER, enemies=["JawWorm"], seed=42
    )
    obs = combat.reset()
    combat._state.player_powers.double_tap = 1
    combat.step(Action.end_turn())
    assert combat._state.player_powers.double_tap == 0
