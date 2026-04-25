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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CombatState, EnemyState


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
    asleep: bool = False         # enemy: sleeping (Lagavulin); does nothing until attacked
    enemy_metallicize: int = 0   # enemy: gain this much block at end of each enemy turn (Lagavulin sleeping)

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
    dmg = base + attacker_powers.strength
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


# Enemy names that split at <= 50% HP
_SPLIT_NAMES = frozenset({"AcidSlimeL", "SpikeSlimeL", "SlimeBoss"})


def attack_enemy(state: "CombatState", enemy: "EnemyState", base_dmg: int) -> None:
    """Deal base_dmg to enemy, applying player strength/weak, enemy vulnerable.

    Also fires Angry (on any attack) and Curl Up (on first HP damage).
    Sets pending_split on large slimes when HP crosses the 50% threshold.
    Wakes up sleeping enemies (Lagavulin).
    Mutates enemy and state in place.
    """
    raw = calc_damage(base_dmg, state.player_powers, enemy.powers)

    # Angry fires on any attack hit, before applying damage
    if enemy.powers.angry > 0:
        enemy.powers.strength += enemy.powers.angry

    hp_before = enemy.hp
    new_block, new_hp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block = new_block
    enemy.hp = new_hp

    # Wake up sleeping enemies on HP damage
    if enemy.powers.asleep and enemy.hp < hp_before:
        enemy.powers.asleep = False
        enemy.powers.enemy_metallicize = 0

    # Curl Up fires the first time the enemy takes HP damage
    if enemy.powers.curl_up > 0 and enemy.hp < hp_before:
        enemy.block += enemy.powers.curl_up
        enemy.powers.curl_up = 0

    # SporeCloud fires when the enemy is killed for the first time
    if hp_before > 0 and enemy.hp <= 0 and enemy.powers.spore_cloud > 0:
        state.player_powers.vulnerable += enemy.powers.spore_cloud
        enemy.powers.spore_cloud = 0

    # Large slimes split when HP first crosses <= 50% threshold
    if (
        enemy.name in _SPLIT_NAMES
        and not enemy.pending_split
        and enemy.hp > 0
        and enemy.hp <= enemy.max_hp // 2
        and hp_before > enemy.max_hp // 2
    ):
        enemy.pending_split = True
