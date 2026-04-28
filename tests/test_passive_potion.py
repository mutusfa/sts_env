"""Tests for passive potion feature.

TDD: These tests fail before implementing the passive potion mechanism.
"""
import pytest

from sts_env.combat import Action
from sts_env.combat.engine import Combat
from sts_env.combat.potions import get_spec
from sts_env.combat.state import ActionType
from sts_env.combat.potions import potion, TargetType


def test_potion_decorator_passive_flag():
    """@potion decorator should accept a passive keyword argument."""
    @potion("TestPassive", TargetType.NONE, passive=True)
    def _handler(state, ti):
        pass

    spec = get_spec("TestPassive")
    assert spec.passive is True


def test_potion_decorator_defaults_to_active():
    """@potion decorator should default to active (passive=False)."""
    @potion("TestActive", TargetType.NONE)
    def _handler(state, ti):
        pass

    spec = get_spec("TestActive")
    assert spec.passive is False


def test_fairy_in_a_bottle_is_passive():
    """FairyInABottle should be marked as a passive potion."""
    spec = get_spec("FairyInABottle")
    assert spec.passive is True, "FairyInABottle should be passive"


def test_fairy_in_a_bottle_not_in_legal_actions():
    """Passive potions should not appear as use_potion actions.

    They should only be discardable.
    """
    c = Combat(
        deck=["Strike", "Defend", "Bash"],
        enemies=["JawWorm"],
        seed=42,
        potions=["FairyInABottle"],
    )
    c.reset()
    legal = c.valid_actions()

    # Should have discard_potion(0)
    assert Action.discard_potion(0) in legal, "Should be able to discard FairyInABottle"

    # Should NOT have use_potion(0) (target index doesn't matter for NONE-target potions)
    use_actions = [a for a in legal if a.action_type == ActionType.USE_POTION and a.potion_index == 0]
    assert len(use_actions) == 0, "Passive potions should not have use_potion actions"


def test_active_potions_still_work():
    """Non-passive potions should still generate use_potion actions."""
    c = Combat(
        deck=["Strike", "Defend", "Bash"],
        enemies=["JawWorm"],
        seed=42,
        potions=["BlockPotion", "FirePotion"],
    )
    c.reset()
    legal = c.valid_actions()

    # BlockPotion (NONE target) should have use_potion(0)
    use_block = [a for a in legal if a.action_type == ActionType.USE_POTION and a.potion_index == 0]
    assert len(use_block) == 1, "BlockPotion should have a use_potion action"

    # FirePotion (SINGLE_ENEMY) should have use_potion(1, 0) targeting the enemy
    use_fire = [a for a in legal if a.action_type == ActionType.USE_POTION and a.potion_index == 1 and a.target_index == 0]
    assert len(use_fire) == 1, "FirePotion should have a use_potion action targeting enemy 0"
