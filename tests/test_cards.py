"""Tests for individual card effects.

Each test builds a minimal CombatState, plays the card, and asserts the
resulting state changes.
"""

from __future__ import annotations

import pytest

from sts_env.combat.card import Card
from sts_env.combat.cards import get_spec, play_card
from sts_env.combat.deck import Piles
from sts_env.combat.powers import Powers
from sts_env.combat.rng import RNG
from sts_env.combat.state import CombatState, EnemyState


def _c(card_id: str) -> Card:
    return Card(card_id)


def _make_state(
    hand: list[str],
    draw: list[str] | None = None,
    discard: list[str] | None = None,
    energy: int = 3,
    player_hp: int = 80,
    player_block: int = 0,
    player_powers: Powers | None = None,
    enemy_hp: int = 50,
    enemy_block: int = 0,
    enemy_powers: Powers | None = None,
) -> CombatState:
    enemy = EnemyState(
        name="DummyEnemy",
        hp=enemy_hp,
        max_hp=enemy_hp,
        block=enemy_block,
        powers=enemy_powers or Powers(),
    )
    return CombatState(
        player_hp=player_hp,
        player_max_hp=player_hp,
        player_block=player_block,
        player_powers=player_powers or Powers(),
        energy=energy,
        piles=Piles(
            hand=[_c(c) for c in hand],
            draw=[_c(c) for c in (draw or [])],
            discard=[_c(c) for c in (discard or [])],
        ),
        enemies=[enemy],
        rng=RNG(0),
    )


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

def test_strike_spec():
    spec = get_spec("Strike")
    assert spec.cost == 1


def test_defend_spec():
    spec = get_spec("Defend")
    assert spec.cost == 1


def test_bash_spec():
    spec = get_spec("Bash")
    assert spec.cost == 2


def test_ascenders_bane_spec():
    spec = get_spec("AscendersBane")
    assert spec.playable is False


# ---------------------------------------------------------------------------
# Strike
# ---------------------------------------------------------------------------

def test_strike_deals_6_damage():
    state = _make_state(hand=["Strike"])
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 44  # 50 - 6


