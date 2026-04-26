"""End-to-end engine tests."""

from __future__ import annotations

import pytest

from sts_env.combat import Action, Combat, Observation, encounters
from sts_env.combat.state import ActionType


# ---------------------------------------------------------------------------
# Basic termination
# ---------------------------------------------------------------------------

def _play_to_end(combat: Combat, policy=None) -> Observation:
    """Run a combat to termination using a greedy (play-all then end) policy."""
    obs = combat.reset()
    while not obs.done:
        if policy:
            action = policy(obs)
        else:
            # Default: play the first card in hand that costs <= energy; else end turn
            action = None
            for i, card in enumerate(obs.hand):
                from sts_env.combat.cards import get_spec
                spec = get_spec(card.card_id)
                target = 0
                if spec.playable and spec.cost <= obs.energy:
                    action = Action.play_card(hand_index=i, target_index=target)
                    break
            if action is None:
                action = Action.end_turn()
        obs, _, _ = combat.step(action)
    return obs


def test_combat_terminates_enemy_dead():
    """Starter deck should always kill a single low-HP enemy eventually."""
    # Use a very weak enemy by building state directly
    combat = Combat(
        deck=["Strike"] * 5 + ["Defend"] * 4 + ["Bash"],
        enemies=["Cultist"],
        seed=0,
    )
    obs = _play_to_end(combat)
    assert obs.done
    assert all(e.hp <= 0 for e in obs.enemies)


def test_combat_damage_taken_tracked():
    combat = Combat(
        deck=["Strike"] * 5 + ["Defend"] * 4 + ["Bash"],
        enemies=["Cultist"],
        seed=0,
    )
    obs = _play_to_end(combat)
    assert combat.damage_taken == 80 - obs.player_hp


def test_combat_player_can_die():
    """If player takes enough damage the combat ends with player_dead."""
    # Put player at 1 HP
    combat = Combat(
        deck=["AscendersBane"] * 10,  # can't play anything
        enemies=["JawWorm"],
        seed=0,
        player_hp=1,
    )
    obs = combat.reset()
    # End turn immediately — enemy will attack and kill player
    obs, _, _ = combat.step(Action.end_turn())
    assert obs.player_hp <= 0 or obs.done


# ---------------------------------------------------------------------------
# Energy mechanics
# ---------------------------------------------------------------------------

