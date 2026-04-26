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
from .powers import attack_enemy, gain_block

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
CardHandler = Callable[["CombatState", int, int, int], None]

_SPECS: dict[str, CardSpec] = {}
_HANDLERS: dict[str, CardHandler] = {}

# Upgrade bonuses: card_id → dict of bonuses applied when Card.upgraded == 1
UPGRADE_BONUSES: dict[str, dict[str, int]] = {
    "Strike": {"damage": 3}, "Defend": {"block": 3}, "Bash": {"damage": 2, "vulnerable": 1},
    "Anger": {"damage": 2}, "Cleave": {"damage": 3}, "Clothesline": {"damage": 2, "vulnerable": 1},
    "Headbutt": {"damage": 3}, "IronWave": {"damage": 2, "block": 2},
    "PommelStrike": {"damage": 1, "draw": 1}, "ThunderClap": {"damage": 2},
    "TwinStrike": {"damage": 2}, "TrueStrike": {"damage": 2}, "WildStrike": {"damage": 5},
    "SwordBoomerang": {"damage": 1}, "Armaments": {"block": 3}, "Flex": {"strength": 2},
    "WarCry": {"draw": 1}, "Carnage": {"damage": 8}, "Dropkick": {"damage": 3},
    "Pummel": {"hits": 1}, "Rampage": {"damage": 10}, "RecklessCharge": {"damage": 4},
    "SearingBlow": {"damage": 3}, "SeverSoul": {"damage": 6},
    "Uppercut": {"damage": 3, "vulnerable": 1, "weak": 1}, "Whirlwind": {"damage": 3},
    "Bloodletting": {"energy": 1}, "BurningPact": {"draw": 1}, "Disarm": {"strength": 1},
    "FlameBarrier": {"block": 4}, "GhostArmor": {"block": 3}, "PowerThrough": {"block": 5},
    "SecondWind": {"block": 3}, "SeeingRed": {"energy": 1}, "Sentinel": {"block": 3},
    "ShockWave": {"vulnerable": 1, "weak": 1}, "SpotWeakness": {"strength": 1},
    "BattleTrance": {"draw": 1}, "ShrugItOff": {"block": 3, "draw": 1},
    "Inflame": {"strength": 1}, "Metallicize": {"block": 1},
    "Bludgeon": {"damage": 10}, "Feed": {"damage": 5, "max_hp": 1},
    "Impervious": {"block": 10}, "Offering": {"hp_loss": 4, "energy": 1, "draw": 2},
    "Berserk": {"energy": 1}, "Entrench": {"cost": -1}, "Corruption": {"cost": -1},
    "DemonForm": {"strength": 1},
}


def _ub(card_id: str, upgraded: int, key: str) -> int:
    """Return upgrade bonus for a card and key, or 0 if not upgraded."""
    if upgraded:
        return UPGRADE_BONUSES.get(card_id, {}).get(key, 0)
    return 0



def card(
    card_id: str,
    *,
    cost: int,
    card_type: CardType,
    target: TargetType,
    exhausts: bool = False,
) -> Callable[[CardHandler], CardHandler]:
    def decorator(fn: CardHandler) -> CardHandler:
        _SPECS[card_id] = CardSpec(card_id, cost, card_type, target, exhausts)
        _HANDLERS[card_id] = fn
        return fn
    return decorator


def get_spec(card_id: str) -> CardSpec:
    return _SPECS[card_id]


def play_card(state: "CombatState", hand_index: int, target_index: int) -> None:
    """Validate and execute a card play, updating state in place."""
    card = state.piles.hand[hand_index]
    spec = _SPECS[card.card_id]

    effective_cost = card.cost_override if card.cost_override is not None else spec.cost
    if card.upgraded:
        effective_cost += UPGRADE_BONUSES.get(card.card_id, {}).get("cost", 0)
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
    _HANDLERS[card.card_id](state, hand_index, target_index, card.upgraded)
    if spec.exhausts:
        state.piles.move_to_exhaust(played_card)
    else:
        state.piles.move_to_discard(played_card)


# ---------------------------------------------------------------------------
# Individual card handlers
# ---------------------------------------------------------------------------

# --- Starter cards ---

