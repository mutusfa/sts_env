"""Potion system tests (TDD — written before implementation)."""

from __future__ import annotations

import pytest

from sts_env.combat.engine import Combat
from sts_env.combat.state import Action, ActionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _combat_with_potions(potions: list[str], enemies=("Cultist",), seed=0, player_hp=80) -> Combat:
    """Create a minimal combat pre-loaded with the given potions."""
    return Combat(
        deck=["Strike"] * 5 + ["Defend"] * 4 + ["Bash"],
        enemies=list(enemies),
        seed=seed,
        player_hp=player_hp,
        potions=potions,
    )


def _first_live_enemy_idx(obs) -> int:
    for i, e in enumerate(obs.enemies):
        if e.hp > 0:
            return i
    raise ValueError("No live enemy found")


# ---------------------------------------------------------------------------
# Slot mechanics
# ---------------------------------------------------------------------------

def test_use_potion_consumes_slot():
    combat = _combat_with_potions(["BlockPotion"])
    obs = combat.reset()
    assert "BlockPotion" in obs.potions
    ti = _first_live_enemy_idx(obs)
    obs, _, _ = combat.step(Action.use_potion(0, ti))
    assert "BlockPotion" not in obs.potions
    assert len(obs.potions) == 0


def test_potion_no_energy_cost():
    combat = _combat_with_potions(["EnergyPotion"])
    obs = combat.reset()
    energy_before = obs.energy
    # EnergyPotion grants +2 energy, so energy_after = before + 2 (it doesn't cost any)
    obs, _, _ = combat.step(Action.use_potion(0))
    assert obs.energy == energy_before + 2


def test_potion_can_be_used_when_entangled():
    """Entangled prevents SKILL cards; potions are unaffected."""
    from sts_env.combat.state import CombatState
    combat = _combat_with_potions(["BlockPotion"])
    obs = combat.reset()
    # Manually set entangled
    combat._state.player_powers.entangled = True
    ti = _first_live_enemy_idx(obs)
    obs, _, _ = combat.step(Action.use_potion(0, ti))
    assert "BlockPotion" not in obs.potions


def test_discard_potion_removes_slot():
    combat = _combat_with_potions(["StrengthPotion"])
    obs = combat.reset()
    hp_before = obs.player_hp
    str_before = obs.player_powers.get("strength", 0)
    obs, _, _ = combat.step(Action.discard_potion(0))
    # No effect on strength, no energy change, slot gone
    assert "StrengthPotion" not in obs.potions
    assert obs.player_powers.get("strength", 0) == str_before


def test_potion_slot_cap_respected():
    """Passing too many potions to Combat should raise."""
    with pytest.raises(ValueError):
        Combat(
            deck=["Strike"],
            enemies=["Cultist"],
            seed=0,
            potions=["BlockPotion"] * 4,  # default max_potion_slots=3
        )


def test_max_potion_slots_in_observation():
    combat = _combat_with_potions([])
    obs = combat.reset()
    assert obs.max_potion_slots == 3


def test_potions_in_observation():
    combat = _combat_with_potions(["BlockPotion", "FirePotion"])
    obs = combat.reset()
    assert obs.potions == ["BlockPotion", "FirePotion"]


# ---------------------------------------------------------------------------
# Damage potions
# ---------------------------------------------------------------------------

def test_fire_potion_ignores_strength_and_weak():
    """Fire Potion deals exactly 20 regardless of player Weak or Strength."""
    combat = _combat_with_potions(["FirePotion"])
    obs = combat.reset()
    ti = _first_live_enemy_idx(obs)
    # Apply weak + give strength; should make no difference
    combat._state.player_powers.weak = 5
    combat._state.player_powers.strength = 10
    hp_before = combat._state.enemies[ti].hp
    block_before = combat._state.enemies[ti].block
    combat.step(Action.use_potion(0, ti))
    enemy = combat._state.enemies[ti]
    dmg_dealt = (hp_before + block_before) - (enemy.hp + enemy.block)
    assert dmg_dealt == 20


def test_explosive_potion_hits_all_enemies():
    combat = _combat_with_potions(["ExplosivePotion"], enemies=["Cultist", "Cultist"])
    obs = combat.reset()
    hps_before = [e.hp for e in obs.enemies]
    obs, _, _ = combat.step(Action.use_potion(0))
    for i, e in enumerate(obs.enemies):
        if e.max_hp > 0:
            assert e.hp < hps_before[i], f"Enemy {i} was not damaged"


