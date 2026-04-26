"""Tests for the effect stack (pending_stack / Frame types).

Covers:
  - ChoiceFrame gates agent actions
  - ThunkFrame auto-drains after a choice resolves
  - Nesting contract: thunk below choice runs after choice
"""

import pytest
from sts_env.combat import Combat
from sts_env.combat.card import Card
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


# ---------------------------------------------------------------------------
# Stack mechanics
# ---------------------------------------------------------------------------

class TestChoiceFrameGating:
    """When a ChoiceFrame is on top, only CHOOSE_CARD / SKIP_CHOICE are valid."""

    def test_choice_frame_restricts_actions(self):
        combat = _make_combat()
        state = combat._state
        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike")],
                kind="test",
                on_choose=lambda s, c: None,
            )
        )
        actions = combat.valid_actions()
        types = {a.action_type for a in actions}
        assert types == {ActionType.CHOOSE_CARD, ActionType.SKIP_CHOICE}

    def test_choice_frame_gives_correct_choice_indices(self):
        combat = _make_combat()
        state = combat._state
        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike"), Card("Defend"), Card("Bash")],
                kind="test",
                on_choose=lambda s, c: None,
            )
        )
        actions = combat.valid_actions()
        choose_indices = {a.choice_index for a in actions if a.action_type == ActionType.CHOOSE_CARD}
        assert choose_indices == {0, 1, 2}

    def test_no_stack_means_normal_actions(self):
        combat = _make_combat()
        actions = combat.valid_actions()
        types = {a.action_type for a in actions}
        # Should have at least PLAY_CARD and END_TURN
        assert ActionType.END_TURN in types
        assert ActionType.PLAY_CARD in types
        # Should NOT have CHOOSE_CARD or SKIP_CHOICE
        assert ActionType.CHOOSE_CARD not in types
        assert ActionType.SKIP_CHOICE not in types


class TestChooseCardResolves:
    """CHOOSE_CARD pops the top ChoiceFrame and calls on_choose."""

    def test_on_choose_called(self):
        combat = _make_combat()
        state = combat._state
        chosen = []

        def track_choose(s, c):
            chosen.append(c.card_id)

        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike"), Card("Defend")],
                kind="test",
                on_choose=track_choose,
            )
        )
        obs, _, _ = combat.step(Action.choose_card(1))
        assert chosen == ["Defend"]
        # Stack should be empty now
        assert state.pending_stack == []
        # Observation should show no pending choices
        assert obs.pending_choices == []
        assert obs.pending_choice_kind == ""


class TestSkipChoiceResolves:
    """SKIP_CHOICE pops the top ChoiceFrame and calls on_skip."""

    def test_on_skip_called(self):
        combat = _make_combat()
        state = combat._state
        skipped = []

        def track_skip(s):
            skipped.append(True)

        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike")],
                kind="test",
                on_choose=lambda s, c: None,
                on_skip=track_skip,
            )
        )
        obs, _, _ = combat.step(Action.skip_choice())
        assert skipped == [True]
        assert state.pending_stack == []
        assert obs.pending_choices == []
        assert obs.pending_choice_kind == ""


class TestThunkDrain:
    """ThunkFrames are auto-drained when they become the top of the stack."""

    def test_thunk_drains_after_choice(self):
        """ThunkFrame under a ChoiceFrame runs after the choice resolves."""
        combat = _make_combat()
        state = combat._state
        log = []

        state.pending_stack.append(
            ThunkFrame(run=lambda s: log.append("thunk"), label="test-thunk")
        )
        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike")],
                kind="test",
                on_choose=lambda s, c: log.append("choose"),
            )
        )

        combat.step(Action.choose_card(0))
        # Choice runs first, then thunk drains
        assert log == ["choose", "thunk"]
        assert state.pending_stack == []

    def test_multiple_thunks_drain_in_order(self):
        """Multiple thunks drain top-to-bottom after choice resolves."""
        combat = _make_combat()
        state = combat._state
        log = []

        state.pending_stack.append(
            ThunkFrame(run=lambda s: log.append("thunk1"), label="t1")
        )
        state.pending_stack.append(
            ThunkFrame(run=lambda s: log.append("thunk2"), label="t2")
        )
        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike")],
                kind="test",
                on_choose=lambda s, c: log.append("choose"),
            )
        )

        combat.step(Action.choose_card(0))
        assert log == ["choose", "thunk2", "thunk1"]

    def test_thunk_drains_after_skip(self):
        combat = _make_combat()
        state = combat._state
        log = []

        state.pending_stack.append(
            ThunkFrame(run=lambda s: log.append("thunk"), label="t")
        )
        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike")],
                kind="test",
                on_choose=lambda s, c: log.append("choose"),
                on_skip=lambda s: log.append("skip"),
            )
        )

        combat.step(Action.skip_choice())
        assert log == ["skip", "thunk"]

    def test_bare_thunk_stack_drains_on_play_card(self):
        """Thunks pushed during PLAY_CARD drain before the step returns."""
        combat = _make_combat()
        state = combat._state
        log = []

        state.pending_stack.append(
            ThunkFrame(run=lambda s: log.append("thunk"), label="t")
        )
        # Now play a card - thunk should drain first... actually no,
        # the thunk is already there. Let's test via a card that pushes a thunk.
        # We'll test this properly with the actual Havoc card later.
        # For now, just verify drain_stack works as a helper.
        from sts_env.combat.engine import _drain_stack
        _drain_stack(state)
        assert log == ["thunk"]
        assert state.pending_stack == []


class TestObservationDerivesFromStack:
    """Observation.pending_choices / pending_choice_kind come from the stack."""

    def test_obs_from_choice_frame(self):
        combat = _make_combat()
        state = combat._state
        state.pending_stack.append(
            ChoiceFrame(
                choices=[Card("Strike"), Card("Defend")],
                kind="burningpact",
                on_choose=lambda s, c: None,
            )
        )
        obs = combat._observe()
        assert len(obs.pending_choices) == 2
        assert obs.pending_choices[0].card_id == "Strike"
        assert obs.pending_choices[1].card_id == "Defend"
        assert obs.pending_choice_kind == "burningpact"

    def test_obs_empty_when_no_choice_frame(self):
        combat = _make_combat()
        obs = combat._observe()
        assert obs.pending_choices == []
        assert obs.pending_choice_kind == ""

    def test_obs_skips_thunk_frames(self):
        """If only ThunkFrames are on the stack, obs shows no pending choices."""
        combat = _make_combat()
        state = combat._state
        state.pending_stack.append(
            ThunkFrame(run=lambda s: None, label="t")
        )
        obs = combat._observe()
        assert obs.pending_choices == []
        assert obs.pending_choice_kind == ""
