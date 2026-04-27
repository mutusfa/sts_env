from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, eq=False)
class Card:
    card_id: str
    cost_override: int | None = (
        None  # None = use spec cost; set by potion-generated cards
    )

    def __eq__(self, other: object) -> bool:
        """Compare equal to another Card (by all fields) or to a plain string card_id."""
        if isinstance(other, str):
            return self.card_id == other
        if isinstance(other, Card):
            return (
                self.card_id == other.card_id
                and self.cost_override == other.cost_override
            )
        return NotImplemented

    def __hash__(self) -> int:
        """Hash by card_id so Card("X") and the string "X" hash identically.

        cost_override variants hash the same as the base card; callers
        that need full identity should use to_key() explicitly.
        """
        return hash(self.card_id)

    def to_key(self) -> tuple:
        """Fully-qualified hashable key for transposition tables."""
        # Use a sortable sentinel for None (must be comparable with int)
        co = self.cost_override if self.cost_override is not None else -1
        return (self.card_id, co)

    @property
    def upgraded(self) -> bool:
        return self.card_id.endswith("+")

    @property
    def base_id(self) -> str:
        return self.card_id.rstrip("+")

    def clear_cost_override(self) -> None:
        """Reset cost override (called at end of turn for potion-generated cards)."""
        self.cost_override = None
