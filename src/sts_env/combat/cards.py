"""Card definitions for the Ironclad starter set + selected commons.

Each card has a CardSpec that carries both static metadata and declarative
effect data.  Simple cards are pure data; complex cards use the custom=
callable for effects that don't fit the declarative shape.

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

from dataclasses import dataclass, field
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


# Custom handler signature: (state, hand_index, target_index, upgraded) -> None
CardHandler = Callable[["CombatState", int, int, int], None]


@dataclass(frozen=True)
class CardSpec:
    card_id: str
    cost: int
    card_type: CardType
    target: TargetType
    exhausts: bool = False
    playable: bool = True       # False for curses/statuses (AscendersBane, Dazed)

    # Declarative effects — all default to 0 / no-op
    attack: int = 0             # damage per hit (single target or all if ALL_ENEMIES)
    hits: int = 1               # number of attack hits
    block: int = 0              # block gained by player
    vulnerable: int = 0         # stacks applied to target(s)
    weak: int = 0               # stacks applied to target(s)
    enemy_strength: int = 0     # added to enemy strength; negative = Disarm
    self_strength: int = 0      # player strength gained
    self_strength_eot_loss: int = 0  # player strength lost at end of turn (Flex)
    self_dexterity: int = 0     # player dexterity gained
    self_vulnerable: int = 0    # player vulnerable stacks (Berserk)
    metallicize: int = 0        # player metallicize stacks
    energy: int = 0             # energy gained
    draw: int = 0               # cards drawn
    hp_loss: int = 0            # player HP lost

    # Per-field upgrade deltas (keys must match field names above, plus "cost")
    upgrade: dict[str, int] = field(default_factory=dict, hash=False, compare=False)

    # Escape hatch for effects that don't fit the declarative model.
    # Runs AFTER declarative effects.
    custom: CardHandler | None = field(default=None, hash=False, compare=False)


_SPECS: dict[str, CardSpec] = {}


def register(
    card_id: str,
    *,
    cost: int,
    card_type: CardType,
    target: TargetType,
    exhausts: bool = False,
    playable: bool = True,
    attack: int = 0,
    hits: int = 1,
    block: int = 0,
    vulnerable: int = 0,
    weak: int = 0,
    enemy_strength: int = 0,
    self_strength: int = 0,
    self_strength_eot_loss: int = 0,
    self_dexterity: int = 0,
    self_vulnerable: int = 0,
    metallicize: int = 0,
    energy: int = 0,
    draw: int = 0,
    hp_loss: int = 0,
    upgrade: dict[str, int] | None = None,
    custom: CardHandler | None = None,
) -> None:
    _SPECS[card_id] = CardSpec(
        card_id=card_id,
        cost=cost,
        card_type=card_type,
        target=target,
        exhausts=exhausts,
        playable=playable,
        attack=attack,
        hits=hits,
        block=block,
        vulnerable=vulnerable,
        weak=weak,
        enemy_strength=enemy_strength,
        self_strength=self_strength,
        self_strength_eot_loss=self_strength_eot_loss,
        self_dexterity=self_dexterity,
        self_vulnerable=self_vulnerable,
        metallicize=metallicize,
        energy=energy,
        draw=draw,
        hp_loss=hp_loss,
        upgrade=upgrade or {},
        custom=custom,
    )


def get_spec(card_id: str) -> CardSpec:
    base = card_id[:-1] if card_id.endswith("+") else card_id
    return _SPECS[base]


def _apply_spec(
    state: "CombatState",
    spec: CardSpec,
    target_index: int,
    upgraded: int,
) -> None:
    """Execute declarative effects in a fixed, deterministic order.

    Order: hp_loss → energy → attack → debuffs → block → self-buffs → draw
    """
    u = spec.upgrade if upgraded else {}

    # 1. Player HP loss
    if spec.hp_loss:
        loss = spec.hp_loss + u.get("hp_loss", 0)
        state.player_hp = max(0, state.player_hp - loss)

    # 2. Energy gain
    if spec.energy:
        state.energy += spec.energy + u.get("energy", 0)

    # 3. Attack
    if spec.attack:
        dmg = spec.attack + u.get("attack", 0)
        hits = spec.hits + u.get("hits", 0)
        if spec.target == TargetType.ALL_ENEMIES:
            for enemy in state.enemies:
                if enemy.hp > 0 and enemy.name != "Empty":
                    for _ in range(hits):
                        attack_enemy(state, enemy, dmg)
        else:
            enemy = state.enemies[target_index]
            for _ in range(hits):
                attack_enemy(state, enemy, dmg)

    # 4. Debuffs applied to target(s)
    vuln = spec.vulnerable + u.get("vulnerable", 0)
    weak = spec.weak + u.get("weak", 0)
    estr = spec.enemy_strength + u.get("enemy_strength", 0)
    if vuln or weak or estr:
        if spec.target == TargetType.ALL_ENEMIES:
            for enemy in state.enemies:
                if enemy.hp > 0 and enemy.name != "Empty":
                    enemy.powers.vulnerable += vuln
                    enemy.powers.weak += weak
                    enemy.powers.strength += estr
        else:
            enemy = state.enemies[target_index]
            enemy.powers.vulnerable += vuln
            enemy.powers.weak += weak
            enemy.powers.strength += estr

    # 5. Player block
    if spec.block:
        state.player_block += gain_block(
            state.player_powers, spec.block + u.get("block", 0)
        )

    # 6. Player self-buffs
    if spec.self_strength or spec.self_strength_eot_loss:
        state.player_powers.strength += spec.self_strength + u.get("self_strength", 0)
        state.player_powers.strength_loss_eot += (
            spec.self_strength_eot_loss + u.get("self_strength_eot_loss", 0)
        )

    if spec.self_dexterity:
        state.player_powers.dexterity += spec.self_dexterity + u.get("self_dexterity", 0)

    if spec.self_vulnerable:
        state.player_powers.vulnerable += spec.self_vulnerable + u.get("self_vulnerable", 0)

    if spec.metallicize:
        state.player_powers.metallicize += spec.metallicize + u.get("metallicize", 0)

    # 7. Draw (last so it doesn't interact with the current card's effects)
    if spec.draw:
        state.piles.draw_cards(spec.draw + u.get("draw", 0), state.rng)


def play_card(state: "CombatState", hand_index: int, target_index: int) -> None:
    """Validate and execute a card play, updating state in place."""
    raw = state.piles.hand[hand_index]
    if isinstance(raw, str):
        raw_id = raw
        cost_override = None
    else:
        raw_id = raw.card_id
        cost_override = raw.cost_override

    upgraded = 1 if raw_id.endswith("+") else 0
    card_id = raw_id[:-1] if upgraded else raw_id

    spec = _SPECS[card_id]

    if not spec.playable:
        raise ValueError(f"Card {card_id!r} is unplayable.")

    effective_cost = (
        cost_override
        if cost_override is not None
        else spec.cost + (spec.upgrade.get("cost", 0) if upgraded else 0)
    )
    if effective_cost > state.energy:
        raise ValueError(
            f"Not enough energy to play {card_id!r}: "
            f"need {effective_cost}, have {state.energy}."
        )
    if spec.target == TargetType.SINGLE_ENEMY and not (
        0 <= target_index < len(state.enemies)
    ):
        raise ValueError(f"Invalid target_index {target_index}.")

    state.energy -= effective_cost
    played_card = state.piles.play_card(hand_index)

    _apply_spec(state, spec, target_index, upgraded)
    if spec.custom is not None:
        spec.custom(state, hand_index, target_index, upgraded)

    if spec.exhausts:
        state.piles.move_to_exhaust(played_card)
    else:
        state.piles.move_to_discard(played_card)


# ---------------------------------------------------------------------------
# Custom handlers (for cards whose effects can't be expressed declaratively)
# ---------------------------------------------------------------------------

def _anger_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.piles.add_to_discard(Card("Anger"))


def _havoc_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    if state.piles.draw:
        top_card = state.piles.draw.pop(0)
        state.piles.move_to_exhaust(top_card)


def _sword_boomerang_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    dmg = 3 + (1 if upgraded else 0)
    for _ in range(3):
        alive = [e for e in state.enemies if e.hp > 0 and e.name != "Empty"]
        if alive:
            target = alive[state.rng.randint(0, len(alive) - 1)]
            attack_enemy(state, target, dmg)


def _wild_strike_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    # Real StS adds a Wound to the draw pile; simplified: add to discard
    state.piles.add_to_discard(Card("WildStrike"))


def _dropkick_custom(state: "CombatState", _hi: int, ti: int, _upgraded: int) -> None:
    if state.enemies[ti].powers.vulnerable > 0:
        state.energy += 1
        state.piles.draw_cards(1, state.rng)


def _feed_custom(state: "CombatState", _hi: int, ti: int, upgraded: int) -> None:
    enemy = state.enemies[ti]
    if enemy.hp <= 0:
        gain = 3 + (1 if upgraded else 0)
        state.player_max_hp += gain
        state.player_hp = min(state.player_hp + gain, state.player_max_hp)


def _reckless_charge_custom(
    state: "CombatState", _hi: int, _ti: int, _upgraded: int
) -> None:
    state.piles.place_on_top(Card("Dazed"))


def _entrench_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.player_block *= 2


def _limit_break_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.player_powers.strength *= 2


# ---------------------------------------------------------------------------
# Card registry
# ---------------------------------------------------------------------------

A = CardType.ATTACK
S = CardType.SKILL
P = CardType.POWER
C = CardType.CURSE
ST = CardType.STATUS
SE = TargetType.SINGLE_ENEMY
AE = TargetType.ALL_ENEMIES
NO = TargetType.NONE

# --- Starter ---
register("Strike", cost=1, card_type=A, target=SE, attack=6, upgrade={"attack": 3})
register("Defend", cost=1, card_type=S, target=NO, block=5, upgrade={"block": 3})
register("Bash",   cost=2, card_type=A, target=SE, attack=8, vulnerable=2,
         upgrade={"attack": 2, "vulnerable": 1})

# --- Curse ---
register("AscendersBane", cost=0, card_type=C, target=NO, playable=False)

# --- Status ---
register("Slimed", cost=1, card_type=ST, target=NO, exhausts=True)
register("Dazed",  cost=0, card_type=ST, target=NO, exhausts=True, playable=False)

# --- Common Attacks ---
register("Anger",         cost=0, card_type=A, target=SE, attack=6,
         upgrade={"attack": 2}, custom=_anger_custom)
register("Cleave",        cost=1, card_type=A, target=AE, attack=8,
         upgrade={"attack": 3})
register("Clothesline",   cost=2, card_type=A, target=SE, attack=12, vulnerable=2,
         upgrade={"attack": 2, "vulnerable": 1})
register("Headbutt",      cost=1, card_type=A, target=SE, attack=9,
         upgrade={"attack": 3})
register("IronWave",      cost=1, card_type=A, target=SE, attack=5, block=5,
         upgrade={"attack": 2, "block": 2})
register("PommelStrike",  cost=1, card_type=A, target=SE, attack=9, draw=1,
         upgrade={"attack": 1, "draw": 1})
register("ThunderClap",   cost=1, card_type=A, target=AE, attack=7, vulnerable=1,
         upgrade={"attack": 2})
register("TrueStrike",    cost=1, card_type=A, target=SE, attack=12,
         upgrade={"attack": 2})
register("TwinStrike",    cost=1, card_type=A, target=SE, attack=5, hits=2,
         upgrade={"attack": 2})
register("WildStrike",    cost=1, card_type=A, target=SE, attack=12,
         upgrade={"attack": 5}, custom=_wild_strike_custom)
register("SwordBoomerang", cost=1, card_type=A, target=AE,
         custom=_sword_boomerang_custom)

# --- Common Skills ---
register("Armaments",  cost=1, card_type=S, target=NO, block=5,
         upgrade={"block": 3})
register("Flex",       cost=0, card_type=S, target=NO,
         self_strength=2, self_strength_eot_loss=2,
         upgrade={"self_strength": 2, "self_strength_eot_loss": 2})
register("Havoc",      cost=1, card_type=S, target=NO, exhausts=True,
         custom=_havoc_custom)
register("ShrugItOff", cost=1, card_type=S, target=NO, block=8, draw=1,
         upgrade={"block": 3, "draw": 1})
register("WarCry",     cost=0, card_type=S, target=NO, exhausts=True, draw=1,
         upgrade={"draw": 1})

# --- Uncommon Attacks ---
register("Carnage",        cost=2, card_type=A, target=SE, exhausts=True, attack=20,
         upgrade={"attack": 8})
register("Dropkick",       cost=1, card_type=A, target=SE, attack=5,
         upgrade={"attack": 3}, custom=_dropkick_custom)
register("Pummel",         cost=1, card_type=A, target=SE, exhausts=True,
         attack=2, hits=4, upgrade={"hits": 1})
register("Rampage",        cost=2, card_type=A, target=SE, attack=18,
         upgrade={"attack": 10})
register("RecklessCharge", cost=1, card_type=A, target=SE, attack=7,
         upgrade={"attack": 4}, custom=_reckless_charge_custom)
register("SearingBlow",    cost=2, card_type=A, target=SE, attack=12,
         upgrade={"attack": 3})
register("SeverSoul",      cost=2, card_type=A, target=SE, exhausts=True, attack=16,
         upgrade={"attack": 6})
register("Uppercut",       cost=2, card_type=A, target=SE, attack=13, vulnerable=1, weak=1,
         upgrade={"attack": 3, "vulnerable": 1, "weak": 1})
register("Whirlwind",      cost=1, card_type=A, target=AE, attack=5,
         upgrade={"attack": 3})

# --- Uncommon Skills ---
register("Bloodletting", cost=0, card_type=S, target=NO, hp_loss=3, energy=2,
         upgrade={"energy": 1})
register("BurningPact",  cost=1, card_type=S, target=NO, draw=2,
         upgrade={"draw": 1})
register("Disarm",       cost=1, card_type=S, target=SE, exhausts=True,
         enemy_strength=-2, upgrade={"enemy_strength": -1})
register("DualWield",    cost=1, card_type=S, target=NO)
register("Entrench",     cost=2, card_type=S, target=NO, upgrade={"cost": -1},
         custom=_entrench_custom)
register("FlameBarrier", cost=2, card_type=S, target=NO, block=12,
         upgrade={"block": 4})
register("GhostArmor",   cost=1, card_type=S, target=NO, exhausts=True, block=10,
         upgrade={"block": 3})
register("PowerThrough", cost=1, card_type=S, target=NO, block=15,
         upgrade={"block": 5})
register("Rage",         cost=0, card_type=S, target=NO)
register("SecondWind",   cost=1, card_type=S, target=NO, block=5,
         upgrade={"block": 3})
register("SeeingRed",    cost=1, card_type=S, target=NO, exhausts=True, energy=2,
         upgrade={"energy": 1})
register("Sentinel",     cost=1, card_type=S, target=NO, block=12,
         upgrade={"block": 3})
register("ShockWave",    cost=2, card_type=S, target=AE, exhausts=True,
         vulnerable=3, weak=3, upgrade={"vulnerable": 1, "weak": 1})
register("SpotWeakness", cost=1, card_type=S, target=SE, self_strength=3,
         upgrade={"self_strength": 1})
register("BattleTrance", cost=0, card_type=S, target=NO, draw=3,
         upgrade={"draw": 1})

# --- Uncommon Powers ---
register("FeelNoPain",  cost=1, card_type=P, target=NO)
register("Inflame",     cost=1, card_type=P, target=NO, self_strength=2,
         upgrade={"self_strength": 1})
register("Metallicize", cost=1, card_type=P, target=NO, metallicize=3,
         upgrade={"metallicize": 1})

# --- Rare Attacks ---
register("Bludgeon", cost=3, card_type=A, target=SE, attack=32,
         upgrade={"attack": 10})
register("Feed",     cost=1, card_type=A, target=SE, attack=10,
         upgrade={"attack": 5}, custom=_feed_custom)

# --- Rare Skills ---
register("Impervious", cost=2, card_type=S, target=NO, exhausts=True, block=30,
         upgrade={"block": 10})
register("Offering",   cost=0, card_type=S, target=NO, exhausts=True,
         hp_loss=6, energy=2, draw=3,
         upgrade={"hp_loss": -4, "energy": 1, "draw": 2})
register("Berserk",    cost=0, card_type=S, target=NO, energy=2, self_vulnerable=1,
         upgrade={"energy": 1})

# --- Rare Powers ---
register("Brutality",   cost=0, card_type=P, target=NO)
register("Corruption",  cost=3, card_type=P, target=NO, upgrade={"cost": -1})
register("DarkEmbrace", cost=2, card_type=P, target=NO)
register("DemonForm",   cost=3, card_type=P, target=NO, self_strength=2,
         upgrade={"self_strength": 1})
register("DoubleTap",   cost=1, card_type=P, target=NO)
register("Juggernaut",  cost=2, card_type=P, target=NO)
register("LimitBreak",  cost=1, card_type=P, target=NO, exhausts=True,
         custom=_limit_break_custom)
