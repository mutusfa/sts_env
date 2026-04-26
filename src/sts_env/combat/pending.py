"""Effect stack: frames that pause resolution for agent input or defer work.

ChoiceFrame  -- gates on agent input (CHOOSE_CARD / SKIP_CHOICE).
ThunkFrame   -- zero-arg callable, auto-drained by the engine before yielding
                control back to the agent.

The stack is LIFO: the most recently pushed frame resolves first.
This lets Havoc push a "exhaust played card" thunk *before* invoking
the played card's own effects (e.g. BurningPact), which in turn push
their own choice frame on top.  Resolution order: BurningPact choice ->
BurningPact draw -> Havoc exhaust -> Havoc discard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Union

from .card import Card

if TYPE_CHECKING:
    from .state import CombatState


@dataclass
class ChoiceFrame:
    """A frame that requires the agent to pick a card (or skip)."""

    choices: list[Card]
    kind: str  # observation label (e.g. "burningpact", "potion", "headbutt")
    on_choose: Callable[["CombatState", Card], None]
    on_skip: Callable[["CombatState"], None] = lambda s: None


@dataclass
class ThunkFrame:
    """A frame that auto-runs when it becomes the top of the stack."""

    run: Callable[["CombatState"], None]
    label: str = ""  # debug / logging aid


Frame = Union[ChoiceFrame, ThunkFrame]
