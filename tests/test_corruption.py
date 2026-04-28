"""Tests for Corruption power's card mutation behavior."""
import pytest
from sts_env.combat import Combat
from sts_env.combat.state import Action, ActionType
from sts_env.combat.card import Card
from sts_env.combat.cards import CardType

IRONCLAD_STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def _add_corruption_to_hand(combat):
    """Helper to add Corruption card to hand for testing."""
    from sts_env.combat.card import Card
    combat._state.piles.hand.insert(0, Card("Corruption"))
    return combat.observe()


def test_corruption_stamps_existing_skills():
    """Under Corruption, all existing skills in all piles are stamped."""
    combat = Combat(
        deck=IRONCLAD_STARTER,
        enemies=["JawWorm"],
        seed=42
    )
    obs = combat.reset()

    # Add Corruption to hand and play it
    obs = _add_corruption_to_hand(combat)
    obs, _, _ = combat.step(Action(ActionType.PLAY_CARD, 0, 0))

    # Verify corruption power is active
    assert obs.player_powers["corruption"] is True

    # Check that all skills in all piles are stamped
    state = combat._state
    for pile_name, pile in [("draw", state.piles.draw),
                            ("hand", state.piles.hand),
                            ("discard", state.piles.discard),
                            ("exhaust", state.piles.exhaust)]:
        for card in pile:
            if card.spec.card_type == CardType.SKILL:
                assert card.cost_override == 0, f"{pile_name} skill {card.card_id} should have cost_override=0"
                assert card.exhausts_override is True, f"{pile_name} skill {card.card_id} should have exhausts_override=True"
                assert card.corrupted is True, f"{pile_name} skill {card.card_id} should be marked corrupted"
            else:
                # Non-skills should NOT be stamped
                if card.spec.card_type != CardType.CURSE:  # Curses have no cost anyway
                    if card.cost_override is not None:
                        assert not card.corrupted, f"{pile_name} non-skill {card.card_id} should not be marked corrupted"


def test_corruption_stamps_new_skills_via_card_created():
    """Under Corruption, newly created skills (e.g. from potions) are stamped."""
    combat = Combat(
        deck=IRONCLAD_STARTER,
        enemies=["JawWorm"],
        seed=42,
        potions=["SkillPotion"]
    )
    obs = combat.reset()

    # Add Corruption to hand and play it
    obs = _add_corruption_to_hand(combat)
    obs, _, _ = combat.step(Action(ActionType.PLAY_CARD, 0, 0))

    # Use a SkillPotion to create a new skill in hand
    skill_potion_idx = next(i for i, p in enumerate(obs.potions) if p == "SkillPotion")
    obs, _, _ = combat.step(Action(ActionType.USE_POTION, skill_potion_idx, 0))

    # Pick the first skill from the choice (simulating agent choice)
    assert obs.pending_choices
    first_card = obs.pending_choices[0]
    obs, _, _ = combat.step(Action(ActionType.CHOOSE_CARD, 0))

    # Verify the newly created skill is stamped
    state = combat._state
    created_card = state.piles.hand[-1]  # Most recent card added to hand
    assert created_card.spec.card_type == CardType.SKILL
    assert created_card.cost_override == 0, "Newly created skill should have cost_override=0"
    assert created_card.exhausts_override is True, "Newly created skill should have exhausts_override=True"
    assert created_card.corrupted is True, "Newly created skill should be marked corrupted"


def test_corruption_clear_cost_override_skips_corrupted_cards():
    """Clearing cost override at end of turn does NOT affect corruption-stamped cards."""
    combat = Combat(
        deck=IRONCLAD_STARTER,
        enemies=["JawWorm"],
        seed=42
    )
    obs = combat.reset()

    # Add Corruption to hand and play it
    obs = _add_corruption_to_hand(combat)
    obs, _, _ = combat.step(Action(ActionType.PLAY_CARD, 0, 0))

    # Get a corrupted skill from hand
    state = combat._state
    corrupted_skill = next((c for c in state.piles.hand if c.corrupted), None)
    assert corrupted_skill is not None
    assert corrupted_skill.cost_override == 0

    # Call clear_cost_override on it (simulating end-of-turn cleanup)
    corrupted_skill.clear_cost_override()

    # Verify cost_override is preserved (corruption trumps)
    assert corrupted_skill.cost_override == 0, "Corruption-stamped cards should retain cost_override=0 after clear_cost_override"
    assert corrupted_skill.corrupted is True


