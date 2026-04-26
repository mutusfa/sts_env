"""Tests for the large slime split mechanic and enemy-adds-card-to-discard behaviour.

Split rules (asc 0):
  AcidSlimeL  → 2 × AcidSlimeM  at the large's curHp when the split fires.
  SpikeSlimeL → 2 × SpikeSlimeM at the large's curHp when the split fires.

The split happens on the enemy's next turn after HP drops to <=50% of max_hp.
The two replacement mediums occupy the old slot (idx) and idx+1 (pre-allocated
as an "Empty" sentinel).  No damage is dealt on the turn of the split itself.
"""

from __future__ import annotations

import pytest

from sts_env.combat import Action, Combat, encounters
from sts_env.combat.cards import play_card
from sts_env.combat.deck import Piles
from sts_env.combat.enemies import pick_intent_with_state, roll_hp
from sts_env.combat.engine import IRONCLAD_STARTER
from sts_env.combat.powers import Powers
from sts_env.combat.rng import RNG
from sts_env.combat.state import CombatState, EnemyState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state_with_enemies(
    enemies: list[EnemyState],
    hand: list[str] | None = None,
    energy: int = 3,
    player_hp: int = 80,
) -> CombatState:
    return CombatState(
        player_hp=player_hp,
        player_max_hp=player_hp,
        player_block=0,
        player_powers=Powers(),
        energy=energy,
        piles=Piles(hand=list(hand or []), draw=[]),
        enemies=enemies,
        rng=RNG(0),
    )


def _play_to_end(combat: Combat) -> None:
    obs = combat.reset()
    while not obs.done:
        actions = combat.valid_actions()
        obs, _, _ = combat.step(actions[0])


# ---------------------------------------------------------------------------
# Enemy-adds-card-to-discard (via Intent.status_card_*)
# ---------------------------------------------------------------------------

def test_slimed_added_to_discard_on_flame_tackle():
    """When SpikeSlimeM uses FlameTackle, one Slimed is added to the player discard."""
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["SpikeSlimeM"],
        seed=0,
        player_hp=80,
    )
    obs = combat.reset()
    # Force SpikeSlimeM's first intent to FlameTackle by picking a seed where
    # that's what it does.  We'll just end-turn and check the discard.
    # We need the first intent to be FlameTackle (30% chance per roll).
    # Instead of relying on a specific seed, we'll manually verify over several turns.
    slimed_count_before = obs.discard_pile.get("Slimed", 0)

    # End turn — enemy acts; FlameTackle adds Slimed to discard.
    # We check by accumulating over multiple seeds until FlameTackle fires.
    found_slimed = False
    for seed in range(50):
        c = Combat(deck=["AscendersBane"] * 10, enemies=["SpikeSlimeM"], seed=seed, player_hp=80)
        o = c.reset()
        enemy = o.enemies[0]
        if enemy.intent_type == "ATTACK_DEBUFF":  # FlameTackle
            o2, _, _ = c.step(Action.end_turn())
            slimed_in_discard = o2.discard_pile.get("Slimed", 0)
            assert slimed_in_discard >= 1, (
                f"FlameTackle should add 1 Slimed to discard (seed={seed})"
            )
            found_slimed = True
            break
    assert found_slimed, "FlameTackle never fired in 50 seeds"


def test_slimed_played_goes_to_exhaust():
    """Playing Slimed from hand exhausts it instead of discarding."""
    combat = Combat(
        deck=["Slimed"] + ["AscendersBane"] * 9,
        enemies=["Cultist"],
        seed=3,  # seed=3 draws Slimed in the opening hand
    )
    obs = combat.reset()
    assert "Slimed" in obs.hand, "Slimed should be in opening hand for seed=3"

    slimed_idx = obs.hand.index("Slimed")
    obs2, _, _ = combat.step(Action.play_card(slimed_idx))
    assert obs2.exhaust_pile.get("Slimed", 0) == 1, "Slimed should be exhausted"
    assert obs2.discard_pile.get("Slimed", 0) == 0, "Slimed should not be in discard"


def test_slimed_consumes_energy():
    combat = Combat(
        deck=["Slimed"] + ["AscendersBane"] * 9,
        enemies=["Cultist"],
        seed=3,  # seed=3 draws Slimed in the opening hand
    )
    obs = combat.reset()
    assert "Slimed" in obs.hand

    energy_before = obs.energy
    slimed_idx = obs.hand.index("Slimed")
    obs2, _, _ = combat.step(Action.play_card(slimed_idx))
    assert obs2.energy == energy_before - 1


