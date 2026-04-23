"""Card definitions for the Ironclad starter set + selected commons.

Each card has:
  - A CardSpec (static metadata: cost, type, target requirement).
  - A handler function: play(ctx, hand_index, target_index) -> None.
    The handler mutates CombatState directly.

Cards in v1:
  Starter:  Strike x5, Defend x4, Bash x1
  Curse:    AscendersBane (unplayable)
  Commons:  PommelStrike, ShrugItOff, IronWave, Cleave, Anger
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .state import CombatState


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    CURSE = auto()
    STATUS = auto()


class TargetType(Enum):
    SINGLE_ENEMY = auto()
    ALL_ENEMIES = auto()
    NONE = auto()       # self-targeting skills, powers


@dataclass(frozen=True)
class CardSpec:
    card_id: str
    cost: int           # -1 = unplayable (curse/status)
    card_type: CardType
    target: TargetType


# Handler signature
CardHandler = Callable[["CombatState", int, int], None]

_SPECS: dict[str, CardSpec] = {}
_HANDLERS: dict[str, CardHandler] = {}


def _register(spec: CardSpec, handler: CardHandler) -> None:
    _SPECS[spec.card_id] = spec
    _HANDLERS[spec.card_id] = handler


def get_spec(card_id: str) -> CardSpec:
    return _SPECS[card_id]


def play_card(state: "CombatState", hand_index: int, target_index: int) -> None:
    """Validate and execute a card play, updating state in place."""
    card_id = state.piles.hand[hand_index]
    spec = _SPECS[card_id]

    if spec.cost < 0:
        raise ValueError(f"Card {card_id!r} is unplayable.")
    if spec.cost > state.energy:
        raise ValueError(
            f"Not enough energy to play {card_id!r}: need {spec.cost}, have {state.energy}."
        )
    if spec.target == TargetType.SINGLE_ENEMY and not (
        0 <= target_index < len(state.enemies)
    ):
        raise ValueError(f"Invalid target_index {target_index}.")

    state.energy -= spec.cost
    card = state.piles.play_card(hand_index)
    _HANDLERS[card_id](state, hand_index, target_index)
    state.piles.move_to_discard(card)


# ---------------------------------------------------------------------------
# Individual card handlers
# ---------------------------------------------------------------------------

def _strike(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import calc_damage, apply_damage

    raw = calc_damage(6, state.player_powers, state.enemies[ti].powers)
    nb, nhp = apply_damage(raw, state.enemies[ti].block, state.enemies[ti].hp)
    state.enemies[ti].block = nb
    state.enemies[ti].hp = nhp


_register(
    CardSpec("Strike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _strike,
)


def _defend(state: "CombatState", _hi: int, _ti: int) -> None:
    state.player_block += 5


_register(
    CardSpec("Defend", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _defend,
)


def _bash(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import calc_damage, apply_damage

    raw = calc_damage(8, state.player_powers, state.enemies[ti].powers)
    nb, nhp = apply_damage(raw, state.enemies[ti].block, state.enemies[ti].hp)
    state.enemies[ti].block = nb
    state.enemies[ti].hp = nhp
    state.enemies[ti].powers.vulnerable += 2


_register(
    CardSpec("Bash", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _bash,
)


def _ascenders_bane(state: "CombatState", _hi: int, _ti: int) -> None:
    raise ValueError("AscendersBane is unplayable.")


_register(
    CardSpec("AscendersBane", cost=-1, card_type=CardType.CURSE, target=TargetType.NONE),
    _ascenders_bane,
)


def _pommel_strike(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import calc_damage, apply_damage

    raw = calc_damage(9, state.player_powers, state.enemies[ti].powers)
    nb, nhp = apply_damage(raw, state.enemies[ti].block, state.enemies[ti].hp)
    state.enemies[ti].block = nb
    state.enemies[ti].hp = nhp
    state.piles.draw_cards(1, state.rng)


_register(
    CardSpec("PommelStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _pommel_strike,
)


def _shrug_it_off(state: "CombatState", _hi: int, _ti: int) -> None:
    state.player_block += 8
    state.piles.draw_cards(1, state.rng)


_register(
    CardSpec("ShrugItOff", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _shrug_it_off,
)


def _iron_wave(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import calc_damage, apply_damage

    raw = calc_damage(5, state.player_powers, state.enemies[ti].powers)
    nb, nhp = apply_damage(raw, state.enemies[ti].block, state.enemies[ti].hp)
    state.enemies[ti].block = nb
    state.enemies[ti].hp = nhp
    state.player_block += 5


_register(
    CardSpec("IronWave", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _iron_wave,
)


def _cleave(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import calc_damage, apply_damage

    for enemy in state.enemies:
        if enemy.hp > 0:
            raw = calc_damage(8, state.player_powers, enemy.powers)
            nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
            enemy.block = nb
            enemy.hp = nhp


_register(
    CardSpec("Cleave", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES),
    _cleave,
)


def _anger(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import calc_damage, apply_damage

    raw = calc_damage(6, state.player_powers, state.enemies[ti].powers)
    nb, nhp = apply_damage(raw, state.enemies[ti].block, state.enemies[ti].hp)
    state.enemies[ti].block = nb
    state.enemies[ti].hp = nhp
    state.piles.add_to_discard("Anger")


_register(
    CardSpec("Anger", cost=0, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _anger,
)
