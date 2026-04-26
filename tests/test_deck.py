"""Tests for deck pile primitives."""

import pytest

from sts_env.combat.deck import Piles
from sts_env.combat.rng import RNG


def test_draw_from_non_empty():
    piles = Piles(draw=["A", "B", "C"])
    rng = RNG(0)
    drawn = piles.draw_cards(2, rng)
    assert drawn == ["A", "B"]
    assert piles.hand == ["A", "B"]
    assert piles.draw == ["C"]


def test_draw_all_from_draw_pile():
    piles = Piles(draw=["A", "B"])
    rng = RNG(0)
    drawn = piles.draw_cards(2, rng)
    assert drawn == ["A", "B"]
    assert piles.draw == []
    assert piles.hand == ["A", "B"]


def test_draw_triggers_shuffle_of_discard():
    """When draw pile is empty, discard is shuffled into draw before drawing."""
    piles = Piles(draw=[], discard=["X", "Y", "Z"])
    rng = RNG(42)
    drawn = piles.draw_cards(2, rng)
    assert len(drawn) == 2
    assert len(piles.hand) == 2
    # All three cards came from discard; one should still be in draw
    assert len(piles.draw) == 1
    assert piles.discard == []


def test_draw_does_not_shuffle_if_draw_not_empty():
    """Shuffle should NOT happen while there are still cards in the draw pile."""
    piles = Piles(draw=["A"], discard=["X", "Y"])
    rng = RNG(0)
    piles.draw_cards(1, rng)
    # Only "A" should be drawn; discard untouched
    assert piles.hand == ["A"]
    assert piles.discard == ["X", "Y"]
    assert piles.draw == []


def test_draw_mid_hand_triggers_single_shuffle():
    """Drawing 3 with 1 in draw + 2 in discard should shuffle once."""
    piles = Piles(draw=["A"], discard=["X", "Y"])
    rng = RNG(0)
    drawn = piles.draw_cards(3, rng)
    assert len(drawn) == 3
    assert piles.hand == list(drawn)
    assert piles.discard == []
    assert piles.draw == []


def test_draw_nothing_when_both_empty():
    piles = Piles(draw=[], discard=[])
    rng = RNG(0)
    drawn = piles.draw_cards(5, rng)
    assert drawn == []
    assert piles.hand == []


def test_exhaust_removes_card():
    piles = Piles(draw=["A", "B"])
    piles.move_to_exhaust("A")
    assert piles.exhaust == ["A"]
    # draw pile is untouched (exhaust is independent)
    assert piles.draw == ["A", "B"]


def test_play_card_removes_from_hand():
    piles = Piles(hand=["Strike", "Defend"])
    card = piles.play_card(0)
    assert card == "Strike"
    assert piles.hand == ["Defend"]


def test_move_to_discard():
    piles = Piles()
    piles.move_to_discard("Strike")
    assert piles.discard == ["Strike"]


def test_place_on_top_and_draw_order():
    """Card placed on top should be the next card drawn."""
    piles = Piles(draw=["A", "B"])
    piles.place_on_top("TOP")
    rng = RNG(0)
    drawn = piles.draw_cards(3, rng)
    assert drawn == ["TOP", "A", "B"]


def test_place_on_top_survives_across_draws():
    """Top card stays at top even after drawing one card from below it."""
    piles = Piles(draw=["A", "B", "C"])
    piles.place_on_top("TOP")
    rng = RNG(0)
    first = piles.draw_cards(1, rng)
    assert first == ["TOP"]
    rest = piles.draw_cards(2, rng)
    assert rest == ["A", "B"]


def test_place_on_top_not_reshuffled_with_later_shuffle():
    """If the draw pile empties and triggers a shuffle, TOP card is already
    consumed before the shuffle (or sits at top of the new pile if still there).

    This test verifies: when TOP is placed, then other cards are drawn until
    draw is empty, the shuffle of discard does NOT mix TOP into the shuffle.
    Specifically: TOP is drawn first; if TOP is the only remaining card and
    discard needs to be shuffled in, TOP is drawn before any shuffle occurs.
    """
    # Draw: ["TOP"] only, discard has 2 cards
    piles = Piles(draw=[], discard=["X", "Y"])
    piles.place_on_top("TOP")
    rng = RNG(42)
    # Draw 1 — should get TOP without triggering shuffle
    drawn = piles.draw_cards(1, rng)
    assert drawn == ["TOP"]
    assert piles.discard == ["X", "Y"]
    assert piles.draw == []


def test_discard_hand():
    piles = Piles(hand=["A", "B", "C"], discard=["X"])
    piles.discard_hand(RNG(0))
    assert piles.hand == []
    assert set(piles.discard) == {"A", "B", "C", "X"}


def test_add_to_discard():
    piles = Piles()
    piles.add_to_discard("Anger")
    assert piles.discard == ["Anger"]


def test_shuffle_determinism():
    """Same seed produces same shuffle order."""
    discard = ["A", "B", "C", "D", "E"]
    p1 = Piles(discard=list(discard))
    p2 = Piles(discard=list(discard))
    p1.shuffle_draw_from_discard(RNG(7))
    p2.shuffle_draw_from_discard(RNG(7))
    assert p1.draw == p2.draw


def test_shuffle_different_seeds_likely_differ():
    """Different seeds very likely produce different orders."""
    discard = ["A", "B", "C", "D", "E", "F", "G"]
    p1 = Piles(discard=list(discard))
    p2 = Piles(discard=list(discard))
    p1.shuffle_draw_from_discard(RNG(1))
    p2.shuffle_draw_from_discard(RNG(2))
    # 1/5040 chance of being equal — acceptable flakiness risk
    assert p1.draw != p2.draw
