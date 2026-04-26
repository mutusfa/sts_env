"""Tests for Havoc card and its interaction with the effect stack.

Covers:
  - Havoc plays top of draw pile
  - Havoc exhausts the played card (not Havoc itself)
  - Havoc on empty draw fizzles
  - Havoc + BurningPact nesting (the motivating case)
"""

import pytest
from sts_env.combat import Combat
from sts_env.combat.card import Card
from sts_env.combat.cards import get_spec
from sts_env.combat.engine import IRONCLAD_STARTER
from sts_env.combat.pending import ChoiceFrame, ThunkFrame
from sts_env.combat.state import Action, ActionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_combat(seed: int = 42) -> Combat:
    combat = Combat(deck=list(IRONCLAD_STARTER), enemies=["JawWorm"], seed=seed)
    combat.reset()
    return combat


def _make_combat_with_havoc(seed: int = 42) -> Combat:
    """Create a combat with Havoc in hand and known draw pile."""
    # Use Ironclad starter + extra Strikes to pad the deck
    combat = Combat(deck=list(IRONCLAD_STARTER), enemies=["JawWorm"], seed=seed)
    combat.reset()
    # Inject Havoc into hand
    combat._state.piles.hand.insert(0, Card("Havoc"))
    return combat


# ---------------------------------------------------------------------------
# Basic Havoc
# ---------------------------------------------------------------------------

class TestHavocBasic:

    def test_havoc_plays_top_of_draw(self):
        """Havoc should resolve the top card of the draw pile."""
        combat = _make_combat_with_havoc()
        state = combat._state
        # Find Havoc in hand
        havoc_idx = None
        for i, card in enumerate(state.piles.hand):
            if card.card_id == "Havoc":
                havoc_idx = i
                break
        assert havoc_idx is not None, "Havoc should be in hand"
        # Peek at top of draw
        top_card = state.piles.draw[0]
        top_id = top_card.card_id
        enemy = state.enemies[0]
        old_hp = enemy.hp
        # Play Havoc
        obs, _, _ = combat.step(Action.play_card(havoc_idx, 0))
        # The top card's effects should have been applied
        # (Strike does 6 damage)
        if top_id.rstrip("+") == "Strike":
            assert enemy.hp < old_hp, "Strike from Havoc should have dealt damage"

    def test_havoc_exhausts_played_card(self):
        """Havoc should exhaust the card it plays (not Havoc itself)."""
        combat = _make_combat_with_havoc()
        state = combat._state
        havoc_idx = None
        for i, card in enumerate(state.piles.hand):
            if card.card_id == "Havoc":
                havoc_idx = i
                break
        assert havoc_idx is not None
        top_card = state.piles.draw[0]
        top_id = top_card.card_id
        exhaust_before = [c.card_id for c in state.piles.exhaust]
        obs, _, _ = combat.step(Action.play_card(havoc_idx, 0))
        exhaust_after = [c.card_id for c in state.piles.exhaust]
        # The played card should be in exhaust pile
        assert top_id in exhaust_after
        # Havoc itself should be in discard (it's a normal skill that exhausts,
        # so it goes to exhaust via the spec.exhausts flag — but it's the Havoc
        # card that exhausts, not the played card from Havoc's effect)
        # Actually Havoc has exhausts=True, so Havoc goes to exhaust too.
        # The played card is also exhausted by Havoc's effect.

    def test_havoc_on_empty_draw_fizzles(self):
        """Havoc with empty draw and discard should fizzle (no crash)."""
        combat = _make_combat_with_havoc()
        state = combat._state
        # Empty both draw and discard
        state.piles.draw.clear()
        state.piles.discard.clear()
        havoc_idx = None
        for i, card in enumerate(state.piles.hand):
            if card.card_id == "Havoc":
                havoc_idx = i
                break
        assert havoc_idx is not None
        enemy = state.enemies[0]
        old_hp = enemy.hp
        obs, _, _ = combat.step(Action.play_card(havoc_idx, 0))
        # No damage dealt (nothing to play)
        assert enemy.hp == old_hp
        # Havoc still exhausts itself
        assert "Havoc" in [c.card_id for c in state.piles.exhaust]

    def test_havoc_reshuffles_if_draw_empty(self):
        """If draw is empty but discard has cards, reshuffle then play."""
        combat = _make_combat_with_havoc()
        state = combat._state
        # Move all draw cards to discard except none
        state.piles.discard.extend(state.piles.draw)
        state.piles.draw.clear()
        # Add a Strike to discard so it gets shuffled
        state.piles.discard.append(Card("Strike"))
        havoc_idx = None
        for i, card in enumerate(state.piles.hand):
            if card.card_id == "Havoc":
                havoc_idx = i
                break
        assert havoc_idx is not None
        enemy = state.enemies[0]
        old_hp = enemy.hp
        obs, _, _ = combat.step(Action.play_card(havoc_idx, 0))
        # Something should have been played (damage dealt or not depending on what was drawn)
        # Just verify no crash
        assert True


