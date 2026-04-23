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


@dataclass(slots=True)
class Powers:
    """Mutable bag of status/power stacks on a single combatant."""

    strength: int = 0
    vulnerable: int = 0          # turns remaining
    weak: int = 0                # turns remaining
    ritual: int = 0              # stacks; fires at end of enemy turn → +strength
    ritual_just_applied: bool = False  # skip strength gain on the turn ritual is acquired

    def tick_start_of_turn(self) -> None:
        """Decrement duration-based statuses."""
        if self.vulnerable > 0:
            self.vulnerable -= 1
        if self.weak > 0:
            self.weak -= 1

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