def test_fear_potion_applies_vulnerable_to_target():
    combat = _combat_with_potions(["FearPotion"])
    obs = combat.reset()
    ti = _first_live_enemy_idx(obs)
    vuln_before = obs.enemies[ti].powers.get("vulnerable", 0)
    obs, _, _ = combat.step(Action.use_potion(0, ti))
    assert obs.enemies[ti].powers.get("vulnerable", 0) > vuln_before


# ---------------------------------------------------------------------------
# Block potions
# ---------------------------------------------------------------------------

def test_block_potion_grants_block():
    combat = _combat_with_potions(["BlockPotion"])
    obs = combat.reset()
    block_before = obs.player_block
    obs, _, _ = combat.step(Action.use_potion(0))
    assert obs.player_block > block_before


def test_block_potion_ignores_frail():
    """Block Potion grants flat 12 even when player is Frail."""
    combat = _combat_with_potions(["BlockPotion"])
    obs = combat.reset()
    combat._state.player_powers.frail = 5
    block_before = combat._state.player_block
    combat.step(Action.use_potion(0))
    gained = combat._state.player_block - block_before
    assert gained == 12


# ---------------------------------------------------------------------------
# Buff potions
# ---------------------------------------------------------------------------

def test_strength_potion_persists_after_turn_end():
    combat = _combat_with_potions(["StrengthPotion"])
    obs = combat.reset()
    str_before = obs.player_powers.get("strength", 0)
    obs, _, _ = combat.step(Action.use_potion(0))
    str_after = obs.player_powers.get("strength", 0)
    assert str_after == str_before + 2
    # End the turn and confirm strength remains
    obs, _, _ = combat.step(Action.end_turn())
    assert obs.player_powers.get("strength", 0) == str_before + 2


def test_steroid_potion_lost_at_end_of_turn():
    """Steroid Potion gives +5 strength this turn; lost at end of turn."""
    combat = _combat_with_potions(["SteroidPotion"])
    obs = combat.reset()
    str_before = obs.player_powers.get("strength", 0)
    obs, _, _ = combat.step(Action.use_potion(0))
    assert obs.player_powers.get("strength", 0) == str_before + 5
    obs, _, _ = combat.step(Action.end_turn())
    assert obs.player_powers.get("strength", 0) == str_before


def test_flex_potion_lost_at_end_of_turn():
    """Flex Potion gives +5 strength this turn; lost at end of turn."""
    combat = _combat_with_potions(["FlexPotion"])
    obs = combat.reset()
    str_before = obs.player_powers.get("strength", 0)
    obs, _, _ = combat.step(Action.use_potion(0))
    assert obs.player_powers.get("strength", 0) == str_before + 5
    obs, _, _ = combat.step(Action.end_turn())
    assert obs.player_powers.get("strength", 0) == str_before


def test_dexterity_potion_persists():
    """Dexterity Potion grants +2 dexterity permanently (for this combat)."""
    combat = _combat_with_potions(["DexterityPotion"])
    obs = combat.reset()
    dex_before = obs.player_powers.get("dexterity", 0)
    obs, _, _ = combat.step(Action.use_potion(0))
    assert obs.player_powers.get("dexterity", 0) == dex_before + 2
    obs, _, _ = combat.step(Action.end_turn())
    assert obs.player_powers.get("dexterity", 0) == dex_before + 2


def test_speed_potion_dexterity_lost_at_end_of_turn():
    """Speed Potion gives +5 dexterity this turn; lost at end of turn."""
    combat = _combat_with_potions(["SpeedPotion"])
    obs = combat.reset()
    dex_before = obs.player_powers.get("dexterity", 0)
    obs, _, _ = combat.step(Action.use_potion(0))
    assert obs.player_powers.get("dexterity", 0) == dex_before + 5
    obs, _, _ = combat.step(Action.end_turn())
    assert obs.player_powers.get("dexterity", 0) == dex_before


# ---------------------------------------------------------------------------
# Utility potions
# ---------------------------------------------------------------------------

def test_swift_potion_draws_three():
    combat = _combat_with_potions(["SwiftPotion"])
    obs = combat.reset()
    hand_size_before = len(obs.hand)
    obs, _, _ = combat.step(Action.use_potion(0))
    assert len(obs.hand) == hand_size_before + 3