def test_slimed_in_valid_actions_when_energy_available():
    """Slimed should appear in valid_actions when energy >= 1."""
    combat = Combat(
        deck=["Slimed"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    assert "Slimed" in obs.hand
    actions = combat.valid_actions()
    play_actions = [a for a in actions if a.action_type.name == "PLAY_CARD"]
    slimed_indices = [i for i, c in enumerate(obs.hand) if c == "Slimed"]
    for si in slimed_indices:
        assert any(a.hand_index == si for a in play_actions), (
            f"Slimed at hand_index={si} not in valid_actions"
        )


# ---------------------------------------------------------------------------
# Empty sentinel slot
# ---------------------------------------------------------------------------

def test_empty_slot_not_targetable():
    """An Empty slot should not appear in valid target indices."""
    combat = encounters.acid_slime_l(seed=0)
    obs = combat.reset()
    actions = combat.valid_actions()
    play_actions = [a for a in actions if a.action_type.name == "PLAY_CARD"]
    # The Empty slot is at index 1; it should never be a target
    empty_targets = [a for a in play_actions if a.target_index == 1]
    assert empty_targets == [], "Empty slot should not be a valid target"


def test_empty_slot_not_counted_for_done():
    """Combat should be done when only the real enemy is dead, not when Empty is 'alive'."""
    combat = encounters.acid_slime_l(seed=0)
    obs = combat.reset()
    # Kill the AcidSlimeL directly — combat should be done now
    combat._state.enemies[0].hp = 0
    assert combat._is_done(), "Combat should be done when AcidSlimeL is dead (Empty ignored)"


def test_acid_slime_l_factory_has_two_slots():
    """acid_slime_l encounter should expose 2 slots: AcidSlimeL + Empty."""
    obs = encounters.acid_slime_l(seed=0).reset()
    assert len(obs.enemies) == 2
    assert obs.enemies[0].name == "AcidSlimeL"
    assert obs.enemies[1].name == "Empty"


def test_spike_slime_l_factory_has_two_slots():
    obs = encounters.spike_slime_l(seed=0).reset()
    assert len(obs.enemies) == 2
    assert obs.enemies[0].name == "SpikeSlimeL"
    assert obs.enemies[1].name == "Empty"


# ---------------------------------------------------------------------------
# Split mechanics
# ---------------------------------------------------------------------------

def _damage_large_to_half(combat: Combat, large_idx: int, deck: list[str] | None = None) -> None:
    """Use direct state manipulation to drop the large slime to exactly 50% HP."""
    state = combat._state
    assert state is not None
    enemy = state.enemies[large_idx]
    enemy.hp = enemy.max_hp // 2


def test_acid_slime_l_split_fires_when_at_half_hp():
    """After AcidSlimeL drops to <=50% HP, the next enemy turn spawns 2 AcidSlimeM."""
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["AcidSlimeL", "Empty"],
        seed=0,
        player_hp=80,
    )
    obs = combat.reset()
    large = combat._state.enemies[0]
    half_hp = large.max_hp // 2

    # Directly set HP at the split threshold and arm the flag
    # (attack_enemy sets this flag when HP crosses the threshold)
    large.hp = half_hp
    large.pending_split = True

    # End turn — enemy acts; split should fire (no damage this turn)
    obs2, _, _ = combat.step(Action.end_turn())

    # After split: slot 0 and slot 1 should be AcidSlimeM
    assert obs2.enemies[0].name == "AcidSlimeM", (
        f"Slot 0 after split should be AcidSlimeM, got {obs2.enemies[0].name}"
    )
    assert obs2.enemies[1].name == "AcidSlimeM", (
        f"Slot 1 after split should be AcidSlimeM, got {obs2.enemies[1].name}"
    )


def test_split_hp_equals_large_hp_at_trigger():
    """The split mediums start with the large's HP value at the time of split."""
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["AcidSlimeL", "Empty"],
        seed=0,
        player_hp=80,
    )
    combat.reset()
    large = combat._state.enemies[0]
    split_hp = large.max_hp // 2
    large.hp = split_hp
    large.pending_split = True

    combat.step(Action.end_turn())

    state = combat._state
    assert state is not None
    assert state.enemies[0].hp == split_hp, "Medium 0 HP should equal large's HP at split"
    assert state.enemies[1].hp == split_hp, "Medium 1 HP should equal large's HP at split"


def test_split_no_damage_on_split_turn():
    """The turn the split fires, no attack damage should be dealt to the player."""
    # Give player full health; AcidSlimeL only splits, no attack
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["AcidSlimeL", "Empty"],
        seed=0,
        player_hp=80,
    )
    combat.reset()
    large = combat._state.enemies[0]
    large.hp = large.max_hp // 2
    large.pending_split = True

    hp_before = combat._state.player_hp
    obs2, reward, _ = combat.step(Action.end_turn())
    # No damage from split itself
    assert obs2.player_hp == hp_before, (
        f"Player took damage on split turn: {hp_before} -> {obs2.player_hp}"
    )


