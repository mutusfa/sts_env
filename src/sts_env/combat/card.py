from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cards import CardSpec


@dataclass(eq=False, slots=True)  # drop slots=True to allow @cached_property
class Card:
    card_id: str
    cost_override: int | None = (
        None  # None = use spec cost; set by potion-generated cards
    )
    cost_override_duration: str | None = (
        None  # "turn" = cleared at EOT, "combat" = persists; None = no override
    )
    exhausts_override: bool | None = None  # None = use spec exhausts
    corrupted: bool = False  # True if Corruption power has modified this card
    _spec: CardSpec | None = None

    @property
    def spec(self) -> CardSpec:
        return self._spec

    def __post_init__(self) -> None:
        from sts_env.combat.cards import get_spec
        self._spec = get_spec(self.card_id)

    def effective_cost(self) -> int:
        """Return the effective cost of this card, accounting for overrides."""
        if self.cost_override is not None:
            return self.cost_override
        base_cost = self.spec.cost
        if self.upgraded:
            base_cost += self.spec.upgrade.get("cost", 0)
        return base_cost

    def effective_exhausts(self) -> bool:
        """Return whether this card exhausts when played, accounting for overrides."""
        if self.exhausts_override is not None:
            return self.exhausts_override
        return self.spec.exhausts

    def __eq__(self, other: object) -> bool:
        """Compare equal to another Card (by all fields) or to a plain string card_id."""
        if isinstance(other, str):
            return self.card_id == other
        if isinstance(other, Card):
            return (
                self.card_id == other.card_id
                and self.cost_override == other.cost_override
                and self.cost_override_duration == other.cost_override_duration
                and self.exhausts_override == other.exhausts_override
                and self.corrupted == other.corrupted
            )
        return NotImplemented

    def __hash__(self) -> int:
        """Hash by card_id so Card("X") and the string "X" hash identically.

        Override variants hash the same as the base card; callers
        that need full identity should use to_key() explicitly.
        """
        return hash(self.card_id)

    def to_key(self) -> tuple:
        """Fully-qualified hashable key for transposition tables."""
        # Use sortable sentinels for None (must be comparable with int/bool)
        co = self.cost_override if self.cost_override is not None else -1
        eo = self.exhausts_override if self.exhausts_override is not None else -1
        cd = self.cost_override_duration or ""
        return (self.card_id, co, cd, eo, self.corrupted)

    @property
    def upgraded(self) -> bool:
        return self.card_id.endswith("+")

    @property
    def base_id(self) -> str:
        return self.card_id.rstrip("+")

    def clear_cost_override(self) -> None:
        """Reset cost override at end of turn.

        Only clears overrides with duration="turn". Duration="combat"
        overrides persist until combat ends. Corruption-stamped cards
        (corrupted=True) are handled via duration="combat" set at stamp time.
        """
        if self.cost_override_duration == "turn":
            self.cost_override = None
            self.cost_override_duration = None