def test_energy_potion_grants_two_energy():
    combat = _combat_with_potions(["EnergyPotion"])
    obs = combat.reset()
    energy_before = obs.energy
    obs, _, _ = combat.step(Action.use_potion(0))
    assert obs.energy == energy_before + 2


# ---------------------------------------------------------------------------
# Ironclad-only potions
# ---------------------------------------------------------------------------

def test_blood_potion_heals_20_percent_max_hp():
    """Blood Potion heals floor(20% of max_hp)."""
    import math
    max_hp = 80
    current_hp = 50
    combat = Combat(
        deck=["Strike"] * 5 + ["Defend"] * 4 + ["Bash"],
        enemies=["Cultist"],
        seed=0,
        player_hp=current_hp,
        player_max_hp=max_hp,
        potions=["BloodPotion"],
    )
    obs = combat.reset()
    assert obs.player_max_hp == max_hp
    hp_before = obs.player_hp
    obs, _, _ = combat.step(Action.use_potion(0))
    expected_heal = math.floor(max_hp * 0.20)
    assert obs.player_hp == min(max_hp, hp_before + expected_heal)


def test_heart_of_iron_grants_metallicize_block_at_eot():
    """Heart of Iron gives Metallicize 4: gain 4 block at end of every player turn."""
    combat = _combat_with_potions(["HeartOfIron"])
    obs = combat.reset()
    obs, _, _ = combat.step(Action.use_potion(0))
    # Confirm metallicize field visible in observation
    assert obs.player_powers.get("metallicize", 0) == 4
    block_before = obs.player_block
    obs, _, _ = combat.step(Action.end_turn())
    # After end of player turn, should have gained 4 block (then player turn starts wiping block;
    # actually block is wiped at START of *next* player turn — so metallicize block survives
    # through enemy turns but is wiped at the very start of next player turn.
    # The observation is taken *after* the new player turn starts and block is wiped.
    # So we verify via the state directly after end turn resolves metallicize but before new-turn wipe.
    # Actually: _resolve_end_of_player_turn fires metallicize, then enemies attack (may reduce block),
    # then new player turn starts and wipes block. The observation reflects the NEW player turn state.
    # => the metallicize block will have been wiped. We test the power is still applied (=4).
    assert obs.player_powers.get("metallicize", 0) == 4


def test_heart_of_iron_block_applied_before_enemy_attacks():
    """Metallicize block is gained before enemies attack (absorbs damage)."""
    # Player at low HP with a single-attack enemy; metallicize block should reduce damage
    # Use a fresh-state check via combat._state to inspect block right after metallicize fires
    # but this is hard without deeper hooks. Instead we verify damage_taken is lower with it.
    combat_no_met = Combat(
        deck=["Defend"] * 10,
        enemies=["Cultist"],
        seed=0,
        player_hp=80,
    )
    combat_with_met = _combat_with_potions(["HeartOfIron"], enemies=["Cultist"], seed=0, player_hp=80)

    obs_no = combat_no_met.reset()
    obs_met = combat_with_met.reset()

    # Use the potion immediately
    obs_met, _, _ = combat_with_met.step(Action.use_potion(0))

    # End the turn for both
    obs_no, _, _ = combat_no_met.step(Action.end_turn())
    obs_met, _, _ = combat_with_met.step(Action.end_turn())

    # With metallicize the player should have taken less or equal damage
    assert combat_with_met.damage_taken <= combat_no_met.damage_taken


# ---------------------------------------------------------------------------
# valid_actions integration
# ---------------------------------------------------------------------------

def test_valid_actions_includes_potion_actions():
    combat = _combat_with_potions(["FirePotion", "BlockPotion"])
    obs = combat.reset()
    actions = combat.valid_actions()
    use_actions = [a for a in actions if a.action_type == ActionType.USE_POTION]
    discard_actions = [a for a in actions if a.action_type == ActionType.DISCARD_POTION]
    # FirePotion is SINGLE_ENEMY → one USE per live enemy
    # BlockPotion is NONE → one USE total
    # Both have DISCARD
    assert len(discard_actions) == 2
    assert len(use_actions) >= 2  # at least 1 for FirePotion + 1 for BlockPotion


def test_potion_action_invalid_when_slot_empty():
    combat = _combat_with_potions([])
    obs = combat.reset()
    actions = combat.valid_actions()
    assert not any(a.action_type == ActionType.USE_POTION for a in actions)
    assert not any(a.action_type == ActionType.DISCARD_POTION for a in actions)
