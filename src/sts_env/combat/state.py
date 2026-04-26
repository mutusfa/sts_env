"""Core state dataclasses and the Action / Observation types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from .card import Card
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
    misc: int = 0  # per-enemy scratch space: louse bite dmg, wizard charge counter, etc.
    pending_split: bool = False  # set when HP crosses <=50% for large slimes
    is_escaping: bool = False    # Looter/Mugger: fled combat; counts as dead for win condition
    skill_played_str: int = 0    # Gremlin Nob: gain this much strength when player plays a Skill

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
    potions: list[str] = field(default_factory=list)
    max_potion_slots: int = 3
    energy_loss_next_turn: int = 0  # accumulated energy loss (e.g. Gremlin Nob Bellow)
    pending_choices: list[Card] = field(default_factory=list)
    pending_choice_kind: str = ""   # "potion" | "headbutt" | "armaments" | "dualwield" | "burningpact"
    pending_choice_extra: int = 0   # generic int payload per choice kind (e.g. draw count for burningpact)
    rampage_extra: int = 0         # accumulated Rampage bonus this combat


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

class ActionType(Enum):
    PLAY_CARD = auto()
    END_TURN = auto()
    USE_POTION = auto()
    DISCARD_POTION = auto()
    CHOOSE_CARD = auto()
    SKIP_CHOICE = auto()


@dataclass(frozen=True)
class Action:
    action_type: ActionType
    hand_index: int = 0
    target_index: int = 0
    potion_index: int = 0
    choice_index: int = 0

    @staticmethod
    def play_card(hand_index: int, target_index: int = 0) -> "Action":
        return Action(ActionType.PLAY_CARD, hand_index=hand_index, target_index=target_index)

    @staticmethod
    def end_turn() -> "Action":
        return Action(ActionType.END_TURN)

    @staticmethod
    def use_potion(potion_index: int, target_index: int = 0) -> "Action":
        return Action(ActionType.USE_POTION, potion_index=potion_index, target_index=target_index)

    @staticmethod
    def discard_potion(potion_index: int) -> "Action":
        return Action(ActionType.DISCARD_POTION, potion_index=potion_index)

    @staticmethod
    def choose_card(choice_index: int) -> "Action":
        return Action(ActionType.CHOOSE_CARD, choice_index=choice_index)

    @staticmethod
    def skip_choice() -> "Action":
        return Action(ActionType.SKIP_CHOICE)


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
    intent_damage_effective: int
    intent_hits: int
    intent_block_gain: int


@dataclass(frozen=True)
class Observation:
    player_hp: int
    player_max_hp: int
    player_block: int
    player_powers: dict[str, Any]
    energy: int
    hand: list[Card]
    draw_pile: dict[str, int]
    discard_pile: dict[str, int]
    exhaust_pile: dict[str, int]
    enemies: list[EnemyObs]
    done: bool
    player_dead: bool
    turn: int
    potions: list[str]
    max_potion_slots: int
    max_hp_gained: int = 0  # max HP gained this combat (e.g. Feed), exposed for strategic valuation
    pending_choices: list[Card] = ()
    pending_choice_kind: str = ""
