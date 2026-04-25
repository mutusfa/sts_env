"""Card definitions for the Ironclad starter set + selected commons.

Each card has:
  - A CardSpec (static metadata: cost, type, target requirement).
  - A handler function: play(ctx, hand_index, target_index) -> None.
    The handler mutates CombatState directly.

Cards registered:
  Starter:  Strike x5, Defend x4, Bash x1
  Curse:    AscendersBane (unplayable)
  Status:   Slimed, Dazed
  Common:   Anger, Armaments, Cleave, Clothesline, Flex, Havoc, Headbutt,
            IronWave, PommelStrike, ShrugItOff, SwordBoomerang, ThunderClap,
            TrueStrike, TwinStrike, WarCry, WildStrike
  Uncommon: Bloodletting, BurningPact, Carnage, Disarm, Dropkick, DualWield,
            Entrench, FeelNoPain, FlameBarrier, GhostArmor, Inflame, Metallicize,
            PowerThrough, Pummel, Rage, Rampage, RecklessCharge, SecondWind,
            SeeingRed, SearingBlow, Sentinel, SeverSoul, ShockWave, SpotWeakness,
            Uppercut, Whirlwind, BattleTrance
  Rare:     Bludgeon, Berserk, Brutality, Corruption, DarkEmbrace, DemonForm,
            DoubleTap, Feed, Impervious, Juggernaut, LimitBreak, Offering
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

from .card import Card

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
    exhausts: bool = False


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
    card = state.piles.hand[hand_index]
    spec = _SPECS[card.card_id]

    effective_cost = card.cost_override if card.cost_override is not None else spec.cost
    if effective_cost < 0:
        raise ValueError(f"Card {card.card_id!r} is unplayable.")
    if effective_cost > state.energy:
        raise ValueError(
            f"Not enough energy to play {card.card_id!r}: need {effective_cost}, have {state.energy}."
        )
    if spec.target == TargetType.SINGLE_ENEMY and not (
        0 <= target_index < len(state.enemies)
    ):
        raise ValueError(f"Invalid target_index {target_index}.")

    state.energy -= effective_cost
    played_card = state.piles.play_card(hand_index)
    _HANDLERS[card.card_id](state, hand_index, target_index)
    if spec.exhausts:
        state.piles.move_to_exhaust(played_card)
    else:
        state.piles.move_to_discard(played_card)


# ---------------------------------------------------------------------------
# Individual card handlers
# ---------------------------------------------------------------------------

# --- Starter cards ---

def _strike(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 6)


_register(
    CardSpec("Strike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _strike,
)


def _defend(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    state.player_block += gain_block(state.player_powers, 5)


_register(
    CardSpec("Defend", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _defend,
)


def _bash(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 8)
    state.enemies[ti].powers.vulnerable += 2


_register(
    CardSpec("Bash", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _bash,
)


# --- Curse ---

def _ascenders_bane(state: "CombatState", _hi: int, _ti: int) -> None:
    raise ValueError("AscendersBane is unplayable.")


_register(
    CardSpec("AscendersBane", cost=-1, card_type=CardType.CURSE, target=TargetType.NONE),
    _ascenders_bane,
)


# --- Status cards ---

# Slimed: Cost 1, does nothing, exhausts when played.
def _slimed(state: "CombatState", _hi: int, _ti: int) -> None:
    pass  # no effect; exhausts automatically via spec.exhausts = True


_register(
    CardSpec("Slimed", cost=1, card_type=CardType.STATUS, target=TargetType.NONE, exhausts=True),
    _slimed,
)


# Dazed: Unplayable status card. Exhausts at end of turn (handled by engine).
# Placed in discard by Sentries' Bolt attack.
def _dazed(state: "CombatState", _hi: int, _ti: int) -> None:
    raise ValueError("Dazed is unplayable.")


_register(
    CardSpec("Dazed", cost=-1, card_type=CardType.STATUS, target=TargetType.NONE, exhausts=True),
    _dazed,
)


# ---------------------------------------------------------------------------
# Common Attacks
# ---------------------------------------------------------------------------

def _pommel_strike(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 9)
    state.piles.draw_cards(1, state.rng)


_register(
    CardSpec("PommelStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _pommel_strike,
)


def _shrug_it_off(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    state.player_block += gain_block(state.player_powers, 8)
    state.piles.draw_cards(1, state.rng)


_register(
    CardSpec("ShrugItOff", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _shrug_it_off,
)


def _iron_wave(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy, gain_block
    attack_enemy(state, state.enemies[ti], 5)
    state.player_block += gain_block(state.player_powers, 5)


_register(
    CardSpec("IronWave", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _iron_wave,
)


def _cleave(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import attack_enemy

    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            attack_enemy(state, enemy, 8)


_register(
    CardSpec("Cleave", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES),
    _cleave,
)


def _anger(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 6)
    state.piles.add_to_discard(Card("Anger"))


_register(
    CardSpec("Anger", cost=0, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _anger,
)


def _clothesline(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 12)
    state.enemies[ti].powers.vulnerable += 2


_register(
    CardSpec("Clothesline", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _clothesline,
)


def _headbutt(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 9)


_register(
    CardSpec("Headbutt", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _headbutt,
)


def _thunder_clap(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    # Deals 7 damage to ALL enemies, applies 1 Vulnerable to ALL
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            attack_enemy(state, enemy, 7)
            enemy.powers.vulnerable += 1


_register(
    CardSpec("ThunderClap", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES),
    _thunder_clap,
)


def _twin_strike(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 5)
    attack_enemy(state, state.enemies[ti], 5)


_register(
    CardSpec("TwinStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _twin_strike,
)


def _wild_strike(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 12)
    state.piles.add_to_discard(Card("WildStrike"))  # placeholder: adds a copy to draw pile top in real StS
    # Simplified: just add a status-like card to discard instead of draw pile


_register(
    CardSpec("WildStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _wild_strike,
)


def _sword_boomerang(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import attack_enemy
    # Deal 3 damage to a random enemy 3 times
    for _ in range(3):
        alive = [e for e in state.enemies if e.hp > 0 and e.name != "Empty"]
        if alive:
            target = alive[state.rng.randint(0, len(alive) - 1)]
            attack_enemy(state, target, 3)


_register(
    CardSpec("SwordBoomerang", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES),
    _sword_boomerang,
)


def _true_strike(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 12)


_register(
    CardSpec("TrueStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _true_strike,
)


# ---------------------------------------------------------------------------
# Common Skills
# ---------------------------------------------------------------------------

def _armaments(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    state.player_block += gain_block(state.player_powers, 5)
    # Simplified: In real StS, upgrades a card in hand. We just grant block.


_register(
    CardSpec("Armaments", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _armaments,
)


def _flex(state: "CombatState", _hi: int, _ti: int) -> None:
    state.player_powers.strength += 2
    state.player_powers.strength_loss_eot += 2


_register(
    CardSpec("Flex", cost=0, card_type=CardType.SKILL, target=TargetType.NONE),
    _flex,
)


def _havoc(state: "CombatState", _hi: int, _ti: int) -> None:
    # Play the top card of your draw pile and Exhaust it
    if state.piles.draw:
        top_card = state.piles.draw.pop(0)
        spec = _SPECS.get(top_card.card_id)
        if spec is not None and spec.cost >= 0:
            # Pay 0 for the played card (Havoc covers the cost)
            # Simplified: just exhaust it
            state.piles.move_to_exhaust(top_card)
        else:
            state.piles.move_to_exhaust(top_card)
    # If draw pile is empty, nothing happens


_register(
    CardSpec("Havoc", cost=1, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True),
    _havoc,
)


def _war_cry(state: "CombatState", _hi: int, _ti: int) -> None:
    state.piles.draw_cards(1, state.rng)
    # Simplified: In real StS, puts a card from draw pile into hand and Exhausts.
    # We just draw 1 card.


_register(
    CardSpec("WarCry", cost=0, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True),
    _war_cry,
)


# ---------------------------------------------------------------------------
# Uncommon Attacks
# ---------------------------------------------------------------------------

def _carnage(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 20)


_register(
    CardSpec("Carnage", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY, exhausts=True),
    _carnage,
)


def _dropkick(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    enemy = state.enemies[ti]
    attack_enemy(state, enemy, 5)
    if enemy.powers.vulnerable > 0:
        state.energy += 1
        state.piles.draw_cards(1, state.rng)


_register(
    CardSpec("Dropkick", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _dropkick,
)


def _pummel(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    for _ in range(4):
        attack_enemy(state, state.enemies[ti], 2)


_register(
    CardSpec("Pummel", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY, exhausts=True),
    _pummel,
)


def _rampage(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 18)


_register(
    CardSpec("Rampage", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _rampage,
)


def _reckless_charge(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 7)
    # Adds Dazed to draw pile top
    state.piles.place_on_top(Card("Dazed"))


_register(
    CardSpec("RecklessCharge", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _reckless_charge,
)


def _searing_blow(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 12)


_register(
    CardSpec("SearingBlow", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _searing_blow,
)


def _sever_soul(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 16)


_register(
    CardSpec("SeverSoul", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY, exhausts=True),
    _sever_soul,
)


def _uppercut(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 13)
    state.enemies[ti].powers.vulnerable += 1
    state.enemies[ti].powers.weak += 1


_register(
    CardSpec("Uppercut", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _uppercut,
)


def _whirlwind(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import attack_enemy
    # Deal 5 damage to ALL enemies X times (X = energy spent)
    # Simplified: fixed at 1 hit for 5 damage to all enemies
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            attack_enemy(state, enemy, 5)


_register(
    CardSpec("Whirlwind", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES),
    _whirlwind,
)


# ---------------------------------------------------------------------------
# Uncommon Skills
# ---------------------------------------------------------------------------

def _bloodletting(state: "CombatState", _hi: int, _ti: int) -> None:
    # Lose 3 HP, gain 2 energy
    state.player_hp = max(0, state.player_hp - 3)
    state.energy += 2


_register(
    CardSpec("Bloodletting", cost=0, card_type=CardType.SKILL, target=TargetType.NONE),
    _bloodletting,
)


def _burning_pact(state: "CombatState", _hi: int, _ti: int) -> None:
    # Exhaust a card, draw 2 cards. Simplified: just draw 2.
    state.piles.draw_cards(2, state.rng)


_register(
    CardSpec("BurningPact", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _burning_pact,
)


def _disarm(state: "CombatState", _hi: int, ti: int) -> None:
    state.enemies[ti].powers.strength -= 2


_register(
    CardSpec("Disarm", cost=1, card_type=CardType.SKILL, target=TargetType.SINGLE_ENEMY, exhausts=True),
    _disarm,
)


def _dual_wield(state: "CombatState", _hi: int, _ti: int) -> None:
    # Create a copy of an Attack or Power card in hand. Simplified: no-op.
    pass


_register(
    CardSpec("DualWield", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _dual_wield,
)


def _entrench(state: "CombatState", _hi: int, _ti: int) -> None:
    state.player_block *= 2


_register(
    CardSpec("Entrench", cost=2, card_type=CardType.SKILL, target=TargetType.NONE),
    _entrench,
)


def _flame_barrier(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    state.player_block += gain_block(state.player_powers, 12)
    # Also has Thorns 4 — simplified: just block


_register(
    CardSpec("FlameBarrier", cost=2, card_type=CardType.SKILL, target=TargetType.NONE),
    _flame_barrier,
)


def _ghost_armor(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    state.player_block += gain_block(state.player_powers, 10)


_register(
    CardSpec("GhostArmor", cost=1, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True),
    _ghost_armor,
)


def _power_through(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    # Add 2 Wounds to hand, gain 15 block. Simplified: just gain block.
    state.player_block += gain_block(state.player_powers, 15)


_register(
    CardSpec("PowerThrough", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _power_through,
)


def _rage(state: "CombatState", _hi: int, _ti: int) -> None:
    # Gain 3 block whenever you play an Attack this turn. Simplified: just gain 0 block direct.
    # We don't track the "on attack played" trigger, so this is simplified.
    pass


_register(
    CardSpec("Rage", cost=0, card_type=CardType.SKILL, target=TargetType.NONE),
    _rage,
)


def _second_wind(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    # Exhaust all non-Attack cards in hand, gain 5 block per card exhausted. Simplified.
    state.player_block += gain_block(state.player_powers, 5)


_register(
    CardSpec("SecondWind", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _second_wind,
)


def _seeing_red(state: "CombatState", _hi: int, _ti: int) -> None:
    state.energy += 2


_register(
    CardSpec("SeeingRed", cost=1, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True),
    _seeing_red,
)


def _sentinel(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    state.player_block += gain_block(state.player_powers, 12)


_register(
    CardSpec("Sentinel", cost=1, card_type=CardType.SKILL, target=TargetType.NONE),
    _sentinel,
)


def _shock_wave(state: "CombatState", _hi: int, _ti: int) -> None:
    # Apply 3 Weak and 3 Vulnerable to ALL enemies
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            enemy.powers.weak += 3
            enemy.powers.vulnerable += 3


_register(
    CardSpec("ShockWave", cost=2, card_type=CardType.SKILL, target=TargetType.ALL_ENEMIES, exhausts=True),
    _shock_wave,
)


def _spot_weakness(state: "CombatState", _hi: int, ti: int) -> None:
    # If enemy intends to attack, gain 3 Strength
    state.player_powers.strength += 3


_register(
    CardSpec("SpotWeakness", cost=1, card_type=CardType.SKILL, target=TargetType.SINGLE_ENEMY),
    _spot_weakness,
)


def _battle_trance(state: "CombatState", _hi: int, _ti: int) -> None:
    state.piles.draw_cards(3, state.rng)


_register(
    CardSpec("BattleTrance", cost=0, card_type=CardType.SKILL, target=TargetType.NONE),
    _battle_trance,
)


# ---------------------------------------------------------------------------
# Uncommon Powers
# ---------------------------------------------------------------------------

def _inflame(state: "CombatState", _hi: int, _ti: int) -> None:
    state.player_powers.strength += 2


_register(
    CardSpec("Inflame", cost=1, card_type=CardType.POWER, target=TargetType.NONE),
    _inflame,
)


def _metallicize(state: "CombatState", _hi: int, _ti: int) -> None:
    state.player_powers.metallicize += 3


_register(
    CardSpec("Metallicize", cost=1, card_type=CardType.POWER, target=TargetType.NONE),
    _metallicize,
)


def _feel_no_pain(state: "CombatState", _hi: int, _ti: int) -> None:
    # Whenever a card is Exhausted, gain 3 block. Simplified: no trigger system.
    pass


_register(
    CardSpec("FeelNoPain", cost=1, card_type=CardType.POWER, target=TargetType.NONE),
    _feel_no_pain,
)


# ---------------------------------------------------------------------------
# Rare Attacks
# ---------------------------------------------------------------------------

def _bludgeon(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    attack_enemy(state, state.enemies[ti], 32)


_register(
    CardSpec("Bludgeon", cost=3, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _bludgeon,
)


def _feed(state: "CombatState", _hi: int, ti: int) -> None:
    from .powers import attack_enemy
    enemy = state.enemies[ti]
    attack_enemy(state, enemy, 10)
    # If fatal, gain 3 max HP. Checked in engine post-combat; simplified here.
    if enemy.hp <= 0:
        state.player_max_hp += 3
        state.player_hp = min(state.player_hp + 3, state.player_max_hp)


_register(
    CardSpec("Feed", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY),
    _feed,
)


# ---------------------------------------------------------------------------
# Rare Skills
# ---------------------------------------------------------------------------

def _impervious(state: "CombatState", _hi: int, _ti: int) -> None:
    from .powers import gain_block
    state.player_block += gain_block(state.player_powers, 30)


_register(
    CardSpec("Impervious", cost=2, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True),
    _impervious,
)


def _offering(state: "CombatState", _hi: int, _ti: int) -> None:
    # Lose 6 HP, gain 2 energy, draw 3 cards
    state.player_hp = max(0, state.player_hp - 6)
    state.energy += 2
    state.piles.draw_cards(3, state.rng)


_register(
    CardSpec("Offering", cost=0, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True),
    _offering,
)


def _berserk(state: "CombatState", _hi: int, _ti: int) -> None:
    state.energy += 2
    state.player_powers.vulnerable += 1


_register(
    CardSpec("Berserk", cost=0, card_type=CardType.SKILL, target=TargetType.NONE),
    _berserk,
)


# ---------------------------------------------------------------------------
# Rare Powers
# ---------------------------------------------------------------------------

def _demon_form(state: "CombatState", _hi: int, _ti: int) -> None:
    # At the start of each turn, gain 2 Strength. Simplified: gain 2 strength now.
    state.player_powers.strength += 2
    # In a full implementation, this would set a "demon_form" power that triggers at turn start.


_register(
    CardSpec("DemonForm", cost=3, card_type=CardType.POWER, target=TargetType.NONE),
    _demon_form,
)


def _double_tap(state: "CombatState", _hi: int, _ti: int) -> None:
    # Next attack played twice. Simplified: no trigger system.
    pass


_register(
    CardSpec("DoubleTap", cost=1, card_type=CardType.POWER, target=TargetType.NONE),
    _double_tap,
)


def _brutality(state: "CombatState", _hi: int, _ti: int) -> None:
    # At start of turn, lose 1 HP and draw 1 card. Simplified.
    pass


_register(
    CardSpec("Brutality", cost=0, card_type=CardType.POWER, target=TargetType.NONE),
    _brutality,
)


def _corruption(state: "CombatState", _hi: int, _ti: int) -> None:
    # Skills cost 0 and exhaust. Simplified: no trigger system.
    pass


_register(
    CardSpec("Corruption", cost=3, card_type=CardType.POWER, target=TargetType.NONE),
    _corruption,
)


def _dark_embrace(state: "CombatState", _hi: int, _ti: int) -> None:
    # Whenever a card is Exhausted, draw 1 card. Simplified: no trigger system.
    pass


_register(
    CardSpec("DarkEmbrace", cost=2, card_type=CardType.POWER, target=TargetType.NONE),
    _dark_embrace,
)


def _juggernaut(state: "CombatState", _hi: int, _ti: int) -> None:
    # Whenever you gain block, deal 5 damage to a random enemy. Simplified.
    pass


_register(
    CardSpec("Juggernaut", cost=2, card_type=CardType.POWER, target=TargetType.NONE),
    _juggernaut,
)


def _limit_break(state: "CombatState", _hi: int, _ti: int) -> None:
    # Double your Strength
    state.player_powers.strength *= 2


_register(
    CardSpec("LimitBreak", cost=1, card_type=CardType.POWER, target=TargetType.NONE, exhausts=True),
    _limit_break,
)
