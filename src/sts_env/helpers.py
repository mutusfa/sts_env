"""Shared helpers used by both run-level and combat-level code."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .combat.rng import RNG


def roll_d100(rng: RNG) -> int:
    """Return a uniform integer in [0, 99] (C++ d100)."""
    return rng.randint(0, 99)


def below_d100(roll: int, prob: float) -> bool:
    """True when *roll* falls below *prob* on a d100 scale."""
    return roll < round(prob * 100)


def d100_threshold(prob: float) -> int:
    """Exclusive cumulative upper bound for ``roll < threshold`` checks."""
    return round(prob * 100)


def increase_max_hp(obj: object, amount: int) -> None:
    """Increase max HP by *amount* and also heal by the same amount.

    Every max-HP increase in Slay the Spire also heals the player.
    Works with any object that has ``player_hp`` and ``player_max_hp``
    attributes (``Character``, ``CombatState``, etc.).
    """
    obj.player_max_hp += amount  # type: ignore[attr-defined]
    obj.player_hp = min(  # type: ignore[attr-defined]
        obj.player_hp + amount,  # type: ignore[attr-defined]
        obj.player_max_hp,  # type: ignore[attr-defined]
    )
