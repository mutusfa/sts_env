"""Status effects and powers, plus the central damage calculation.

Damage formula (mirrors StS 1):
  1. base = card_base + strength
  2. if attacker is Weak:  base = floor(base * 0.75)
  3. if target is Vulnerable: base = floor(base * 1.5)
  4. damage dealt = max(0, base - target_block)
  5. target.block = max(0, target_block - base_before_hp)
  6. target.hp    -= max(0, base - target_block)

Block timing:
  - Player block is wiped at the START of the player's next turn.
  - Enemy block  is wiped at the START of that enemy's next turn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CombatState, EnemyState


class DebuffKind(Enum):
    VULNERABLE = auto()
    WEAK = auto()
    STRENGTH_DOWN = auto()            # permanent (Disarm)
    STRENGTH_DOWN_EOT = auto()        # deferred EOT (Flex, Steroid Potion)
    STRENGTH_DOWN_THIS_TURN = auto()  # temporary (Dark Shackles)
    DEXTERITY_DOWN = auto()           # immediate (future enemy debuffs)
    DEXTERITY_DOWN_EOT = auto()       # deferred EOT (Speed potion)
    SELF_VULNERABLE = auto()          # applied to player (Berserk)


def apply_debuff(
    state: "CombatState",
    target_powers: Powers,
    kind: DebuffKind,
    stacks: int,
    *,
    target_index: int | None = None,
) -> bool:
    """Apply a debuff, respecting Artifact. Returns True if the debuff landed."""
    if stacks <= 0:
        return False

    # Artifact check: any combatant with artifact stacks blocks the debuff
    if target_powers.artifact > 0:
        target_powers.artifact -= 1
        return False

    if kind == DebuffKind.VULNERABLE:
        target_powers.vulnerable += stacks
    elif kind == DebuffKind.WEAK:
        target_powers.weak += stacks
    elif kind == DebuffKind.STRENGTH_DOWN:
        target_powers.strength -= stacks
    elif kind == DebuffKind.STRENGTH_DOWN_EOT:
        target_powers.strength_loss_eot += stacks
    elif kind == DebuffKind.STRENGTH_DOWN_THIS_TURN:
        target_powers.strength_loss_this_turn += stacks
        target_powers.strength -= stacks
    elif kind == DebuffKind.DEXTERITY_DOWN:
        target_powers.dexterity -= stacks
    elif kind == DebuffKind.DEXTERITY_DOWN_EOT:
        target_powers.dexterity_loss_eot += stacks
    elif kind == DebuffKind.SELF_VULNERABLE:
        target_powers.vulnerable += stacks

    # Emit DEBUFF_APPLIED for any subscribed listeners (Sadistic Nature, etc.)
    if target_index is not None:
        from .events import Event, emit as _emit
        _emit(state, Event.DEBUFF_APPLIED, target_index, kind=kind, stacks=stacks)

    return True


@dataclass(slots=True)
class Powers:
    """Mutable bag of status/power stacks on a single combatant."""

    strength: int = 0
    vulnerable: int = 0          # turns remaining
    weak: int = 0                # turns remaining
    frail: int = 0               # turns remaining; reduces block gain to floor(x * 0.75)
    ritual: int = 0              # stacks; fires at end of enemy turn → +strength
    ritual_just_applied: bool = False  # skip strength gain on the turn ritual is acquired
    curl_up: int = 0             # enemy: on first HP damage, gain this much block (then consumed)
    angry: int = 0               # enemy: on any attack hit, gain this much strength
    spore_cloud: int = 0         # enemy: on death, apply this many Vulnerable stacks to player
    entangled: bool = False      # player: cannot play Skill or Power cards this turn
    dexterity: int = 0           # player: flat bonus to all block gains
    metallicize: int = 0         # player: gain this much block at end of each player turn
    strength_loss_eot: int = 0   # player: lose this much strength at end of turn (Steroid/Flex)
    dexterity_loss_eot: int = 0  # player: lose this much dexterity at end of turn (Speed)
    strength_loss_this_turn: int = 0  # enemy: lose this much strength until end of turn (Dark Shackles)
    asleep: bool = False         # enemy: sleeping (Lagavulin); does nothing until attacked
    enemy_metallicize: int = 0   # enemy: gain this much block at end of each enemy turn (Lagavulin sleeping)

    # Triggered power stacks (player only)
    dark_embrace: int = 0        # draw this many cards whenever any card is exhausted
    feel_no_pain: int = 0        # gain this much block whenever any card is exhausted
    juggernaut: int = 0          # deal this much damage to a random enemy whenever you gain block
    brutality: int = 0           # start of turn: lose 1 HP, draw 1
    demon_form: int = 0          # start of turn: gain this much strength
    berserk_energy: int = 0      # start of turn: gain this much energy
    corruption: bool = False     # skills cost 0 and are exhausted when played
    double_tap: int = 0          # next N attacks this turn are played twice
    rage_block: int = 0          # gain this much block per Attack played this turn
    artifact: int = 0            # block N debuffs (decremented per debuff blocked)
    no_card_block_turns: int = 0 # cannot gain block from cards for N turns
    panache_counter: int = 0     # cards played counter for Panache trigger
    panache_damage: int = 0      # damage dealt per Panache trigger
    magnetism: int = 0           # start of turn: add random colorless to hand
    sadistic_nature: int = 0     # deal damage whenever a debuff is applied to an enemy
    bomb_fuses: list[tuple[int, int]] = field(default_factory=list)  # (turns_left, damage)
    mayhem: int = 0              # start of turn: play top card of draw pile
    cards_played_this_turn: int = 0  # counter for Panache etc.
    combust: int = 0               # Combust: stacks (HP loss per turn = this value)
    combust_dmg: int = 0           # Combust: total damage dealt to all enemies per turn

    def tick_start_of_turn(self) -> None:
        """Decrement duration-based statuses."""
        if self.vulnerable > 0:
            self.vulnerable -= 1
        if self.weak > 0:
            self.weak -= 1
        if self.frail > 0:
            self.frail -= 1
        self.entangled = False

    def apply_ritual(self) -> None:
        """Fire end-of-round Ritual: gain strength equal to ritual stacks.

        The first time ritual is acquired (ritual_just_applied=True) the
        strength gain is skipped, matching sts_lightspeed's justApplied logic.
        """
        if self.ritual_just_applied:
            self.ritual_just_applied = False
        elif self.ritual > 0:
            self.strength += self.ritual


def calc_damage(
    base: int,
    attacker_powers: Powers,
    target_powers: Powers,
) -> int:
    """Return the raw damage value before block is applied."""
    dmg = base + attacker_powers.strength - attacker_powers.strength_loss_this_turn
    if attacker_powers.weak > 0:
        dmg = math.floor(dmg * 0.75)
    if target_powers.vulnerable > 0:
        dmg = math.floor(dmg * 1.5)
    return max(0, dmg)


def apply_damage(
    raw_dmg: int,
    target_block: int,
    target_hp: int,
) -> tuple[int, int]:
    """Apply raw damage to a target, returning (new_block, new_hp)."""
    blocked = min(raw_dmg, target_block)
    new_block = target_block - blocked
    hp_dmg = raw_dmg - blocked
    new_hp = target_hp - hp_dmg
    return new_block, new_hp


def gain_block(powers: Powers, amount: int, ignore_dexterity: bool = False) -> int:
    """Return actual block gained, with Dexterity bonus then Frail reduction.

    ignore_dexterity=True is used by potions that grant flat block bypassing Frail
    (Block Potion in StS grants exactly 12 regardless of Frail).
    """
    if ignore_dexterity:
        return amount
    total = amount + powers.dexterity
    if powers.frail > 0:
        return math.floor(total * 0.75)
    return total



def attack_enemy(state: "CombatState", enemy: "EnemyState", base_dmg: int, enemy_index: int | None = None) -> None:
    """Deal base_dmg to enemy, applying player strength/weak, enemy vulnerable.

    Also fires Angry (on any attack) and emits HP_LOSS / DEATH events via the
    event bus (Curl Up, Lagavulin wake, slime split, Spore Cloud).
    Mutates enemy and state in place.
    """
    from .events import Event, emit as _emit

    # Pen Nib: if active, double the damage
    if state.relic_state.get("pen_nib_active", 0):
        base_dmg *= 2
        state.relic_state["pen_nib_active"] = 0

    raw = calc_damage(base_dmg, state.player_powers, enemy.powers)

    # Angry fires on any attack hit, before applying damage
    if enemy.powers.angry > 0:
        enemy.powers.strength += enemy.powers.angry

    hp_before = enemy.hp
    new_block, new_hp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block = new_block
    enemy.hp = new_hp

    # Emit HP_LOSS for enemy reactions (Curl Up, Lagavulin wake, slime split)
    if enemy.hp < hp_before and enemy_index is not None:
        _emit(state, Event.HP_LOSS, enemy_index, hp_before=hp_before)

    # Emit DEATH for death-triggered effects (Spore Cloud)
    if hp_before > 0 and enemy.hp <= 0 and enemy_index is not None:
        _emit(state, Event.DEATH, enemy_index, hp_before=hp_before)
