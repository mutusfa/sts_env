"""Potion definitions for v1.

Registry pattern mirrors cards.py.

Potions in v1 (13 total):
  Class-neutral: BlockPotion, EnergyPotion, FirePotion, ExplosivePotion,
                 StrengthPotion, SwiftPotion, DexterityPotion, SpeedPotion,
                 SteroidPotion, FlexPotion, FearPotion
  Ironclad-only: BloodPotion, HeartOfIron

Deferred:
  AttackPotion, SkillPotion, PowerPotion — require mid-action card-choice UI.
  FairyInABottle, SmokeBomb — special trigger/context mechanics.

Damage notes:
  Potion damage in StS bypasses player Strength, Weak, and enemy Vulnerable.
  Handlers use a fresh Powers() for calc_damage, not state.player_powers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .card import Card
from .cards import CardType, TargetType, _SPECS
from .powers import Powers, apply_damage, calc_damage

if TYPE_CHECKING:
    from .state import CombatState


@dataclass(frozen=True)
class PotionSpec:
    potion_id: str
    target: TargetType  # SINGLE_ENEMY, ALL_ENEMIES, or NONE (self-targeting)


PotionHandler = Callable[["CombatState", int], None]  # (state, target_index)

_SPECS: dict[str, PotionSpec] = {}
_HANDLERS: dict[str, PotionHandler] = {}


def potion(potion_id: str, target: TargetType) -> Callable[[PotionHandler], PotionHandler]:
    def decorator(fn: PotionHandler) -> PotionHandler:
        _SPECS[potion_id] = PotionSpec(potion_id, target)
        _HANDLERS[potion_id] = fn
        return fn
    return decorator


def get_spec(potion_id: str) -> PotionSpec:
    try:
        return _SPECS[potion_id]
    except KeyError:
        raise KeyError(f"Unknown potion: {potion_id!r}") from None


def use_potion(state: "CombatState", potion_index: int, target_index: int) -> None:
    """Execute a potion's effect and remove it from the slot list."""
    potion_id = state.potions[potion_index]
    _HANDLERS[potion_id](state, target_index)
    state.potions.pop(potion_index)


# ---------------------------------------------------------------------------
# Individual potion handlers
# ---------------------------------------------------------------------------

@potion("FirePotion", TargetType.SINGLE_ENEMY)
def _fire_potion(state: "CombatState", ti: int) -> None:
    """Deal 20 damage to target (ignores Strength, Weak, Vulnerable)."""
    enemy = state.enemies[ti]
    raw = calc_damage(20, Powers(), Powers())
    nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block, enemy.hp = nb, nhp


@potion("ExplosivePotion", TargetType.ALL_ENEMIES)
def _explosive_potion(state: "CombatState", _ti: int) -> None:
    """Deal 10 damage to ALL enemies (ignores Strength, Weak, Vulnerable)."""
    raw = calc_damage(10, Powers(), Powers())
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
            enemy.block, enemy.hp = nb, nhp


@potion("BlockPotion", TargetType.NONE)
def _block_potion(state: "CombatState", _ti: int) -> None:
    """Gain 12 block (flat, not affected by Frail or Dexterity)."""
    state.player_block += 12


@potion("EnergyPotion", TargetType.NONE)
def _energy_potion(state: "CombatState", _ti: int) -> None:
    """Gain 2 energy."""
    state.energy += 2


@potion("StrengthPotion", TargetType.NONE)
def _strength_potion(state: "CombatState", _ti: int) -> None:
    """Gain 2 Strength permanently (for this combat)."""
    state.player_powers.strength += 2


@potion("SteroidPotion", TargetType.NONE)
def _steroid_potion(state: "CombatState", _ti: int) -> None:
    """Gain 5 Strength; lose 5 Strength at end of turn."""
    state.player_powers.strength += 5
    state.player_powers.strength_loss_eot += 5


@potion("FlexPotion", TargetType.NONE)
def _flex_potion(state: "CombatState", _ti: int) -> None:
    """Gain 5 Strength; lose 5 Strength at end of turn (identical to Steroid in combat)."""
    state.player_powers.strength += 5
    state.player_powers.strength_loss_eot += 5


@potion("DexterityPotion", TargetType.NONE)
def _dexterity_potion(state: "CombatState", _ti: int) -> None:
    """Gain 2 Dexterity permanently (flat bonus to all block gains)."""
    state.player_powers.dexterity += 2


@potion("SpeedPotion", TargetType.NONE)
def _speed_potion(state: "CombatState", _ti: int) -> None:
    """Gain 5 Dexterity; lose 5 Dexterity at end of turn."""
    state.player_powers.dexterity += 5
    state.player_powers.dexterity_loss_eot += 5


@potion("SwiftPotion", TargetType.NONE)
def _swift_potion(state: "CombatState", _ti: int) -> None:
    """Draw 3 cards."""
    state.piles.draw_cards(3, state.rng)


@potion("FearPotion", TargetType.SINGLE_ENEMY)
def _fear_potion(state: "CombatState", ti: int) -> None:
    """Apply 3 Vulnerable to target."""
    state.enemies[ti].powers.vulnerable += 3


# ---------------------------------------------------------------------------
# Ironclad-only
# ---------------------------------------------------------------------------

@potion("BloodPotion", TargetType.NONE)
def _blood_potion(state: "CombatState", _ti: int) -> None:
    """Heal floor(20% of max HP)."""
    heal = math.floor(state.player_max_hp * 0.20)
    state.player_hp = min(state.player_max_hp, state.player_hp + heal)


@potion("HeartOfIron", TargetType.NONE)
def _heart_of_iron(state: "CombatState", _ti: int) -> None:
    """Gain Metallicize 4: gain 4 block at end of each player turn."""
    state.player_powers.metallicize += 4


# ---------------------------------------------------------------------------
# Choose-a-card potions (add a random card to hand at cost 0)
# ---------------------------------------------------------------------------

def _get_playable_cards_by_type(card_type) -> list[str]:
    """Return card IDs of playable (cost >= 0) cards of the given CardType."""
    return [cid for cid, spec in _SPECS.items()
            if spec.card_type == card_type and spec.cost >= 0]


@potion("AttackPotion", TargetType.NONE)
def _attack_potion(state: "CombatState", _ti: int) -> None:
    """Present 3 random Attack cards to choose from. Agent picks one via CHOOSE_CARD."""
    pool = _get_playable_cards_by_type(CardType.ATTACK)
    k = min(3, len(pool))
    choices = state.rng.sample(pool, k)
    state.potion_choices = [Card(cid, cost_override=0) for cid in choices]


@potion("SkillPotion", TargetType.NONE)
def _skill_potion(state: "CombatState", _ti: int) -> None:
    """Present 3 random Skill cards to choose from. Agent picks one via CHOOSE_CARD."""
    pool = _get_playable_cards_by_type(CardType.SKILL)
    k = min(3, len(pool))
    choices = state.rng.sample(pool, k)
    state.potion_choices = [Card(cid, cost_override=0) for cid in choices]


@potion("PowerPotion", TargetType.NONE)
def _power_potion(state: "CombatState", _ti: int) -> None:
    """Present 3 random Power cards to choose from. Agent picks one via CHOOSE_CARD."""
    pool = _get_playable_cards_by_type(CardType.POWER)
    k = min(3, len(pool))
    choices = state.rng.sample(pool, k)
    state.potion_choices = [Card(cid, cost_override=0) for cid in choices]