def test_spike_slime_l_split_spawns_spike_slime_m():
    """SpikeSlimeL should split into 2 SpikeSlimeM."""
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["SpikeSlimeL", "Empty"],
        seed=0,
        player_hp=80,
    )
    combat.reset()
    large = combat._state.enemies[0]
    large.hp = large.max_hp // 2
    large.pending_split = True

    combat.step(Action.end_turn())

    state = combat._state
    assert state is not None
    assert state.enemies[0].name == "SpikeSlimeM"
    assert state.enemies[1].name == "SpikeSlimeM"


def test_split_mediums_pick_initial_intent():
    """After split, both mediums should have valid intents for the next player turn."""
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["AcidSlimeL", "Empty"],
        seed=0,
        player_hp=80,
    )
    combat.reset()
    combat._state.enemies[0].hp = combat._state.enemies[0].max_hp // 2
    combat._state.enemies[0].pending_split = True

    obs2, _, _ = combat.step(Action.end_turn())
    # Both mediums should show some intent (not "NONE")
    for i, e in enumerate(obs2.enemies):
        if e.name == "AcidSlimeM":
            assert e.intent_type != "NONE", (
                f"AcidSlimeM at slot {i} has no intent after split"
            )


def test_split_combat_terminates():
    """An acid_slime_l encounter should terminate without errors."""
    _play_to_end(encounters.acid_slime_l(seed=0))


def test_spike_slime_l_combat_terminates():
    _play_to_end(encounters.spike_slime_l(seed=0))


def test_targeting_valid_after_split():
    """After split, only the live mediums should be valid targets."""
    combat = Combat(
        deck=["Strike"] * 10,
        enemies=["AcidSlimeL", "Empty"],
        seed=0,
        player_hp=80,
    )
    combat.reset()
    combat._state.enemies[0].hp = combat._state.enemies[0].max_hp // 2
    combat._state.enemies[0].pending_split = True

    # End turn to trigger split
    obs2, _, _ = combat.step(Action.end_turn())

    # Now both mediums are alive; valid actions should target both indices 0 and 1
    actions = combat.valid_actions()
    play_actions = [a for a in actions if a.action_type.name == "PLAY_CARD"]
    targets = {a.target_index for a in play_actions}
    assert 0 in targets, "AcidSlimeM at slot 0 should be a valid target after split"
    assert 1 in targets, "AcidSlimeM at slot 1 should be a valid target after split"


def test_pending_split_set_by_attack():
    """attack_enemy should set pending_split when HP crosses <=50% threshold."""
    from sts_env.combat.powers import attack_enemy

    large = EnemyState(name="AcidSlimeL", hp=67, max_hp=67)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[large], rng=RNG(0),
    )
    # Deal just enough to cross the 50% threshold
    threshold = 67 // 2  # 33
    damage_needed = 67 - threshold  # 34
    attack_enemy(state, large, damage_needed)
    assert large.pending_split, "pending_split should be True after crossing 50% HP"


def test_pending_split_not_set_above_half():
    """attack_enemy should not set pending_split if HP stays above 50%."""
    from sts_env.combat.powers import attack_enemy

    large = EnemyState(name="AcidSlimeL", hp=67, max_hp=67)
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[large], rng=RNG(0),
    )
    attack_enemy(state, large, 5)  # 67 -> 62, still > 33
    assert not large.pending_split, "pending_split should not be set above 50% HP"


def test_pending_split_not_set_if_already_below_half():
    """If HP is already below 50%, a subsequent hit should not re-trigger split."""
    from sts_env.combat.powers import attack_enemy

    large = EnemyState(name="AcidSlimeL", hp=20, max_hp=67)
    large.pending_split = False  # already fired previously
    state = CombatState(
        player_hp=80, player_max_hp=80, player_block=0,
        player_powers=Powers(), energy=3,
        piles=Piles(draw=[]), enemies=[large], rng=RNG(0),
    )
    attack_enemy(state, large, 3)  # still below half, no new split
    assert not large.pending_split, "pending_split should not be re-triggered below 50%"


# ---------------------------------------------------------------------------
# Determinism across split
# ---------------------------------------------------------------------------

def test_split_reproducible():
    """Same seed should produce same split-moment HP and same sequence after."""
    combat1 = encounters.acid_slime_l(seed=7)
    combat2 = encounters.acid_slime_l(seed=7)
    obs1 = combat1.reset()
    obs2 = combat2.reset()
    assert obs1.enemies[0].hp == obs2.enemies[0].hp

    # Drive both to split at same HP
    split_hp = combat1._state.enemies[0].max_hp // 2
    combat1._state.enemies[0].hp = split_hp
    combat1._state.enemies[0].pending_split = True
    combat2._state.enemies[0].hp = split_hp
    combat2._state.enemies[0].pending_split = True
    obs1b, _, _ = combat1.step(Action.end_turn())
    obs2b, _, _ = combat2.step(Action.end_turn())
    assert obs1b.enemies[0].hp == obs2b.enemies[0].hp
    assert obs1b.enemies[1].hp == obs2b.enemies[1].hp