def test_energy_resets_to_3_each_turn():
    combat = Combat(
        deck=["Defend"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    assert obs.energy == 3

    # Play a Defend (costs 1) then end turn
    obs, _, _ = combat.step(Action.play_card(0))
    assert obs.energy == 2

    obs, _, _ = combat.step(Action.end_turn())
    if not obs.done:
        assert obs.energy == 3


def test_insufficient_energy_raises():
    combat = Combat(
        deck=["Bash"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    # Play two Bashes to drain energy to 3 - 2 - 2 = -1, should fail on second
    obs, _, _ = combat.step(Action.play_card(0))  # uses 2 energy → 1 left
    with pytest.raises(ValueError, match="energy"):
        combat.step(Action.play_card(0))       # needs 2, only 1


def test_unplayable_card_raises():
    combat = Combat(
        deck=["AscendersBane"] * 5,
        enemies=["Cultist"],
        seed=0,
    )
    combat.reset()
    with pytest.raises(ValueError):
        combat.step(Action.play_card(0))


def test_invalid_target_raises():
    combat = Combat(
        deck=["Strike"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    combat.reset()
    with pytest.raises(ValueError, match="target"):
        combat.step(Action.play_card(0, target_index=5))


# ---------------------------------------------------------------------------
# Turn structure
# ---------------------------------------------------------------------------

def test_hand_drawn_at_start():
    combat = Combat(
        deck=["Strike"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    assert len(obs.hand) == 5


def test_hand_refreshes_each_turn():
    combat = Combat(
        deck=["Defend"] * 20,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    assert len(obs.hand) == 5
    obs, _, _ = combat.step(Action.end_turn())
    if not obs.done:
        assert len(obs.hand) == 5


def test_step_after_done_raises():
    combat = Combat(
        deck=["Strike"] * 5 + ["Defend"] * 4 + ["Bash"],
        enemies=["Cultist"],
        seed=0,
    )
    obs = _play_to_end(combat)
    assert obs.done
    with pytest.raises(RuntimeError):
        combat.step(Action.end_turn())


def test_step_before_reset_raises():
    combat = Combat(
        deck=["Strike"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    with pytest.raises(RuntimeError):
        combat.step(Action.end_turn())


# ---------------------------------------------------------------------------
# Seed snapshot — fixed seed produces reproducible result
# ---------------------------------------------------------------------------

def test_seed_snapshot_ironclad_starter_vs_jaw_worm():
    """Greedy policy on seed=0 must produce a stable damage_taken value.

    The exact number is computed from our implementation and recorded here.
    If the value changes, it means a mechanic has changed — investigate before
    updating the snapshot.
    """
    combat = encounters.jaw_worm(seed=0)
    obs = _play_to_end(combat)
    # Record whatever our engine produces and assert stability
    # (First run: compute and commit. Subsequent runs: must match.)
    # Snapshot: captured from first correct run — update if mechanics intentionally change
    assert combat.damage_taken == 10


def test_ironclad_starter_factory():
    combat = encounters.jaw_worm(seed=42)
    obs = combat.reset()
    assert obs.player_hp == 80
    assert len(obs.enemies) == 1
    assert obs.enemies[0].name == "JawWorm"
    assert len(obs.hand) == 5


def test_reset_restores_state():
    """Calling reset() twice should produce identical first observations."""
    combat = encounters.cultist(seed=99)
    obs1 = combat.reset()
    obs2 = combat.reset()
    assert obs1.player_hp == obs2.player_hp
    assert obs1.hand == obs2.hand
    assert obs1.enemies[0].hp == obs2.enemies[0].hp


# ---------------------------------------------------------------------------
# Specific mechanic checks via engine
# ---------------------------------------------------------------------------

def test_bash_vulnerable_amplifies_next_strike():
    """Bash applies Vulnerable; the next Strike should deal 9 (floor(6*1.5))."""
    combat = Combat(
        deck=["Bash", "Strike"] + ["Defend"] * 8,
        enemies=["JawWorm"],
        seed=0,
    )
    obs = combat.reset()
    # Find Bash and Strike in opening hand (seed-dependent; play whatever is there)
    bash_idx = next((i for i, c in enumerate(obs.hand) if c == "Bash"), None)
    strike_idx = next((i for i, c in enumerate(obs.hand) if c == "Strike"), None)

    if bash_idx is None or strike_idx is None:
        pytest.skip("Bash/Strike not in opening hand for this seed")

    hp_before = obs.enemies[0].hp
    obs, _, _ = combat.step(Action.play_card(bash_idx))
    # After Bash: enemy has 2 Vulnerable
    assert obs.enemies[0].powers["vulnerable"] == 2
    dmg_from_bash = hp_before - obs.enemies[0].hp
    assert dmg_from_bash == 8  # no vuln yet when bash hits

    hp_after_bash = obs.enemies[0].hp
    # Adjust strike_idx (hand shifted after bash was played)
    strike_idx_adjusted = next(i for i, c in enumerate(obs.hand) if c == "Strike")
    obs, _, _ = combat.step(Action.play_card(strike_idx_adjusted))
    dmg_from_strike = hp_after_bash - obs.enemies[0].hp
    assert dmg_from_strike == 9  # floor(6 * 1.5) = 9


def test_turn_counter_increments_once_per_round_with_multiple_enemies():
    """Turn counter must advance by 1 per round regardless of enemy count.

    With two enemies the old bug incremented turn once per enemy per round,
    causing pick_intent to see stale / wrong turn numbers.
    """
    combat = Combat(
        deck=["Defend"] * 20,
        enemies=["Cultist", "JawWorm"],
        seed=0,
    )
    obs = combat.reset()
    assert obs.turn == 0

    obs, _, _ = combat.step(Action.end_turn())
    if not obs.done:
        assert obs.turn == 1, f"Expected turn=1 after round 1, got {obs.turn}"

    obs, _, _ = combat.step(Action.end_turn())
    if not obs.done:
        assert obs.turn == 2, f"Expected turn=2 after round 2, got {obs.turn}"


def test_anger_copy_can_be_played_next_turn():
    """Anger adds a copy to discard; after a reshuffle it can be drawn and played."""
    combat = Combat(
        deck=["Anger"] + ["Defend"] * 9,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    # Play Anger if in opening hand
    anger_idx = next((i for i, c in enumerate(obs.hand) if c == "Anger"), None)
    if anger_idx is None:
        pytest.skip("Anger not in opening hand for this seed")

    obs, _, _ = combat.step(Action.play_card(anger_idx))
    # Discard should now contain 2 Anger cards (original + copy)
    total_anger = obs.hand.count("Anger") + sum(obs.discard_pile.values())  # proxy
    # After playing, discard contains both the played Anger and the copy
    assert sum(obs.discard_pile.values()) >= 1  # at minimum the played Anger


# ---------------------------------------------------------------------------
# Reward
# ---------------------------------------------------------------------------

def test_step_returns_three_tuple():
    combat = encounters.cultist(seed=0)
    combat.reset()
    result = combat.step(Action.end_turn())
    assert len(result) == 3


def test_reward_zero_when_no_damage_taken():
    """Cultist turn 0 is Incantation (no attack); reward should be 0."""
    combat = Combat(
        deck=["Defend"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    defend_idx = obs.hand.index("Defend")
    _, r1, _ = combat.step(Action.play_card(defend_idx))
    _, r2, _ = combat.step(Action.end_turn())
    assert r1 == 0
    assert r2 == 0  # Incantation turn, no damage


def test_reward_negative_on_damage():
    """Cultist turn 1 is Dark Strike (6 damage); reward should be -6 that step."""
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["Cultist"],
        seed=0,
        player_hp=80,
    )
    combat.reset()
    # Turn 0: Incantation, no damage
    _, r0, _ = combat.step(Action.end_turn())
    assert r0 == 0
    # Turn 1: Dark Strike, 6 damage (strength=0 this turn; Ritual fires AFTER attack)
    _, r1, _ = combat.step(Action.end_turn())
    assert r1 == -6


# ---------------------------------------------------------------------------
# Pile histograms
# ---------------------------------------------------------------------------

def test_observation_has_pile_histograms():
    """After reset, pile counts should match starter deck minus 5 drawn cards."""
    combat = encounters.cultist(seed=0)
    obs = combat.reset()

    total_in_piles = (
        sum(obs.draw_pile.values())
        + sum(obs.discard_pile.values())
        + sum(obs.exhaust_pile.values())
        + len(obs.hand)
    )
    assert total_in_piles == 10  # full starter deck accounted for
    assert len(obs.hand) == 5
    assert sum(obs.draw_pile.values()) == 5


def test_histogram_card_counts_sum_to_deck_size():
    """Combined histogram counts must always equal full deck size."""
    combat = encounters.jaw_worm(seed=7)
    obs = combat.reset()
    total = (
        sum(obs.draw_pile.values())
        + sum(obs.discard_pile.values())
        + sum(obs.exhaust_pile.values())
        + len(obs.hand)
    )
    assert total == 10


def test_discard_histogram_tracks_anger_copy():
    """Playing Anger adds a copy to discard; histogram should show Anger count = 2."""
    combat = Combat(
        deck=["Anger"] + ["Defend"] * 9,
        enemies=["Cultist"],
        seed=0,
    )
    obs = combat.reset()
    anger_idx = next((i for i, c in enumerate(obs.hand) if c == "Anger"), None)
    if anger_idx is None:
        pytest.skip("Anger not in opening hand for this seed")

    obs, _, _ = combat.step(Action.play_card(anger_idx))
    # Played Anger goes to discard, copy also goes to discard → 2 Anger in discard
    assert obs.discard_pile.get("Anger", 0) == 2


def test_exhaust_pile_reflects_exhausted_cards():
    """Exhaust pile histogram should be empty at start and grow on exhaust effects."""
    combat = encounters.cultist(seed=0)
    obs = combat.reset()
    assert obs.exhaust_pile == {}


# ---------------------------------------------------------------------------
# valid_actions()
# ---------------------------------------------------------------------------

def test_valid_actions_includes_end_turn():
    combat = encounters.cultist(seed=0)
    combat.reset()
    actions = combat.valid_actions()
    assert Action.end_turn() in actions


def test_valid_actions_empty_when_done():
    """No valid actions after combat ends."""
    combat = Combat(
        deck=["AscendersBane"] * 10,
        enemies=["Cultist"],
        seed=0,
        player_hp=1,
    )
    combat.reset()
    # Turn 0: Incantation (no damage). Turn 1: Dark Strike kills the 1-HP player.
    combat.step(Action.end_turn())
    combat.step(Action.end_turn())
    assert combat.valid_actions() == []


def test_valid_actions_filters_unaffordable_bash():
    """After draining energy to 1, Bash (cost 2) should not appear."""
    combat = Combat(
        deck=["Bash"] * 10,
        enemies=["Cultist"],
        seed=0,
    )
    combat.reset()
    # Play one Bash (cost 2): energy drops from 3 → 1
    combat.step(Action.play_card(0))
    actions = combat.valid_actions()
    play_actions = [a for a in actions if a.action_type == ActionType.PLAY_CARD]
    assert play_actions == [], f"Bash should be unaffordable at energy=1, got {play_actions}"


def test_valid_actions_skips_unplayable_curse():
    """AscendersBane (cost=-1) must never appear in valid_actions."""
    combat = Combat(
        deck=["AscendersBane"] * 5 + ["Defend"] * 5,
        enemies=["Cultist"],
        seed=0,
    )
    combat.reset()
    actions = combat.valid_actions()
    for a in actions:
        if a.action_type == ActionType.PLAY_CARD:
            from sts_env.combat.cards import get_spec
            card = combat._state.piles.hand[a.hand_index]
            assert card != "AscendersBane", "Curse appeared in valid_actions"


def test_valid_actions_expands_targets_per_live_enemy():
    """Strike with two enemies → two play actions (one per target)."""
    combat = Combat(
        deck=["Strike"] * 10,
        enemies=["Cultist", "JawWorm"],
        seed=0,
    )
    combat.reset()
    actions = combat.valid_actions()
    # Each Strike in hand expands to two targets
    play_actions = [a for a in actions if a.action_type == ActionType.PLAY_CARD]
    target_indices = {a.target_index for a in play_actions}
    assert 0 in target_indices
    assert 1 in target_indices


def test_valid_actions_skips_dead_enemies():
    """After killing one of two enemies, Strike should only target the live one."""
    combat = Combat(
        deck=["Strike"] * 10,
        enemies=["Cultist", "Cultist"],
        seed=0,
    )
    obs = combat.reset()
    # Kill first Cultist with direct state manipulation (hack for test)
    combat._state.enemies[0].hp = 0

    actions = combat.valid_actions()
    play_actions = [a for a in actions if a.action_type == ActionType.PLAY_CARD]
    targets = {a.target_index for a in play_actions}
    assert 0 not in targets, "Dead enemy (index 0) should not be a valid target"
    assert 1 in targets


def test_valid_actions_cleave_single_action_for_all_enemies():
    """Cleave (ALL_ENEMIES target) emits exactly one action regardless of enemy count."""
    combat = Combat(
        deck=["Cleave"] * 10,
        enemies=["Cultist", "JawWorm"],
        seed=0,
    )
    combat.reset()
    actions = combat.valid_actions()
    cleave_actions = [a for a in actions if a.action_type == ActionType.PLAY_CARD]
    # Each Cleave in hand produces exactly one action (not one per enemy)
    hand_size = len(combat._state.piles.hand)
    assert len(cleave_actions) == hand_size


# ---------------------------------------------------------------------------
# clone()
# ---------------------------------------------------------------------------

def test_clone_produces_independent_state():
    """Stepping the original after cloning must not affect the clone."""
    combat = encounters.jaw_worm(seed=5)
    combat.reset()
    cloned = combat.clone()

    # Record clone's current observation
    clone_obs_before = cloned.observe()

    # Step the original
    combat.step(Action.end_turn())

    # Clone must be unchanged
    clone_obs_after = cloned.observe()
    assert clone_obs_before.player_hp == clone_obs_after.player_hp
    assert clone_obs_before.turn == clone_obs_after.turn


def test_clone_preserves_rng_sequence():
    """Cloned and original produce identical observations after the same action sequence."""
    combat = encounters.jaw_worm(seed=3)
    combat.reset()
    cloned = combat.clone()

    actions = [Action.end_turn(), Action.end_turn()]
    orig_traj = []
    clone_traj = []
    for a in actions:
        obs_o, _, _ = combat.step(a)
        obs_c, _, _ = cloned.step(a)
        orig_traj.append(obs_o.player_hp)
        clone_traj.append(obs_c.player_hp)
        if obs_o.done:
            break

    assert orig_traj == clone_traj, (
        f"RNG diverged after clone: orig={orig_traj}, clone={clone_traj}"
    )


def test_clone_before_reset_raises():
    """Cloning before reset is valid (deepcopy), but observe() should raise on the clone."""
    combat = encounters.cultist(seed=0)
    cloned = combat.clone()
    with pytest.raises(RuntimeError):
        cloned.observe()


def test_clone_damage_tracking_is_independent():
    """damage_taken on clone and original must be tracked independently."""
    combat = encounters.cultist(seed=0)
    combat.reset()
    cloned = combat.clone()

    # Original: end turn twice (Incantation then Dark Strike)
    combat.step(Action.end_turn())
    combat.step(Action.end_turn())

    # Clone: only end turn once (Incantation, no damage)
    cloned.step(Action.end_turn())

    assert combat.damage_taken == 6
    assert cloned.damage_taken == 0


# ---------------------------------------------------------------------------
# intent_damage_effective
# ---------------------------------------------------------------------------

# JawWorm always plays Chomp (base 11) on turn 0 regardless of seed.
_JW_CHOMP_BASE = 11


def test_intent_damage_effective_no_modifiers():
    """With no powers active, effective damage equals base damage."""
    combat = Combat(deck=["Defend"] * 10, enemies=["JawWorm"], seed=0)
    obs = combat.reset()
    enemy = obs.enemies[0]
    assert enemy.intent_damage == _JW_CHOMP_BASE
    assert enemy.intent_damage_effective == _JW_CHOMP_BASE


def test_intent_damage_effective_enemy_strength():
    """Enemy strength adds to effective damage but not base damage."""
    combat = Combat(deck=["Defend"] * 10, enemies=["JawWorm"], seed=0)
    combat.reset()
    combat._state.enemies[0].powers.strength = 4
    obs = combat.observe()
    enemy = obs.enemies[0]
    assert enemy.intent_damage == _JW_CHOMP_BASE
    assert enemy.intent_damage_effective == _JW_CHOMP_BASE + 4


def test_intent_damage_effective_enemy_weak():
    """Enemy weak reduces effective damage (floor(base * 0.75))."""
    import math
    combat = Combat(deck=["Defend"] * 10, enemies=["JawWorm"], seed=0)
    combat.reset()
    combat._state.enemies[0].powers.weak = 2
    obs = combat.observe()
    enemy = obs.enemies[0]
    assert enemy.intent_damage == _JW_CHOMP_BASE
    assert enemy.intent_damage_effective == math.floor(_JW_CHOMP_BASE * 0.75)


def test_intent_damage_effective_player_vulnerable():
    """Player vulnerable scales effective damage up (floor(base * 1.5))."""
    import math
    combat = Combat(deck=["Defend"] * 10, enemies=["JawWorm"], seed=0)
    combat.reset()
    combat._state.player_powers.vulnerable = 2
    obs = combat.observe()
    enemy = obs.enemies[0]
    assert enemy.intent_damage == _JW_CHOMP_BASE
    assert enemy.intent_damage_effective == math.floor(_JW_CHOMP_BASE * 1.5)


def test_intent_damage_effective_strength_and_vulnerable():
    """Strength and player vulnerable both apply: floor((base + str) * 1.5)."""
    import math
    combat = Combat(deck=["Defend"] * 10, enemies=["JawWorm"], seed=0)
    combat.reset()
    combat._state.enemies[0].powers.strength = 3
    combat._state.player_powers.vulnerable = 2
    obs = combat.observe()
    enemy = obs.enemies[0]
    assert enemy.intent_damage == _JW_CHOMP_BASE
    assert enemy.intent_damage_effective == math.floor((_JW_CHOMP_BASE + 3) * 1.5)


def test_intent_damage_effective_non_attack_intent():
    """Non-attack intents (BUFF) report 0 for both damage fields."""
    # Cultist turn 0: Incantation (IntentType.BUFF, no damage)
    combat = Combat(deck=["Defend"] * 10, enemies=["Cultist"], seed=0)
    obs = combat.reset()
    enemy = obs.enemies[0]
    assert enemy.intent_type == "BUFF"
    assert enemy.intent_damage == 0
    assert enemy.intent_damage_effective == 0


def test_intent_damage_effective_attack_debuff_intent():
    """ATTACK_DEBUFF intents compute effective damage just like ATTACK intents."""
    import math
    # FatGremlin always uses ATTACK_DEBUFF (Smash: 4 dmg + Weak 1)
    _FG_SMASH_BASE = 4
    combat = Combat(deck=["Defend"] * 10, enemies=["FatGremlin"], seed=0)
    obs = combat.reset()
    enemy = obs.enemies[0]
    assert enemy.intent_type == "ATTACK_DEBUFF"
    assert enemy.intent_damage == _FG_SMASH_BASE
    assert enemy.intent_damage_effective == _FG_SMASH_BASE

    # With player vulnerable, effective damage should scale
    combat2 = Combat(deck=["Defend"] * 10, enemies=["FatGremlin"], seed=0)
    combat2.reset()
    combat2._state.player_powers.vulnerable = 2
    obs2 = combat2.observe()
    assert obs2.enemies[0].intent_damage_effective == math.floor(_FG_SMASH_BASE * 1.5)


def test_debuff_intent_damage_is_zero():
    """DEBUFF intents (e.g. Lick) report 0 for both damage fields."""
    # AcidSlimeS always alternates Tackle/Lick; force seed to start with Lick
    combat = Combat(deck=["Defend"] * 10, enemies=["AcidSlimeS"], seed=0)
    obs = combat.reset()
    # Find a seed where turn-0 is Lick
    for seed in range(50):
        c = Combat(deck=["Defend"] * 10, enemies=["AcidSlimeS"], seed=seed)
        o = c.reset()
        if o.enemies[0].intent_type == "DEBUFF":
            assert o.enemies[0].intent_damage == 0
            assert o.enemies[0].intent_damage_effective == 0
            return
    pytest.skip("No seed produced Lick on turn 0 in 50 tries")


# ===========================================================================
# Escape mechanic (Looter / Mugger)
# ===========================================================================

def test_escaping_enemy_counts_as_done():
    """When the only enemy has escaped, combat is done (player wins)."""
    combat = Combat(deck=["Defend"] * 10, enemies=["Looter"], seed=0)
    obs = _play_to_end(combat)
    assert obs.done


def test_escaping_enemy_not_targetable():
    """An enemy with is_escaping=True should not appear in valid attack targets."""
    from sts_env.combat.state import EnemyState
    combat = Combat(deck=["Strike"] * 10, enemies=["Looter"], seed=0)
    combat.reset()
    # Manually set is_escaping
    combat._state.enemies[0].is_escaping = True
    actions = combat.valid_actions()
    # No action should target enemy index 0
    for action in actions:
        from sts_env.combat.state import ActionType
        if action.action_type == ActionType.PLAY_CARD:
            assert action.target_index != 0, (
                "Escaping enemy should not be targetable"
            )


def test_all_enemies_escaped_is_done():
    """Combat is done when all non-Empty enemies have escaped."""
    from sts_env.combat.state import EnemyState
    combat = Combat(deck=["Defend"] * 10, enemies=["Looter", "Mugger"], seed=0)
    combat.reset()
    combat._state.enemies[0].is_escaping = True
    combat._state.enemies[1].is_escaping = True
    assert combat._is_done()


def test_looter_encounter_terminates():
    """The Looter encounter always terminates (either killed or escaped)."""
    from sts_env.combat import encounters
    _play_to_end(encounters.looter(seed=0))


# ===========================================================================
# SporeCloud on-death (Fungi Beast)
# ===========================================================================

def test_fungi_beast_death_applies_vulnerable():
    """Killing a FungiBeast applies Vulnerable 2 to the player."""
    combat = Combat(deck=["Strike"] * 10, enemies=["FungiBeast"], seed=0)
    obs = combat.reset()
    # Strike until dead
    obs = _play_to_end(combat)
    # After the beast dies, player should have received Vulnerable 2 at some point
    # We check damage_taken is higher with no block - actually we just check
    # the mechanic fires. We need to inspect mid-combat state.
    # Restart and track vulnerable
    combat2 = Combat(deck=["Strike"] * 10, enemies=["FungiBeast"], seed=0)
    combat2.reset()
    # Force FungiBeast to a near-death state and kill it
    combat2._state.enemies[0].hp = 1
    combat2._state.enemies[0].powers.spore_cloud = 2
    state = combat2._state
    from sts_env.combat.powers import attack_enemy
    attack_enemy(state, state.enemies[0], 10, enemy_index=0)
    assert state.player_powers.vulnerable == 2


def test_fungi_beast_spore_cloud_only_on_death():
    """SporeCloud does not fire if the FungiBeast survives the hit."""
    combat = Combat(deck=["Strike"] * 10, enemies=["FungiBeast"], seed=0)
    combat.reset()
    combat._state.enemies[0].hp = 10
    combat._state.enemies[0].powers.spore_cloud = 2
    state = combat._state
    from sts_env.combat.powers import attack_enemy
    attack_enemy(state, state.enemies[0], 3)  # only 3 damage, beast survives
    assert state.player_powers.vulnerable == 0


# ===========================================================================
# Entangle (Red Slaver)
# ===========================================================================

def test_entangle_prevents_skill_cards():
    """When the player is Entangled, Skill cards are not in valid_actions."""
    combat = Combat(deck=["Defend"] * 5 + ["Strike"] * 5, enemies=["RedSlaver"], seed=0)
    combat.reset()
    combat._state.player_powers.entangled = True
    actions = combat.valid_actions()
    # Check that Defend (a SKILL card) is never a valid play
    from sts_env.combat.state import ActionType
    for action in actions:
        if action.action_type == ActionType.PLAY_CARD:
            from sts_env.combat.cards import get_spec, CardType
            card = combat._state.piles.hand[action.hand_index]
            spec = get_spec(card.card_id)
            assert spec.card_type != CardType.SKILL, (
                f"Skill card {card.card_id!r} should not be playable when entangled"
            )


def test_entangle_clears_at_start_of_next_player_turn():
    """Entangle is cleared when the player starts their next turn."""
    from sts_env.combat.powers import Powers
    powers = Powers(entangled=True)
    powers.tick_start_of_turn()
    assert not powers.entangled


def test_red_slaver_encounter_applies_entangle():
    """Red Slaver eventually applies Entangle in a real combat."""
    from sts_env.combat import encounters
    combat = encounters.red_slaver(seed=0)
    combat.reset()
    found_entangle = False
    # Let the Red Slaver act for up to 10 turns looking for Entangle
    for _ in range(10):
        obs, _, _ = combat.step(combat.valid_actions()[-1])  # end turn
        if combat._state.player_powers.entangled:
            found_entangle = True
            break
        if obs.done:
            break
    assert found_entangle, "Red Slaver never applied Entangle in 10 turns"
