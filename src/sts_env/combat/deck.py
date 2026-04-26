"""Deck pile primitives.

A deck in STS is split across four piles at any time:
  draw pile  – cards you will draw from (top = index 0 convention used here)
  hand       – currently held cards
  discard    – played or discarded cards
  exhaust    – permanently removed cards for this combat

Shuffle trigger: only when draw() is called and the draw pile is empty.
At that point the discard pile is shuffled and becomes the new draw pile.

"Place on top of draw": inserts at index 0 of the draw list. These cards are
NOT re-shuffled unless the draw pile later empties and a shuffle is triggered.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .card import Card
from .rng import RNG


@dataclass(slots=True)
class Piles:
    """All four card piles for one combat.

    Cards are represented as Card objects.
    Multiple copies are distinct list entries.
    """

    draw: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    exhaust: list[Card] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def shuffle_draw_from_discard(self, rng: RNG) -> None:
        """Move all discard cards into draw pile (shuffled) and clear discard."""
        self.draw.extend(self.discard)
        self.discard.clear()
        rng.shuffle(self.draw)

    def draw_cards(self, n: int, rng: RNG) -> list[Card]:
        """Draw up to *n* cards into hand; triggers reshuffle if needed."""
        drawn: list[Card] = []
        for _ in range(n):
            if not self.draw:
                if not self.discard:
                    break
                self.shuffle_draw_from_discard(rng)
            if self.draw:
                card = self.draw.pop(0)
                self.hand.append(card)
                drawn.append(card)
        return drawn

    def place_on_top(self, card: Card) -> None:
        """Insert a card at the top of the draw pile (index 0)."""
        self.draw.insert(0, card)

    def play_card(self, hand_index: int) -> Card:
        """Remove a card from hand and return it (to be moved to discard or exhaust)."""
        return self.hand.pop(hand_index)

    def move_to_discard(self, card: Card) -> None:
        self.discard.append(card)

    def move_to_exhaust(self, card: Card) -> None:
        self.exhaust.append(card)

    def add_to_discard(self, card: Card) -> None:
        """Add a card directly to the discard pile (e.g. Anger's copy)."""
        self.discard.append(card)

    def add_to_hand(self, card: Card) -> None:
        """Add a card directly to hand (e.g. PowerThrough's Wounds)."""
        self.hand.append(card)

    def shuffle_into_draw(self, card: Card, rng: RNG) -> None:
        """Insert a card at a random position in the draw pile (e.g. WildStrike's Wound)."""
        pos = rng.randint(0, len(self.draw))
        self.draw.insert(pos, card)

    def discard_hand(self, rng: RNG) -> None:  # noqa: ARG002 (rng reserved for future on-discard effects)
        """Move all cards from hand to discard at end of player turn."""
        self.discard.extend(self.hand)
        self.hand.clear()