def test_strike_costs_1_energy():
    state = _make_state(hand=["Strike"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.energy == 2


def test_strike_goes_to_discard():
    state = _make_state(hand=["Strike"])
    play_card(state, hand_index=0, target_index=0)
    assert state.piles.discard == [_c("Strike")]
    assert state.piles.hand == []


def test_strike_respects_enemy_block():
    state = _make_state(hand=["Strike"], enemy_block=4)
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].block == 0
    assert state.enemies[0].hp == 48  # 50 - (6 - 4)


# ---------------------------------------------------------------------------
# Defend
# ---------------------------------------------------------------------------

def test_defend_grants_5_block():
    state = _make_state(hand=["Defend"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_block == 5


def test_defend_stacks_block():
    state = _make_state(hand=["Defend"], player_block=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_block == 8


# ---------------------------------------------------------------------------
# Bash
# ---------------------------------------------------------------------------

def test_bash_deals_8_damage_and_2_vulnerable():
    state = _make_state(hand=["Bash"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 42  # 50 - 8
    assert state.enemies[0].powers.vulnerable == 2


def test_bash_costs_2_energy():
    state = _make_state(hand=["Bash"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.energy == 1


def test_bash_insufficient_energy():
    state = _make_state(hand=["Bash"], energy=1)
    with pytest.raises(ValueError, match="energy"):
        play_card(state, hand_index=0, target_index=0)


# ---------------------------------------------------------------------------
# AscendersBane
# ---------------------------------------------------------------------------

def test_ascenders_bane_is_unplayable():
    state = _make_state(hand=["AscendersBane"], energy=3)
    with pytest.raises(ValueError):
        play_card(state, hand_index=0, target_index=0)


# ---------------------------------------------------------------------------
# Pommel Strike
# ---------------------------------------------------------------------------

def test_pommel_strike_deals_9_damage():
    state = _make_state(hand=["PommelStrike"], draw=["Defend"])
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 41  # 50 - 9


def test_pommel_strike_draws_1():
    state = _make_state(hand=["PommelStrike"], draw=["Defend", "Strike"])
    play_card(state, hand_index=0, target_index=0)
    # After playing PommelStrike hand should contain the drawn card
    assert _c("Defend") in state.piles.hand


# ---------------------------------------------------------------------------
# Shrug It Off
# ---------------------------------------------------------------------------

def test_shrug_it_off_grants_8_block():
    state = _make_state(hand=["ShrugItOff"], draw=["Strike"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_block == 8


def test_shrug_it_off_draws_1():
    state = _make_state(hand=["ShrugItOff"], draw=["Strike", "Defend"])
    play_card(state, hand_index=0, target_index=0)
    assert _c("Strike") in state.piles.hand


# ---------------------------------------------------------------------------
# Iron Wave
# ---------------------------------------------------------------------------

def test_iron_wave_deals_5_damage_and_grants_5_block():
    state = _make_state(hand=["IronWave"])
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 45  # 50 - 5
    assert state.player_block == 5


# ---------------------------------------------------------------------------
# Cleave
# ---------------------------------------------------------------------------

def test_cleave_hits_all_enemies():
    """Cleave should deal 8 to every living enemy."""
    enemies = [
        EnemyState(name="E1", hp=30, max_hp=30),
        EnemyState(name="E2", hp=20, max_hp=20),
    ]
    state = CombatState(
        player_hp=80,
        player_max_hp=80,
        player_block=0,
        player_powers=Powers(),
        energy=3,
        piles=Piles(hand=[_c("Cleave")]),
        enemies=enemies,
        rng=RNG(0),
    )
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 22  # 30 - 8
    assert state.enemies[1].hp == 12  # 20 - 8


def test_cleave_skips_dead_enemies():
    enemies = [
        EnemyState(name="Dead", hp=0, max_hp=30),
        EnemyState(name="Alive", hp=20, max_hp=20),
    ]
    state = CombatState(
        player_hp=80,
        player_max_hp=80,
        player_block=0,
        player_powers=Powers(),
        energy=3,
        piles=Piles(hand=[_c("Cleave")]),
        enemies=enemies,
        rng=RNG(0),
    )
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 0  # dead enemy HP unchanged
    assert state.enemies[1].hp == 12


# ---------------------------------------------------------------------------
# Anger
# ---------------------------------------------------------------------------

def test_anger_deals_6_damage():
    state = _make_state(hand=["Anger"])
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 44  # 50 - 6


def test_anger_adds_copy_to_discard():
    state = _make_state(hand=["Anger"])
    play_card(state, hand_index=0, target_index=0)
    # Original Anger goes to discard + a copy is added
    assert state.piles.discard.count(_c("Anger")) == 2


def test_anger_costs_0_energy():
    state = _make_state(hand=["Anger"], energy=0)
    play_card(state, hand_index=0, target_index=0)
    assert state.energy == 0  # still 0 — Anger costs nothing


# ---------------------------------------------------------------------------
# Slimed (Status card)
# ---------------------------------------------------------------------------

def test_slimed_is_registered():
    spec = get_spec("Slimed")
    assert spec.card_id == "Slimed"


def test_slimed_cost_is_1():
    spec = get_spec("Slimed")
    assert spec.cost == 1


def test_slimed_is_status_type():
    from sts_env.combat.cards import CardType
    spec = get_spec("Slimed")
    assert spec.card_type == CardType.STATUS


def test_slimed_exhausts_on_play():
    """Playing Slimed should move the card to exhaust, not discard."""
    state = _make_state(hand=["Slimed"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert _c("Slimed") in state.piles.exhaust
    assert _c("Slimed") not in state.piles.discard


def test_slimed_costs_1_energy():
    state = _make_state(hand=["Slimed"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.energy == 2


def test_slimed_does_no_damage():
    state = _make_state(hand=["Slimed"], energy=3, enemy_hp=50)
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 50


def test_slimed_does_not_grant_block():
    state = _make_state(hand=["Slimed"], energy=3, player_block=0)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_block == 0


def test_slimed_unplayable_at_zero_energy():
    from sts_env.combat.cards import CardSpec
    spec = get_spec("Slimed")
    # Slimed costs 1, so it should fail with 0 energy
    state = _make_state(hand=["Slimed"], energy=0)
    with pytest.raises(ValueError, match="energy"):
        play_card(state, hand_index=0, target_index=0)


# ---------------------------------------------------------------------------
# playable flag (new declarative API)
# ---------------------------------------------------------------------------

def test_card_spec_has_playable_field():
    """CardSpec.playable=False replaces cost=-1 sentinel for unplayable cards."""
    spec = get_spec("AscendersBane")
    assert hasattr(spec, "playable")
    assert spec.playable is False


def test_slimed_is_playable():
    spec = get_spec("Slimed")
    assert spec.playable is True


def test_dazed_is_not_playable():
    spec = get_spec("Dazed")
    assert spec.playable is False


# ---------------------------------------------------------------------------
# Wound
# ---------------------------------------------------------------------------

def test_wound_is_registered():
    spec = get_spec("Wound")
    assert spec.card_id == "Wound"
    assert spec.playable is False


def test_wound_is_status():
    from sts_env.combat.cards import CardType
    spec = get_spec("Wound")
    assert spec.card_type == CardType.STATUS


def test_wound_costs_1():
    spec = get_spec("Wound")
    assert spec.cost == 1


def test_wound_does_not_exhaust():
    spec = get_spec("Wound")
    assert spec.exhausts is False


def test_wound_does_not_ethereal():
    spec = get_spec("Wound")
    assert spec.ethereal is False


# ---------------------------------------------------------------------------
# WildStrike — adds Wound to draw pile
# ---------------------------------------------------------------------------

def test_wild_strike_adds_wound_to_draw():
    state = _make_state(hand=["WildStrike"], draw=["Defend"])
    play_card(state, hand_index=0, target_index=0)
    wound_in_draw = [c for c in state.piles.draw if c.card_id == "Wound"]
    assert len(wound_in_draw) == 1


def test_wild_strike_deals_12_damage():
    state = _make_state(hand=["WildStrike"], draw=["Defend"])
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 38  # 50 - 12


# ---------------------------------------------------------------------------
# PowerThrough — adds 2 Wounds to hand, grants 15 block
# ---------------------------------------------------------------------------

def test_power_through_adds_2_wounds_to_hand():
    state = _make_state(hand=["PowerThrough"])
    play_card(state, hand_index=0, target_index=0)
    wounds_in_hand = [c for c in state.piles.hand if c.card_id == "Wound"]
    assert len(wounds_in_hand) == 2


def test_power_through_grants_15_block():
    state = _make_state(hand=["PowerThrough"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_block == 15


# ---------------------------------------------------------------------------
# Rampage — 8 base + accumulated bonus per play
# ---------------------------------------------------------------------------

def test_rampage_base_damage_is_8():
    state = _make_state(hand=["Rampage"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 42  # 50 - 8


def test_rampage_grows_on_replay():
    state = _make_state(hand=["Rampage"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.rampage_extra == 5
    # Play a second Rampage from discard via a fresh state
    state2 = _make_state(hand=["Rampage"], energy=3, enemy_hp=100)
    state2.rampage_extra = 5
    play_card(state2, hand_index=0, target_index=0)
    # Base 8 + accumulated 5 = 13 damage
    assert state2.enemies[0].hp == 87  # 100 - 13
    assert state2.rampage_extra == 10


def test_rampage_upgraded_bonus():
    state = _make_state(hand=["Rampage+"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.rampage_extra == 8  # upgraded gives +8 per play


# ---------------------------------------------------------------------------
# Whirlwind — X-cost, hits = energy spent
# ---------------------------------------------------------------------------

def test_whirlwind_is_x_cost():
    spec = get_spec("Whirlwind")
    assert spec.x_cost is True


def test_whirlwind_deals_damage_per_energy():
    enemies = [
        EnemyState(name="E1", hp=30, max_hp=30),
    ]
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(hand=[Card("Whirlwind")]),
        enemies=enemies, rng=RNG(0),
    )
    play_card(state, hand_index=0, target_index=0)
    assert state.energy == 0
    assert state.enemies[0].hp == 15  # 30 - 5*3


def test_whirlwind_upgraded_deals_8_per_energy():
    enemies = [
        EnemyState(name="E1", hp=30, max_hp=30),
    ]
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=2,
        piles=Piles(hand=[Card("Whirlwind+")]),
        enemies=enemies, rng=RNG(0),
    )
    play_card(state, hand_index=0, target_index=0)
    assert state.energy == 0
    assert state.enemies[0].hp == 14  # 30 - 8*2


# ---------------------------------------------------------------------------
# SecondWind — exhaust non-Attacks, block per card
# ---------------------------------------------------------------------------

def test_second_wind_exhausts_non_attacks():
    state = _make_state(hand=["SecondWind", "Defend", "Strike"])
    play_card(state, hand_index=0, target_index=0)
    hand_ids = [c.card_id for c in state.piles.hand]
    assert "Defend" not in hand_ids
    assert "Strike" in hand_ids
    exhaust_ids = [c.card_id for c in state.piles.exhaust]
    assert "Defend" in exhaust_ids


def test_second_wind_block_per_exhausted():
    state = _make_state(hand=["SecondWind", "Defend", "Slimed"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_block == 10  # 5 * 2 non-attacks (Defend, Slimed)


def test_second_wind_upgraded_block():
    state = _make_state(hand=["SecondWind+", "Defend"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_block == 7  # 7 * 1


# ---------------------------------------------------------------------------
# SearingBlow — scaling damage with upgrade level
# ---------------------------------------------------------------------------

def test_searing_blow_base():
    state = _make_state(hand=["SearingBlow"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.enemies[0].hp == 38  # 50 - 12


def test_searing_blow_plus1():
    state = _make_state(hand=["SearingBlow+"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    # Level 1: 12 + 1*2/2 = 12 + 1 = 13
    assert state.enemies[0].hp == 37  # 50 - 13


def test_searing_blow_plus2():
    state = _make_state(hand=["SearingBlow++"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    # Level 2: 12 + 2*3/2 = 12 + 3 = 15
    assert state.enemies[0].hp == 35  # 50 - 15


def test_searing_blow_plus3():
    state = _make_state(hand=["SearingBlow+++"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    # Level 3: 12 + 3*4/2 = 12 + 6 = 18
    assert state.enemies[0].hp == 32  # 50 - 18


# ---------------------------------------------------------------------------
# Ethereal — Carnage, GhostArmor, Dazed
# ---------------------------------------------------------------------------

def test_carnage_is_ethereal():
    spec = get_spec("Carnage")
    assert spec.ethereal is True


def test_ghost_armor_is_ethereal():
    spec = get_spec("GhostArmor")
    assert spec.ethereal is True


def test_dazed_is_ethereal():
    spec = get_spec("Dazed")
    assert spec.ethereal is True


# ---------------------------------------------------------------------------
# Sentinel — block on play, energy on exhaust
# ---------------------------------------------------------------------------

def test_sentinel_base_block():
    spec = get_spec("Sentinel")
    assert spec.block == 5
    assert spec.ethereal is True


# ---------------------------------------------------------------------------
# Berserk — gives per-turn energy, not one-shot
# ---------------------------------------------------------------------------

def test_berserk_gives_vulnerable():
    spec = get_spec("Berserk")
    assert spec.self_vulnerable == 2


def test_berserk_sets_per_turn_energy():
    state = _make_state(hand=["Berserk"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.berserk_energy == 1


def test_berserk_upgraded_sets_2_energy():
    state = _make_state(hand=["Berserk+"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.berserk_energy == 2


# ---------------------------------------------------------------------------
# Triggered powers
# ---------------------------------------------------------------------------

def test_rage_sets_block_per_attack():
    state = _make_state(hand=["Rage"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.rage_block == 3


def test_rage_upgraded():
    state = _make_state(hand=["Rage+"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.rage_block == 5


def test_demon_form_sets_stacks():
    state = _make_state(hand=["DemonForm"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.demon_form == 2


def test_demon_form_upgraded():
    state = _make_state(hand=["DemonForm+"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.demon_form == 3


def test_brutality_sets_flag():
    state = _make_state(hand=["Brutality"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.brutality == 1


def test_corruption_sets_flag():
    state = _make_state(hand=["Corruption"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.corruption is True


def test_dark_embrace_adds_stack():
    state = _make_state(hand=["DarkEmbrace"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.dark_embrace == 1


def test_feel_no_pain_adds_stack():
    state = _make_state(hand=["FeelNoPain"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.feel_no_pain == 3


def test_feel_no_pain_upgraded():
    state = _make_state(hand=["FeelNoPain+"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.feel_no_pain == 4


def test_juggernaut_sets_damage():
    state = _make_state(hand=["Juggernaut"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.juggernaut == 5


def test_juggernaut_upgraded():
    state = _make_state(hand=["Juggernaut+"], energy=3)
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.juggernaut == 7


def test_double_tap_sets_counter():
    state = _make_state(hand=["DoubleTap"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.double_tap == 1


def test_double_tap_upgraded():
    state = _make_state(hand=["DoubleTap+"])
    play_card(state, hand_index=0, target_index=0)
    assert state.player_powers.double_tap == 2


# ---------------------------------------------------------------------------
# X-cost — cost_override is ignored, effective_cost uses energy
# ---------------------------------------------------------------------------

def test_x_cost_ignores_cost_override():
    """X-cost cards always spend all available energy, ignoring cost_override."""
    card = Card("Whirlwind", cost_override=0)
    assert card.effective_cost(energy=3) == 3
    assert card.effective_cost(energy=0) == 0


def test_x_cost_fallback_without_energy():
    """Without energy context, X-cost returns spec.cost (typically -1)."""
    card = Card("Whirlwind")
    assert card.effective_cost() == -1


def test_x_cost_with_override_still_spends_all_energy():
    """Even with cost_override set, play_card spends all energy for X-cost."""
    enemies = [EnemyState(name="E1", hp=50, max_hp=50)]
    card = Card("Whirlwind", cost_override=0)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(hand=[card]),
        enemies=enemies, rng=RNG(0),
    )
    play_card(state, hand_index=0, target_index=0)
    assert state.energy == 0
    assert state.enemies[0].hp == 35  # 50 - 5*3


def test_observation_hand_cost_for_x_card():
    """Observation reports current energy as cost for X-cost cards."""
    from sts_env.combat.engine import Combat, Action, ActionType

    combat = Combat(deck=["Whirlwind"] * 10, enemies=["Cultist"], seed=0)
    combat.reset()
    combat._state.energy = 3
    combat._state.piles.hand = [Card("Whirlwind")]

    obs = combat.observe()
    assert obs.hand[0]["cost"] == 3