@card("Strike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _strike(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 6 + _ub("Strike", upgraded, "damage"))


@card("Defend", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _defend(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block += gain_block(state.player_powers, 5 + _ub("Defend", upgraded, "block"))


@card("Bash", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _bash(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 8 + _ub("Bash", upgraded, "damage"))
    state.enemies[ti].powers.vulnerable += 2 + _ub("Bash", upgraded, "vulnerable")


# --- Curse ---

@card("AscendersBane", cost=-1, card_type=CardType.CURSE, target=TargetType.NONE)
def _ascenders_bane(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    raise ValueError("AscendersBane is unplayable.")


# --- Status cards ---

# Slimed: Cost 1, does nothing, exhausts when played.
@card("Slimed", cost=1, card_type=CardType.STATUS, target=TargetType.NONE, exhausts=True)
def _slimed(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    pass  # no effect; exhausts automatically via spec.exhausts = True


# Dazed: Unplayable status card. Exhausts at end of turn (handled by engine).
# Placed in discard by Sentries' Bolt attack.
@card("Dazed", cost=-1, card_type=CardType.STATUS, target=TargetType.NONE, exhausts=True)
def _dazed(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    raise ValueError("Dazed is unplayable.")


# ---------------------------------------------------------------------------
# Common Attacks
# ---------------------------------------------------------------------------

@card("PommelStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _pommel_strike(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 9 + _ub("PommelStrike", upgraded, "damage"))
    state.piles.draw_cards(1 + _ub("PommelStrike", upgraded, "draw"), state.rng)


@card("ShrugItOff", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _shrug_it_off(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block += gain_block(state.player_powers, 8 + _ub("ShrugItOff", upgraded, "block"))
    state.piles.draw_cards(1 + _ub("ShrugItOff", upgraded, "draw"), state.rng)


@card("IronWave", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _iron_wave(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 5 + _ub("IronWave", upgraded, "damage"))
    state.player_block += gain_block(state.player_powers, 5 + _ub("IronWave", upgraded, "block"))


@card("Cleave", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES)
def _cleave(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            attack_enemy(state, enemy, 8 + _ub("Cleave", upgraded, "damage"))


@card("Anger", cost=0, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _anger(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 6 + _ub("Anger", upgraded, "damage"))
    state.piles.add_to_discard(Card("Anger"))


@card("Clothesline", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _clothesline(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 12 + _ub("Clothesline", upgraded, "damage"))
    state.enemies[ti].powers.vulnerable += 2 + _ub("Clothesline", upgraded, "vulnerable")


@card("Headbutt", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _headbutt(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 9 + _ub("Headbutt", upgraded, "damage"))


@card("ThunderClap", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES)
def _thunder_clap(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    # Deals 7 damage to ALL enemies, applies 1 Vulnerable to ALL
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            attack_enemy(state, enemy, 7 + _ub("ThunderClap", upgraded, "damage"))
            enemy.powers.vulnerable += 1


@card("TwinStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _twin_strike(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 5 + _ub("TwinStrike", upgraded, "damage"))
    attack_enemy(state, state.enemies[ti], 5 + _ub("TwinStrike", upgraded, "damage"))


@card("WildStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _wild_strike(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 12 + _ub("WildStrike", upgraded, "damage"))
    state.piles.add_to_discard(Card("WildStrike"))  # placeholder: adds a copy to draw pile top in real StS
    # Simplified: just add a status-like card to discard instead of draw pile


@card("SwordBoomerang", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES)
def _sword_boomerang(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Deal 3 damage to a random enemy 3 times
    for _ in range(3):
        alive = [e for e in state.enemies if e.hp > 0 and e.name != "Empty"]
        if alive:
            target = alive[state.rng.randint(0, len(alive) - 1)]
            attack_enemy(state, target, 3 + _ub("SwordBoomerang", upgraded, "damage"))


@card("TrueStrike", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _true_strike(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 12 + _ub("TrueStrike", upgraded, "damage"))


# ---------------------------------------------------------------------------
# Common Skills
# ---------------------------------------------------------------------------

@card("Armaments", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _armaments(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block += gain_block(state.player_powers, 5 + _ub("Armaments", upgraded, "block"))
    # Simplified: In real StS, upgrades a card in hand. We just grant block.


@card("Flex", cost=0, card_type=CardType.SKILL, target=TargetType.NONE)
def _flex(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_powers.strength += 2 + _ub("Flex", upgraded, "strength")
    state.player_powers.strength_loss_eot += 2 + _ub("Flex", upgraded, "strength")


@card("Havoc", cost=1, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True)
def _havoc(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
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


@card("WarCry", cost=0, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True)
def _war_cry(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.piles.draw_cards(1 + _ub("WarCry", upgraded, "draw"), state.rng)
    # Simplified: In real StS, puts a card from draw pile into hand and Exhausts.
    # We just draw 1 card.


# ---------------------------------------------------------------------------
# Uncommon Attacks
# ---------------------------------------------------------------------------

@card("Carnage", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY, exhausts=True)
def _carnage(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 20 + _ub("Carnage", upgraded, "damage"))


@card("Dropkick", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _dropkick(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    enemy = state.enemies[ti]
    attack_enemy(state, enemy, 5 + _ub("Dropkick", upgraded, "damage"))
    if enemy.powers.vulnerable > 0:
        state.energy += 1
        state.piles.draw_cards(1, state.rng)


@card("Pummel", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY, exhausts=True)
def _pummel(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    for _ in range(4):
        attack_enemy(state, state.enemies[ti], 2 + _ub("Pummel", upgraded, "damage"))


@card("Rampage", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _rampage(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 18 + _ub("Rampage", upgraded, "damage"))


@card("RecklessCharge", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _reckless_charge(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 7 + _ub("RecklessCharge", upgraded, "damage"))
    # Adds Dazed to draw pile top
    state.piles.place_on_top(Card("Dazed"))


@card("SearingBlow", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _searing_blow(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 12 + _ub("SearingBlow", upgraded, "damage"))


@card("SeverSoul", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY, exhausts=True)
def _sever_soul(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 16 + _ub("SeverSoul", upgraded, "damage"))


@card("Uppercut", cost=2, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _uppercut(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 13 + _ub("Uppercut", upgraded, "damage"))
    state.enemies[ti].powers.vulnerable += 1 + _ub("Uppercut", upgraded, "vulnerable")
    state.enemies[ti].powers.weak += 1 + _ub("Uppercut", upgraded, "weak")


@card("Whirlwind", cost=1, card_type=CardType.ATTACK, target=TargetType.ALL_ENEMIES)
def _whirlwind(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Deal 5 damage to ALL enemies X times (X = energy spent)
    # Simplified: fixed at 1 hit for 5 damage to all enemies
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            attack_enemy(state, enemy, 5 + _ub("Whirlwind", upgraded, "damage"))


# ---------------------------------------------------------------------------
# Uncommon Skills
# ---------------------------------------------------------------------------

@card("Bloodletting", cost=0, card_type=CardType.SKILL, target=TargetType.NONE)
def _bloodletting(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Lose 3 HP, gain 2 energy
    state.player_hp = max(0, state.player_hp - 3)
    state.energy += 2 + _ub("Bloodletting", upgraded, "energy")


@card("BurningPact", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _burning_pact(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Exhaust a card, draw 2 cards. Simplified: just draw 2.
    state.piles.draw_cards(2 + _ub("BurningPact", upgraded, "draw"), state.rng)


@card("Disarm", cost=1, card_type=CardType.SKILL, target=TargetType.SINGLE_ENEMY, exhausts=True)
def _disarm(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    state.enemies[ti].powers.strength -= 2 + _ub("Disarm", upgraded, "strength")


@card("DualWield", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _dual_wield(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Create a copy of an Attack or Power card in hand. Simplified: no-op.
    pass


@card("Entrench", cost=2, card_type=CardType.SKILL, target=TargetType.NONE)
def _entrench(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block *= 2


@card("FlameBarrier", cost=2, card_type=CardType.SKILL, target=TargetType.NONE)
def _flame_barrier(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block += gain_block(state.player_powers, 12 + _ub("FlameBarrier", upgraded, "block"))
    # Also has Thorns 4 — simplified: just block


@card("GhostArmor", cost=1, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True)
def _ghost_armor(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block += gain_block(state.player_powers, 10 + _ub("GhostArmor", upgraded, "block"))


@card("PowerThrough", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _power_through(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Add 2 Wounds to hand, gain 15 block. Simplified: just gain block.
    state.player_block += gain_block(state.player_powers, 15 + _ub("PowerThrough", upgraded, "block"))


@card("Rage", cost=0, card_type=CardType.SKILL, target=TargetType.NONE)
def _rage(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Gain 3 block whenever you play an Attack this turn. Simplified: just gain 0 block direct.
    # We don't track the "on attack played" trigger, so this is simplified.
    pass


@card("SecondWind", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _second_wind(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Exhaust all non-Attack cards in hand, gain 5 block per card exhausted. Simplified.
    state.player_block += gain_block(state.player_powers, 5 + _ub("SecondWind", upgraded, "block"))


@card("SeeingRed", cost=1, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True)
def _seeing_red(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.energy += 2


@card("Sentinel", cost=1, card_type=CardType.SKILL, target=TargetType.NONE)
def _sentinel(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block += gain_block(state.player_powers, 12 + _ub("Sentinel", upgraded, "block"))


@card("ShockWave", cost=2, card_type=CardType.SKILL, target=TargetType.ALL_ENEMIES, exhausts=True)
def _shock_wave(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Apply 3 Weak and 3 Vulnerable to ALL enemies
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            enemy.powers.weak += 3 + _ub("ShockWave", upgraded, "weak")
            enemy.powers.vulnerable += 3 + _ub("ShockWave", upgraded, "vulnerable")


@card("SpotWeakness", cost=1, card_type=CardType.SKILL, target=TargetType.SINGLE_ENEMY)
def _spot_weakness(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    # If enemy intends to attack, gain 3 Strength
    state.player_powers.strength += 3 + _ub("SpotWeakness", upgraded, "strength")


@card("BattleTrance", cost=0, card_type=CardType.SKILL, target=TargetType.NONE)
def _battle_trance(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.piles.draw_cards(3 + _ub("BattleTrance", upgraded, "draw"), state.rng)


# ---------------------------------------------------------------------------
# Uncommon Powers
# ---------------------------------------------------------------------------

@card("Inflame", cost=1, card_type=CardType.POWER, target=TargetType.NONE)
def _inflame(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_powers.strength += 2 + _ub("Inflame", upgraded, "strength")


@card("Metallicize", cost=1, card_type=CardType.POWER, target=TargetType.NONE)
def _metallicize(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_powers.metallicize += 3 + _ub("Metallicize", upgraded, "block")


@card("FeelNoPain", cost=1, card_type=CardType.POWER, target=TargetType.NONE)
def _feel_no_pain(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Whenever a card is Exhausted, gain 3 block. Simplified: no trigger system.
    pass


# ---------------------------------------------------------------------------
# Rare Attacks
# ---------------------------------------------------------------------------

@card("Bludgeon", cost=3, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _bludgeon(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    attack_enemy(state, state.enemies[ti], 32 + _ub("Bludgeon", upgraded, "damage"))


@card("Feed", cost=1, card_type=CardType.ATTACK, target=TargetType.SINGLE_ENEMY)
def _feed(state: "CombatState", _hi: int, ti: int, upgraded: int = 0) -> None:
    enemy = state.enemies[ti]
    attack_enemy(state, enemy, 10 + _ub("Feed", upgraded, "damage"))
    # If fatal, gain 3 max HP. Checked in engine post-combat; simplified here.
    if enemy.hp <= 0:
        state.player_max_hp += 3
        state.player_hp = min(state.player_hp + 3, state.player_max_hp)


# ---------------------------------------------------------------------------
# Rare Skills
# ---------------------------------------------------------------------------

@card("Impervious", cost=2, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True)
def _impervious(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.player_block += gain_block(state.player_powers, 30 + _ub("Impervious", upgraded, "block"))


@card("Offering", cost=0, card_type=CardType.SKILL, target=TargetType.NONE, exhausts=True)
def _offering(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Lose 6 HP, gain 2 energy, draw 3 cards
    state.player_hp = max(0, state.player_hp - 6 + _ub("Offering", upgraded, "hp_loss"))
    state.energy += 2 + _ub("Offering", upgraded, "energy")
    state.piles.draw_cards(3 + _ub("Offering", upgraded, "draw"), state.rng)


@card("Berserk", cost=0, card_type=CardType.SKILL, target=TargetType.NONE)
def _berserk(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    state.energy += 2
    state.player_powers.vulnerable += 1


# ---------------------------------------------------------------------------
# Rare Powers
# ---------------------------------------------------------------------------

@card("DemonForm", cost=3, card_type=CardType.POWER, target=TargetType.NONE)
def _demon_form(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # At the start of each turn, gain 2 Strength. Simplified: gain 2 strength now.
    state.player_powers.strength += 2 + _ub("DemonForm", upgraded, "strength")
    # In a full implementation, this would set a "demon_form" power that triggers at turn start.


@card("DoubleTap", cost=1, card_type=CardType.POWER, target=TargetType.NONE)
def _double_tap(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Next attack played twice. Simplified: no trigger system.
    pass


@card("Brutality", cost=0, card_type=CardType.POWER, target=TargetType.NONE)
def _brutality(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # At start of turn, lose 1 HP and draw 1 card. Simplified.
    pass


@card("Corruption", cost=3, card_type=CardType.POWER, target=TargetType.NONE)
def _corruption(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Skills cost 0 and exhaust. Simplified: no trigger system.
    pass


@card("DarkEmbrace", cost=2, card_type=CardType.POWER, target=TargetType.NONE)
def _dark_embrace(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Whenever a card is Exhausted, draw 1 card. Simplified: no trigger system.
    pass


@card("Juggernaut", cost=2, card_type=CardType.POWER, target=TargetType.NONE)
def _juggernaut(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Whenever you gain block, deal 5 damage to a random enemy. Simplified.
    pass


@card("LimitBreak", cost=1, card_type=CardType.POWER, target=TargetType.NONE, exhausts=True)
def _limit_break(state: "CombatState", _hi: int, _ti: int, upgraded: int = 0) -> None:
    # Double your Strength
    state.player_powers.strength *= 2