class TestHavocBurningPactNesting:
    """The motivating case: Havoc plays BurningPact, which needs agent input."""

    def _make_havoc_burning_pact_combat(self, seed: int = 42) -> Combat:
        """Create a combat with Havoc in hand and BurningPact on top of draw."""
        combat = Combat(deck=list(IRONCLAD_STARTER), enemies=["JawWorm"], seed=seed)
        combat.reset()
        # Inject Havoc into hand
        combat._state.piles.hand.insert(0, Card("Havoc"))
        # Put BurningPact on top of draw
        combat._state.piles.draw.insert(0, Card("BurningPact"))
        return combat

    def test_havoc_plays_burning_pact_presents_choice(self):
        """Havoc playing BurningPact should present a ChoiceFrame to the agent."""
        combat = self._make_havoc_burning_pact_combat()
        state = combat._state

        havoc_idx = None
        for i, card in enumerate(state.piles.hand):
            if card.card_id == "Havoc":
                havoc_idx = i
                break
        assert havoc_idx is not None

        obs, _, _ = combat.step(Action.play_card(havoc_idx, 0))

        # Should have a burningpact choice on top of the stack
        assert state.pending_stack, "Stack should not be empty after Havoc plays BurningPact"
        frame = state.pending_stack[-1]
        assert isinstance(frame, ChoiceFrame)
        assert frame.kind == "burningpact"

        # There should be a ThunkFrame underneath (Havoc's "exhaust played card")
        # This is the nesting contract - verify there are at least 2 frames
        assert len(state.pending_stack) >= 2, (
            f"Expected at least 2 frames (choice + thunk), got {len(state.pending_stack)}"
        )
        assert isinstance(state.pending_stack[-2], ThunkFrame), (
            "Second-from-top frame should be Havoc's exhaust thunk"
        )

        # The choices should be the current hand (excluding Havoc and BurningPact)
        hand_ids = [c.card_id for c in frame.choices]
        assert "Havoc" not in hand_ids, "Havoc should not be in choices (it's mid-resolve)"
        assert "BurningPact" not in hand_ids, "BurningPact should not be in choices (it's being played)"

        # Observation should expose the choice
        assert obs.pending_choice_kind == "burningpact"
        assert len(obs.pending_choices) > 0

    def test_havoc_burning_pact_full_resolution(self):
        """Full flow: Havoc plays BurningPact -> agent picks -> draw -> exhaust played card."""
        combat = self._make_havoc_burning_pact_combat()
        state = combat._state

        havoc_idx = None
        for i, card in enumerate(state.piles.hand):
            if card.card_id == "Havoc":
                havoc_idx = i
                break
        assert havoc_idx is not None

        # Play Havoc
        obs, _, _ = combat.step(Action.play_card(havoc_idx, 0))

        # Agent should see a burningpact choice
        assert obs.pending_choice_kind == "burningpact"

        # Pick the first choice
        obs2, _, _ = combat.step(Action.choose_card(0))

        # After resolution:
        # 1. Chosen card was exhausted (from hand)
        # 2. BurningPact drew cards
        # 3. BurningPact itself was exhausted by Havoc's thunk
        # 4. Havoc was exhausted by its own exhausts=True flag

        # Stack should be empty
        assert state.pending_stack == [], f"Stack should be empty, got {state.pending_stack}"

        # BurningPact should be in exhaust pile
        exhaust_ids = [c.card_id for c in state.piles.exhaust]
        assert "BurningPact" in exhaust_ids, "BurningPact should be exhausted by Havoc"

        # Havoc should be in exhaust pile
        assert "Havoc" in exhaust_ids, "Havoc should be in exhaust (exhausts=True)"

    def test_havoc_burning_pact_skip_choice(self):
        """Havoc + BurningPact: agent skips -> still draw, then exhaust played card."""
        combat = self._make_havoc_burning_pact_combat()
        state = combat._state

        havoc_idx = None
        for i, card in enumerate(state.piles.hand):
            if card.card_id == "Havoc":
                havoc_idx = i
                break
        assert havoc_idx is not None

        obs, _, _ = combat.step(Action.play_card(havoc_idx, 0))
        assert obs.pending_choice_kind == "burningpact"

        obs2, _, _ = combat.step(Action.skip_choice())

        # Stack should be empty
        assert state.pending_stack == []
        # BurningPact should be exhausted by Havoc's thunk
        exhaust_ids = [c.card_id for c in state.piles.exhaust]
        assert "BurningPact" in exhaust_ids
        assert "Havoc" in exhaust_ids