def test_corruption_observation_visibility():
    """Corruption power is visible in observation and hand shows effective costs."""
    combat = Combat(
        deck=IRONCLAD_STARTER,
        enemies=["JawWorm"],
        seed=42
    )
    obs = combat.reset()

    # Add Corruption to hand and play it
    obs = _add_corruption_to_hand(combat)
    obs, _, _ = combat.step(Action(ActionType.PLAY_CARD, 0, 0))

    # Verify corruption is visible in player_powers
    assert "corruption" in obs.player_powers, "corruption should be in observation player_powers"
    assert obs.player_powers["corruption"] is True, "corruption should be True in observation"

    # Verify hand shows effective values for corrupted skills
    state = combat._state
    for i, card_dict in enumerate(obs.hand):
        actual_card = state.piles.hand[i]
        if actual_card.spec.card_type == CardType.SKILL:
            # Skills should show effective cost 0
            assert card_dict["cost"] == 0, f"Skill {card_dict['card_id']} should show effective cost 0"
            assert card_dict["exhausts"] is True, f"Skill {card_dict['card_id']} should show exhausts=True"
            assert card_dict["corrupted"] is True, f"Skill {card_dict['card_id']} should show corrupted=True"
        else:
            # Non-skills should show their normal cost
            assert card_dict["cost"] == actual_card.effective_cost()
            assert card_dict["exhausts"] == actual_card.effective_exhausts()


def test_corruption_attacks_not_affected():
    """Corruption does NOT affect attack cards."""
    combat = Combat(
        deck=IRONCLAD_STARTER,
        enemies=["JawWorm"],
        seed=42
    )
    obs = combat.reset()

    # Add Corruption to hand and play it
    obs = _add_corruption_to_hand(combat)
    obs, _, _ = combat.step(Action(ActionType.PLAY_CARD, 0, 0))

    # Check that attacks are NOT stamped
    state = combat._state
    for pile_name, pile in [("draw", state.piles.draw),
                            ("hand", state.piles.hand),
                            ("discard", state.piles.discard)]:
        for card in pile:
            if card.spec.card_type == CardType.ATTACK:
                assert card.cost_override is None, f"{pile_name} attack {card.card_id} should not have cost_override"
                assert card.exhausts_override is None, f"{pile_name} attack {card.card_id} should not have exhausts_override"
                assert card.corrupted is False, f"{pile_name} attack {card.card_id} should not be marked corrupted"


def test_corruption_skills_cost_zero_and_exhaust():
    """Under Corruption, skills cost 0 to play and are exhausted when played."""
    combat = Combat(
        deck=IRONCLAD_STARTER,
        enemies=["JawWorm"],
        seed=42
    )
    obs = combat.reset()

    # Add Corruption to hand and play it
    obs = _add_corruption_to_hand(combat)
    obs, _, _ = combat.step(Action(ActionType.PLAY_CARD, 0, 0))

    # Get a skill from hand
    skill_idx = next(i for i, card in enumerate(obs.hand) if Card(card["card_id"]).spec.card_type == CardType.SKILL)
    skill_card = combat._state.piles.hand[skill_idx]

    # Verify skill shows cost 0 in observation
    assert obs.hand[skill_idx]["cost"] == 0, f"Skill should show effective cost 0"

    # Play the skill
    obs_before_play = obs
    obs, _, _ = combat.step(Action(ActionType.PLAY_CARD, skill_idx, 0))

    # Verify skill cost 0 didn't consume energy
    assert obs.energy == obs_before_play.energy, f"Skill should have cost 0 energy, but energy changed from {obs_before_play.energy} to {obs.energy}"

    # Verify skill is exhausted
    state = combat._state
    assert skill_card in state.piles.exhaust, "Skill should be in exhaust pile after play"
    assert skill_card not in state.piles.discard, "Skill should NOT be in discard pile"
