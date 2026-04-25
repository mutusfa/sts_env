from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, eq=True)
class Card:
    card_id: str
    cost_override: int | None = None  # None = use spec cost; set by potion-generated cards
    upgraded: int = 0                 # 0 = base, future use for card upgrades

    def to_key(self) -> tuple:
        """Hashable key for transposition tables."""
        return (self.card_id, self.cost_override, self.upgraded)

    def clear_cost_override(self) -> None:
        """Reset cost override (called at end of turn for potion-generated cards)."""
        self.cost_override = None
