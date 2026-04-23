"""Core state dataclasses and the Action / Observation types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from .deck import Piles
from .powers import Powers
from .rng import RNG


# ---------------------------------------------------------------------------
# Combat participants
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EnemyState:
    name: str
    hp: int
    max_hp: int
    block: int = 0
    powers: Powers = field(default_factory=Powers)
    move_history: list[str] = field(default_factory=list)

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass(slots=True)
class CombatState:
    """Complete mutable state for one combat encounter."""
    player_hp: int
    player_max_hp: int
    player_block: int
    player_powers: Powers
    energy: int
    piles: Piles
    enemies: list[EnemyState]
    rng: RNG
    turn: int = 0


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

class ActionType(Enum):
    PLAY_CARD = auto()
    END_TURN = auto()


@dataclass(frozen=True)
class Action:
    action_type: ActionType
    hand_index: int = 0
    target_index: int = 0

    @staticmethod
    def play_card(hand_index: int, target_index: int = 0) -> "Action":
        return Action(ActionType.PLAY_CARD, hand_index=hand_index, target_index=target_index)

    @staticmethod
    def end_turn() -> "Action":
        return Action(ActionType.END_TURN)


# ---------------------------------------------------------------------------
# Observation (read-only view returned after each step)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnemyObs:
    name: str
    hp: int
    max_hp: int
    block: int
    powers: dict[str, Any]
    intent_type: str
    intent_damage: int
    intent_hits: int
    intent_block_gain: int


@dataclass(frozen=True)
class Observation:
    player_hp: int
    player_max_hp: int
    player_block: int
    player_powers: dict[str, Any]
    energy: int
    hand: list[str]
    draw_pile: dict[str, int]
    discard_pile: dict[str, int]
    exhaust_pile: dict[str, int]
    enemies: list[EnemyObs]
    done: bool
    player_dead: bool
    turn: int
