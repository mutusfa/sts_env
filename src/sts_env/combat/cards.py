"""Card definitions for the Ironclad starter set + selected commons.

Each card has a CardSpec that carries both static metadata and declarative
effect data.  Simple cards are pure data; complex cards use the custom=
callable for effects that don't fit the declarative shape.

Cards registered:
  Starter:  Strike x5, Defend x4, Bash x1
  Curse:    AscendersBane (unplayable)
  Status:   Slimed, Dazed, Burn
  Common:   Anger, Armaments, Cleave, Clothesline, Flex, Havoc, Headbutt,
            IronWave, PommelStrike, ShrugItOff, SwordBoomerang, ThunderClap,
            TrueStrike, TwinStrike, WarCry, WildStrike
  Uncommon: Bloodletting, BodySlam, BurningPact, Carnage, Combust, Disarm,
            Dropkick, DualWield, Entrench, FeelNoPain, FlameBarrier,
            GhostArmor, HeavyBlade, Hemokinesis, Inflame, Metallicize,
            PowerThrough, Pummel, Rage, Rampage, RecklessCharge, SecondWind,
            SeeingRed, SearingBlow, Sentinel, SeverSoul, ShockWave,
            SpotWeakness, Uppercut, Whirlwind, BattleTrance
  Rare:     Bludgeon, Berserk, Brutality, Corruption, DarkEmbrace, DemonForm,
            DoubleTap, Exhume, Feed, FiendFire, Immolate, Impervious,
            Juggernaut, LimitBreak, Offering, Reaper
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

from .card import Card
from .pending import ChoiceFrame, ThunkFrame
from .powers import attack_enemy, gain_block

if TYPE_CHECKING:
    from .state import CombatState


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    CURSE = auto()
    STATUS = auto()


class CardColor(Enum):
    RED = auto()        # Ironclad
    GREEN = auto()      # Silent
    BLUE = auto()       # Defect
    PURPLE = auto()     # Watcher
    COLORLESS = auto()
    CURSE = auto()


class Rarity(Enum):
    BASIC = auto()      # Strike, Defend, Bash, AscendersBane
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    SPECIAL = auto()    # status cards, event-only cards


class TargetType(Enum):
    SINGLE_ENEMY = auto()
    ALL_ENEMIES = auto()
    NONE = auto()       # self-targeting skills, powers


# Custom handler signature: (state, hand_index, target_index, upgraded) -> None
CardHandler = Callable[["CombatState", int, int, int], None]

# EOT resolve handler: called once per copy in hand at end of player turn
EotHandler = Callable[["CombatState"], None]


@dataclass(frozen=True)
class CardSpec:
    card_id: str
    cost: int
    card_type: CardType
    target: TargetType
    color: CardColor = CardColor.RED
    rarity: Rarity = Rarity.COMMON
    exhausts: bool = False
    playable: bool = True       # False for curses/statuses (AscendersBane, Dazed)
    ethereal: bool = False      # auto-exhaust at end of turn if still in hand
    x_cost: bool = False        # spends all remaining energy (Whirlwind)

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
    heal: int = 0               # player HP healed (clamped to max)
    hp_loss: int = 0            # player HP lost
    innate: bool = False        # always drawn in opening hand

    # Per-field upgrade deltas (keys must match field names above, plus "cost")
    upgrade: dict[str, int] = field(default_factory=dict, hash=False, compare=False)

    # Escape hatch for effects that don't fit the declarative model.
    # Runs AFTER declarative effects.
    custom: CardHandler | None = field(default=None, hash=False, compare=False)

    # Called once per copy in hand at end of player turn (before discard).
    eot_resolve: EotHandler | None = field(default=None, hash=False, compare=False)


_SPECS: dict[str, CardSpec] = {}


def register(
    card_id: str,
    *,
    cost: int,
    card_type: CardType,
    target: TargetType,
    color: CardColor = CardColor.RED,
    rarity: Rarity = Rarity.COMMON,
    exhausts: bool = False,
    playable: bool = True,
    ethereal: bool = False,
    x_cost: bool = False,
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
    heal: int = 0,
    hp_loss: int = 0,
    innate: bool = False,
    upgrade: dict[str, int] | None = None,
    custom: CardHandler | None = None,
    eot_resolve: EotHandler | None = None,
) -> None:
    _SPECS[card_id] = CardSpec(
        card_id=card_id,
        cost=cost,
        card_type=card_type,
        target=target,
        color=color,
        rarity=rarity,
        exhausts=exhausts,
        playable=playable,
        ethereal=ethereal,
        x_cost=x_cost,
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
        heal=heal,
        hp_loss=hp_loss,
        innate=innate,
        upgrade=upgrade or {},
        custom=custom,
        eot_resolve=eot_resolve,
    )


def get_spec(card_id: str) -> CardSpec:
    base = card_id.rstrip("+")
    return _SPECS[base]


def all_specs() -> dict[str, CardSpec]:
    """Return a shallow copy of the full spec registry."""
    return dict(_SPECS)


def _apply_spec(
    state: "CombatState",
    spec: CardSpec,
    target_index: int,
    upgraded: int,
    *,
    x_energy: int = 0,
    upgrade_count: int = 0,
) -> None:
    """Execute declarative effects in a fixed, deterministic order.

    Order: hp_loss → heal → energy → attack → debuffs → block → self-buffs → draw
    """
    u = spec.upgrade if upgraded else {}

    # 1. Player HP loss
    if spec.hp_loss:
        loss = spec.hp_loss + u.get("hp_loss", 0)
        state.player_hp = max(0, state.player_hp - loss)

    # 1b. Player heal (clamped to max HP)
    if spec.heal:
        heal_amt = spec.heal + u.get("heal", 0)
        state.player_hp = min(state.player_max_hp, state.player_hp + heal_amt)

    # 2. Energy gain
    if spec.energy:
        state.energy += spec.energy + u.get("energy", 0)

    # 3. Attack
    if spec.attack:
        from .events import Event, emit as _emit
        dmg = spec.attack + u.get("attack", 0)
        hits = spec.hits + u.get("hits", 0)
        # X-cost cards: hits = energy spent (Whirlwind)
        if spec.x_cost:
            hits = x_energy
        # Snapshot HP for ATTACK_DAMAGED emission after all hits
        if spec.target == TargetType.ALL_ENEMIES:
            hp_before = {ei: state.enemies[ei].hp for ei, e in enumerate(state.enemies)
                         if e.hp > 0 and e.name != "Empty"}
            for ei, enemy in enumerate(state.enemies):
                if enemy.hp > 0 and enemy.name != "Empty":
                    for _ in range(hits):
                        attack_enemy(state, enemy, dmg, enemy_index=ei)
        else:
            enemy = state.enemies[target_index]
            hp_before = {target_index: enemy.hp}
            for _ in range(hits):
                attack_enemy(state, enemy, dmg, enemy_index=target_index)
        # Emit ATTACK_DAMAGED for each enemy that took HP loss but is still alive
        for ei, hpb in hp_before.items():
            e = state.enemies[ei]
            if 0 < e.hp < hpb:
                _emit(state, Event.ATTACK_DAMAGED, ei, hp_before=hpb)

    # 4. Debuffs applied to target(s)
    vuln = spec.vulnerable + u.get("vulnerable", 0)
    weak = spec.weak + u.get("weak", 0)
    estr = spec.enemy_strength + u.get("enemy_strength", 0)
    if vuln or weak or estr:
        from .powers import DebuffKind, apply_debuff
        if spec.target == TargetType.ALL_ENEMIES:
            for ei, enemy in enumerate(state.enemies):
                if enemy.hp > 0 and enemy.name != "Empty":
                    if vuln:
                        apply_debuff(state, enemy.powers, DebuffKind.VULNERABLE, vuln, target_index=ei)
                    if weak:
                        apply_debuff(state, enemy.powers, DebuffKind.WEAK, weak, target_index=ei)
                    if estr:
                        apply_debuff(state, enemy.powers, DebuffKind.STRENGTH_DOWN, estr, target_index=ei)
        else:
            enemy = state.enemies[target_index]
            if vuln:
                apply_debuff(state, enemy.powers, DebuffKind.VULNERABLE, vuln, target_index=target_index)
            if weak:
                apply_debuff(state, enemy.powers, DebuffKind.WEAK, weak, target_index=target_index)
            if estr:
                apply_debuff(state, enemy.powers, DebuffKind.STRENGTH_DOWN, estr, target_index=target_index)

    # 5. Player block
    if spec.block:
        from .engine import gain_player_block
        gain_player_block(
            state, gain_block(
                state.player_powers, spec.block + u.get("block", 0)
            )
        )

    # 6. Player self-buffs
    if spec.self_strength or spec.self_strength_eot_loss:
        state.player_powers.strength += spec.self_strength + u.get("self_strength", 0)
        from .powers import DebuffKind, apply_debuff
        eot_loss = spec.self_strength_eot_loss + u.get("self_strength_eot_loss", 0)
        if eot_loss > 0:
            apply_debuff(state, state.player_powers, DebuffKind.STRENGTH_DOWN_EOT, eot_loss)

    if spec.self_dexterity:
        state.player_powers.dexterity += spec.self_dexterity + u.get("self_dexterity", 0)

    if spec.self_vulnerable:
        from .powers import DebuffKind, apply_debuff
        apply_debuff(state, state.player_powers, DebuffKind.SELF_VULNERABLE,
                     spec.self_vulnerable + u.get("self_vulnerable", 0))

    if spec.metallicize:
        state.player_powers.metallicize += spec.metallicize + u.get("metallicize", 0)

    # 7. Draw (last so it doesn't interact with the current card's effects)
    if spec.draw:
        state.piles.draw_cards(spec.draw + u.get("draw", 0), state.rng)


def play_card(state: "CombatState", hand_index: int, target_index: int) -> None:
    """Validate and execute a card play, updating state in place."""
    card = state.piles.hand[hand_index]
    raw_id = card.card_id

    upgrade_count = len(raw_id) - len(raw_id.rstrip("+"))
    card_id = raw_id.rstrip("+")

    spec = _SPECS[card_id]

    if not spec.playable:
        raise ValueError(f"Card {card_id!r} is unplayable.")

    # Cost calculation
    effective_cost = card.effective_cost(state.energy)

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

    upgraded = 1 if upgrade_count > 0 else 0
    x_energy = effective_cost if spec.x_cost else 0
    _apply_spec(state, spec, target_index, upgraded, x_energy=x_energy, upgrade_count=upgrade_count)
    if spec.custom is not None:
        if spec.x_cost:
            spec.custom(state, hand_index, target_index, upgrade_count, x_energy)
        else:
            spec.custom(state, hand_index, target_index, upgrade_count)

    if played_card.effective_exhausts():
        state.piles.move_to_exhaust(played_card)
    else:
        state.piles.move_to_discard(played_card)

    # Emit CARD_PLAYED for subscribed listeners (Rage, Gremlin Nob)
    from .events import emit, Event
    emit(state, Event.CARD_PLAYED, "player", card=played_card)

    # Emit CARD_EXHAUSTED for triggered effects (Dark Embrace, Feel No Pain, Sentinel)
    if played_card.effective_exhausts():
        emit(state, Event.CARD_EXHAUSTED, "player", card=played_card)


# ---------------------------------------------------------------------------
# Custom handlers (for cards whose effects can't be expressed declaratively)
# ---------------------------------------------------------------------------

def _anger_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.piles.spawn_to_discard(Card("Anger"), state)


def _havoc_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    # Reshuffle if draw is empty
    if not state.piles.draw:
        if not state.piles.discard:
            return  # nothing to play
        state.piles.shuffle_draw_from_discard(state.rng)
    if not state.piles.draw:
        return

    top_card = state.piles.draw.pop(0)
    top_spec = _SPECS.get(top_card.card_id.rstrip("+"))

    if not top_spec or not top_spec.playable:
        # Unplayable card: still exhaust it
        state.piles.move_to_exhaust(top_card)
        return

    # Pick target for the played card
    if top_spec.target == TargetType.SINGLE_ENEMY:
        alive = [e for e in state.enemies if e.hp > 0 and e.name != "Empty"]
        if alive:
            ti = state.enemies.index(alive[state.rng.randint(0, len(alive) - 1)])
        else:
            ti = 0
    else:
        ti = 0

    up = 1 if top_card.upgraded else 0

    # Push thunk FIRST (LIFO): exhaust the played card after its effects resolve.
    # This thunk will run after any frames the played card pushes (e.g. BurningPact's choice).
    from .events import Event, emit as _emit

    def _havoc_exhaust_played(s: "CombatState") -> None:
        s.piles.move_to_exhaust(top_card)
        _emit(s, Event.CARD_EXHAUSTED, "player", card=top_card)

    state.pending_stack.append(
        ThunkFrame(run=_havoc_exhaust_played, label="havoc-exhaust-played")
    )

    # Now resolve the top card's effects — any frames it pushes land on top of our thunk
    _apply_spec(state, top_spec, ti, up)
    if top_spec.custom is not None:
        top_spec.custom(state, -1, ti, up)


def _sword_boomerang_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .events import Event, emit as _emit
    dmg = 3 + (1 if upgraded else 0)
    # Snapshot HP for all alive enemies before the random hits
    hp_before = {i: e.hp for i, e in enumerate(state.enemies)
                 if e.hp > 0 and e.name != "Empty"}
    for _ in range(3):
        alive_indices = [i for i, e in enumerate(state.enemies) if e.hp > 0 and e.name != "Empty"]
        if alive_indices:
            idx = alive_indices[state.rng.randint(0, len(alive_indices) - 1)]
            target = state.enemies[idx]
            attack_enemy(state, target, dmg, enemy_index=idx)
    for ei, hpb in hp_before.items():
        e = state.enemies[ei]
        if 0 < e.hp < hpb:
            _emit(state, Event.ATTACK_DAMAGED, ei, hp_before=hpb)


def _wild_strike_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.piles.spawn_shuffled_into_draw(Card("Wound"), state, state.rng)


def _power_through_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.piles.spawn_to_hand(Card("Wound"), state)
    state.piles.spawn_to_hand(Card("Wound"), state)


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
    state.piles.spawn_on_top_of_draw(Card("Dazed"), state)


def _entrench_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.player_block *= 2


def _limit_break_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.player_powers.strength *= 2


def _rampage_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    # Rampage: 8 dmg + accumulated bonus. Bonus grows each time it's played.
    bonus = 5 + (3 if upgraded else 0)
    enemy = state.enemies[_ti]
    from .powers import calc_damage, apply_damage
    raw = calc_damage(state.rampage_extra, state.player_powers, enemy.powers)
    nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block = nb
    enemy.hp = nhp
    state.rampage_extra += bonus


def _second_wind_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    block_per = 5 + (2 if upgraded else 0)
    # Exhaust all non-Attack cards in hand
    to_exhaust = []
    for card in state.piles.hand:
        spec = _SPECS.get(card.card_id.rstrip("+"))
        if spec and spec.card_type != CardType.ATTACK:
            to_exhaust.append(card)
    count = len(to_exhaust)
    for card in to_exhaust:
        state.piles.hand.remove(card)
        state.piles.move_to_exhaust(card)
    from .engine import gain_player_block
    gain_player_block(state, block_per * count)


def _searing_blow_custom(state: "CombatState", _hi: int, _ti: int, upgrade_count: int) -> None:
    # Base damage 12 is handled declaratively. Custom adds the scaling bonus.
    # Total damage = 12 + n*(n+1)/2 where n = upgrade level.
    if upgrade_count > 0:
        bonus = upgrade_count * (upgrade_count + 1) // 2
        enemy = state.enemies[_ti]
        from .powers import calc_damage, apply_damage
        raw = calc_damage(bonus, state.player_powers, enemy.powers)
        nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
        enemy.block = nb
        enemy.hp = nhp


def _body_slam_custom(state: "CombatState", _hi: int, ti: int, _upgraded: int) -> None:
    from .powers import calc_damage, apply_damage
    dmg = state.player_block
    enemy = state.enemies[ti]
    raw = calc_damage(dmg, state.player_powers, enemy.powers)
    nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block = nb
    enemy.hp = nhp


def _heavy_blade_custom(state: "CombatState", _hi: int, ti: int, upgraded: int) -> None:
    from .powers import calc_damage, apply_damage
    base_dmg = 14 + (4 if upgraded else 0)
    multiplier = 4 if upgraded else 3
    total_str_bonus = multiplier * state.player_powers.strength
    dmg = base_dmg + total_str_bonus
    enemy = state.enemies[ti]
    # Apply weak/vulnerable but NOT strength again (already included)
    raw = dmg
    if state.player_powers.weak > 0:
        import math
        raw = math.floor(raw * 0.75)
    if enemy.powers.vulnerable > 0:
        import math
        raw = math.floor(raw * 1.5)
    raw = max(0, raw)
    nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block = nb
    enemy.hp = nhp


def _reaper_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .powers import calc_damage, apply_damage
    from .events import Event, emit as _emit
    base_dmg = 5 if upgraded else 4
    heal_amount = 0
    # Snapshot HP for ATTACK_DAMAGED emission
    hp_before = {ei: state.enemies[ei].hp for ei, e in enumerate(state.enemies)
                 if e.hp > 0 and e.name != "Empty"}
    for ei, enemy in enumerate(state.enemies):
        if enemy.hp > 0 and enemy.name != "Empty":
            pre_hp = enemy.hp
            raw = calc_damage(base_dmg, state.player_powers, enemy.powers)
            nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
            enemy.block = nb
            enemy.hp = nhp
            heal_amount += pre_hp - enemy.hp
    if heal_amount > 0:
        state.player_hp = min(state.player_max_hp, state.player_hp + heal_amount)
    for ei, hpb in hp_before.items():
        e = state.enemies[ei]
        if 0 < e.hp < hpb:
            _emit(state, Event.ATTACK_DAMAGED, ei, hp_before=hpb)


def _immolate_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    state.piles.spawn_to_discard(Card("Burn"), state)


def _fiend_fire_custom(state: "CombatState", hi: int, ti: int, upgraded: int) -> None:
    from .events import Event, emit as _emit
    from .powers import calc_damage, apply_damage
    dmg_per = 10 if upgraded else 7
    # Exhaust entire hand except this card
    to_exhaust = [c for c in state.piles.hand]
    count = len(to_exhaust)
    for card in to_exhaust:
        state.piles.hand.remove(card)
        state.piles.move_to_exhaust(card)
        _emit(state, Event.CARD_EXHAUSTED, "player", card=card)
    # Deal damage for each exhausted card
    enemy = state.enemies[ti]
    for _ in range(count):
        raw = calc_damage(dmg_per, state.player_powers, enemy.powers)
        nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
        enemy.block = nb
        enemy.hp = nhp


def _exhume_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    if not state.piles.exhaust:
        return
    choices = list(state.piles.exhaust)

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.exhaust:
            s.piles.exhaust.remove(card)
        s.piles.hand.append(card)

    state.pending_stack.append(
        ChoiceFrame(choices=choices, kind="exhume", on_choose=on_choose)
    )


def _burning_pact_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    draw_n = 2 + (1 if upgraded else 0)
    if state.piles.hand:
        choices = list(state.piles.hand)

        def on_choose(s: "CombatState", card: Card) -> None:
            from .events import Event, emit as _emit
            if card in s.piles.hand:
                s.piles.hand.remove(card)
            s.piles.move_to_exhaust(card)
            _emit(s, Event.CARD_EXHAUSTED, "player", card=card)
            s.piles.draw_cards(draw_n, s.rng)

        def on_skip(s: "CombatState") -> None:
            s.piles.draw_cards(draw_n, s.rng)

        state.pending_stack.append(
            ChoiceFrame(choices=choices, kind="burningpact",
                        on_choose=on_choose, on_skip=on_skip)
        )
    else:
        # Empty hand: draw immediately
        state.piles.draw_cards(draw_n, state.rng)


def _headbutt_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    if state.piles.discard:
        choices = list(state.piles.discard)

        def on_choose(s: "CombatState", card: Card) -> None:
            if card in s.piles.discard:
                s.piles.discard.remove(card)
            s.piles.place_on_top(card)

        state.pending_stack.append(
            ChoiceFrame(choices=choices, kind="headbutt", on_choose=on_choose)
        )


def _armaments_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    if upgraded:
        # Upgraded Armaments: upgrade all upgradable cards in hand automatically
        for card in state.piles.hand:
            spec = _SPECS.get(card.card_id.rstrip("+"))
            if spec and spec.card_type not in (CardType.STATUS, CardType.CURSE):
                if spec.card_id == "SearingBlow" or not card.upgraded:
                    card.card_id = card.card_id.rstrip("+") + "+" * (card.card_id.count("+") + 1)
    else:
        # Base Armaments: present upgradable cards as choices
        choices = []
        for card in state.piles.hand:
            spec = _SPECS.get(card.card_id.rstrip("+"))
            if spec and spec.card_type not in (CardType.STATUS, CardType.CURSE):
                if spec.card_id == "SearingBlow" or not card.upgraded:
                    choices.append(card)
        if choices:

            def on_choose(s: "CombatState", card: Card) -> None:
                card.card_id = card.card_id.rstrip("+") + "+" * (card.card_id.count("+") + 1)

            state.pending_stack.append(
                ChoiceFrame(choices=choices, kind="armaments", on_choose=on_choose)
            )


def _dual_wield_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    choices = []
    for card in state.piles.hand:
        spec = _SPECS.get(card.card_id.rstrip("+"))
        if spec and spec.card_type in (CardType.ATTACK, CardType.POWER):
            choices.append(card)
    if choices:
        extra = 1 + (1 if upgraded else 0)

        def on_choose(s: "CombatState", card: Card) -> None:
            for _ in range(extra):
                s.piles.spawn_to_hand(Card(card.card_id), s)

        state.pending_stack.append(
            ChoiceFrame(choices=choices, kind="dualwield", on_choose=on_choose)
        )


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
R = CardColor.RED
CL = CardColor.COLORLESS
CU = CardColor.CURSE
B = Rarity.BASIC
CO = Rarity.COMMON
U = Rarity.UNCOMMON
RA = Rarity.RARE
SP = Rarity.SPECIAL

# --- Starter ---
register("Strike", cost=1, card_type=A, target=SE, color=R, rarity=B, attack=6, upgrade={"attack": 3})
register("Defend", cost=1, card_type=S, target=NO, color=R, rarity=B, block=5, upgrade={"block": 3})
register("Bash",   cost=2, card_type=A, target=SE, color=R, rarity=B, attack=8, vulnerable=2,
         upgrade={"attack": 2, "vulnerable": 1})

# --- Curse ---
register("AscendersBane", cost=0, card_type=C, target=NO, color=CU, rarity=B, playable=False)


def _doubt_eot(state: "CombatState") -> None:
    state.player_powers.weak += 1


register("Doubt", cost=0, card_type=C, target=NO, color=CU, rarity=B,
         playable=False, eot_resolve=_doubt_eot)

# --- Status ---
register("Slimed", cost=1, card_type=ST, target=NO, color=CL, rarity=SP, exhausts=True)
register("Dazed",  cost=0, card_type=ST, target=NO, color=CL, rarity=SP, ethereal=True, playable=False)
register("Wound",  cost=1, card_type=ST, target=NO, color=CL, rarity=SP, playable=False)
register("Burn",   cost=1, card_type=ST, target=NO, color=CL, rarity=SP, playable=False, exhausts=True)

# --- Common Attacks ---
register("Anger",         cost=0, card_type=A, target=SE, color=R, rarity=CO, attack=6,
         upgrade={"attack": 2}, custom=_anger_custom)
register("Cleave",        cost=1, card_type=A, target=AE, color=R, rarity=CO, attack=8,
         upgrade={"attack": 3})
register("Clothesline",   cost=2, card_type=A, target=SE, color=R, rarity=CO, attack=12, vulnerable=2,
         upgrade={"attack": 2, "vulnerable": 1})
register("Headbutt",      cost=1, card_type=A, target=SE, color=R, rarity=CO, attack=9,
         upgrade={"attack": 3}, custom=_headbutt_custom)
register("IronWave",      cost=1, card_type=A, target=SE, color=R, rarity=CO, attack=5, block=5,
         upgrade={"attack": 2, "block": 2})
register("PommelStrike",  cost=1, card_type=A, target=SE, color=R, rarity=CO, attack=9, draw=1,
         upgrade={"attack": 1, "draw": 1})
register("ThunderClap",   cost=1, card_type=A, target=AE, color=R, rarity=CO, attack=7, vulnerable=1,
         upgrade={"attack": 2})
register("TrueStrike",    cost=1, card_type=A, target=SE, color=R, rarity=CO, attack=12,
         upgrade={"attack": 2})
register("TwinStrike",    cost=1, card_type=A, target=SE, color=R, rarity=CO, attack=5, hits=2,
         upgrade={"attack": 2})
register("WildStrike",    cost=1, card_type=A, target=SE, color=R, rarity=CO, attack=12,
         upgrade={"attack": 5}, custom=_wild_strike_custom)
register("SwordBoomerang", cost=1, card_type=A, target=AE, color=R, rarity=CO,
         custom=_sword_boomerang_custom)

# --- Common Skills ---
register("Armaments",  cost=1, card_type=S, target=NO, color=R, rarity=CO, block=5,
         upgrade={"block": 3}, custom=_armaments_custom)
register("Flex",       cost=0, card_type=S, target=NO, color=R, rarity=CO,
         self_strength=2, self_strength_eot_loss=2,
         upgrade={"self_strength": 2, "self_strength_eot_loss": 2})
register("Havoc",      cost=1, card_type=S, target=NO, color=R, rarity=CO, exhausts=True,
         custom=_havoc_custom)
register("ShrugItOff", cost=1, card_type=S, target=NO, color=R, rarity=CO, block=8, draw=1,
         upgrade={"block": 3, "draw": 1})
register("WarCry",     cost=0, card_type=S, target=NO, color=R, rarity=CO, exhausts=True, draw=1,
         upgrade={"draw": 1})

# --- Uncommon Attacks ---
register("BodySlam",        cost=1, card_type=A, target=SE, color=R, rarity=U,
         upgrade={"cost": -1}, custom=_body_slam_custom)
register("Carnage",        cost=2, card_type=A, target=SE, color=R, rarity=U, ethereal=True, attack=20,
         upgrade={"attack": 8})
register("Dropkick",       cost=1, card_type=A, target=SE, color=R, rarity=U, attack=5,
         upgrade={"attack": 3}, custom=_dropkick_custom)
register("Pummel",         cost=1, card_type=A, target=SE, color=R, rarity=U, exhausts=True,
         attack=2, hits=4, upgrade={"hits": 1})
register("Rampage",        cost=2, card_type=A, target=SE, color=R, rarity=U, attack=8,
         upgrade={}, custom=_rampage_custom)
register("RecklessCharge", cost=1, card_type=A, target=SE, color=R, rarity=U, attack=7,
         upgrade={"attack": 4}, custom=_reckless_charge_custom)
register("SearingBlow",    cost=2, card_type=A, target=SE, color=R, rarity=U, attack=12,
         custom=_searing_blow_custom)
register("SeverSoul",      cost=2, card_type=A, target=SE, color=R, rarity=U, exhausts=True, attack=16,
         upgrade={"attack": 6})
register("Uppercut",       cost=2, card_type=A, target=SE, color=R, rarity=U, attack=13, vulnerable=1, weak=1,
         upgrade={"attack": 3, "vulnerable": 1, "weak": 1})
register("Whirlwind",      cost=-1, card_type=A, target=AE, color=R, rarity=U, attack=5, x_cost=True,
         upgrade={"attack": 3})
register("HeavyBlade",     cost=2, card_type=A, target=SE, color=R, rarity=U,
         custom=_heavy_blade_custom)
register("Hemokinesis",    cost=1, card_type=A, target=SE, color=R, rarity=U, hp_loss=3,
         attack=15, upgrade={"attack": 6})

# --- Uncommon Skills ---
register("Bloodletting", cost=0, card_type=S, target=NO, color=R, rarity=U, hp_loss=3, energy=2,
         upgrade={"energy": 1})
register("BurningPact",  cost=1, card_type=S, target=NO, color=R, rarity=U,
         custom=_burning_pact_custom)
register("Disarm",       cost=1, card_type=S, target=SE, color=R, rarity=U, exhausts=True,
         enemy_strength=-2, upgrade={"enemy_strength": -1})
register("DualWield",    cost=1, card_type=S, target=NO, color=R, rarity=U, custom=_dual_wield_custom)
register("Entrench",     cost=2, card_type=S, target=NO, color=R, rarity=U, upgrade={"cost": -1},
         custom=_entrench_custom)
register("FlameBarrier", cost=2, card_type=S, target=NO, color=R, rarity=U, block=12,
         upgrade={"block": 4})
register("GhostArmor",   cost=1, card_type=S, target=NO, color=R, rarity=U, ethereal=True, block=10,
         upgrade={"block": 3})
register("PowerThrough", cost=1, card_type=S, target=NO, color=R, rarity=U, block=15,
         upgrade={"block": 5}, custom=_power_through_custom)
register("Rage",         cost=0, card_type=S, target=NO, color=R, rarity=U,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'rage_block', 3 + (2 if u else 0)))
register("SecondWind",   cost=1, card_type=S, target=NO, color=R, rarity=U,
         custom=_second_wind_custom)
register("SeeingRed",    cost=1, card_type=S, target=NO, color=R, rarity=U, exhausts=True, energy=2,
         upgrade={"energy": 1})
register("Sentinel",     cost=1, card_type=S, target=NO, color=R, rarity=U, ethereal=True, block=5,
         upgrade={"block": 3})
register("ShockWave",    cost=2, card_type=S, target=AE, color=R, rarity=U, exhausts=True,
         vulnerable=3, weak=3, upgrade={"vulnerable": 1, "weak": 1})
register("SpotWeakness", cost=1, card_type=S, target=SE, color=R, rarity=U, self_strength=3,
         upgrade={"self_strength": 1})
register("BattleTrance", cost=0, card_type=S, target=NO, color=R, rarity=U, draw=3,
         upgrade={"draw": 1})

# --- Uncommon Powers ---
register("Combust",     cost=1, card_type=P, target=NO, color=R, rarity=U,
         custom=lambda s, _h, _t, u: (
             setattr(s.player_powers, 'combust', s.player_powers.combust + 1),
             setattr(s.player_powers, 'combust_dmg', s.player_powers.combust_dmg + (7 if u else 5)),
         ))
register("FeelNoPain",  cost=1, card_type=P, target=NO, color=R, rarity=U,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'feel_no_pain', s.player_powers.feel_no_pain + 3 + (1 if u else 0)))
register("Inflame",     cost=1, card_type=P, target=NO, color=R, rarity=U, self_strength=2,
         upgrade={"self_strength": 1})
register("Metallicize", cost=1, card_type=P, target=NO, color=R, rarity=U, metallicize=3,
         upgrade={"metallicize": 1})

# --- Rare Attacks ---
register("Bludgeon", cost=3, card_type=A, target=SE, color=R, rarity=RA, attack=32,
         upgrade={"attack": 10})
register("Feed",     cost=1, card_type=A, target=SE, color=R, rarity=RA, attack=10,
         upgrade={"attack": 5}, custom=_feed_custom)
register("Reaper",   cost=2, card_type=A, target=AE, color=R, rarity=RA, exhausts=True,
         custom=_reaper_custom)
register("Immolate", cost=2, card_type=A, target=AE, color=R, rarity=RA, attack=21,
         upgrade={"attack": 7}, custom=_immolate_custom)
register("FiendFire",cost=2, card_type=A, target=SE, color=R, rarity=RA, exhausts=True,
         custom=_fiend_fire_custom)

# --- Rare Skills ---
register("Exhume",      cost=1, card_type=S, target=NO, color=R, rarity=RA, exhausts=True,
         upgrade={"cost": -1}, custom=_exhume_custom)
register("Impervious", cost=2, card_type=S, target=NO, color=R, rarity=RA, exhausts=True, block=30,
         upgrade={"block": 10})
register("Offering",   cost=0, card_type=S, target=NO, color=R, rarity=RA, exhausts=True,
         hp_loss=6, energy=2, draw=3,
         upgrade={"hp_loss": -4, "energy": 1, "draw": 2})
register("Berserk",    cost=0, card_type=S, target=NO, color=R, rarity=RA, self_vulnerable=2,
         upgrade={},
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'berserk_energy', s.player_powers.berserk_energy + 1 + (1 if u else 0)))

# --- Rare Powers ---
register("Brutality",   cost=0, card_type=P, target=NO, color=R, rarity=RA,
         custom=lambda s, _h, _t, _u: setattr(s.player_powers, 'brutality', 1))
def _corruption_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    """Apply Corruption: all skills cost 0 and are exhausted when played."""
    state.player_powers.corruption = True
    # Stamp all existing skills across all piles
    from .events import subscribe, Event
    all_cards = list(state.piles.draw) + list(state.piles.hand) + list(state.piles.discard) + list(state.piles.exhaust)
    for card in all_cards:
        if card.spec.card_type == CardType.SKILL:
            if not card.spec.x_cost:
                card.cost_override = 0
                card.cost_override_duration = "combat"
            card.exhausts_override = True
            card.corrupted = True
    # Subscribe to stamp future skill spawns
    subscribe(state, Event.CARD_CREATED, "corruption_stamp_skill", "player")

register("Corruption",  cost=3, card_type=P, target=NO, color=R, rarity=RA, upgrade={"cost": -1},
         custom=_corruption_custom)
register("DarkEmbrace", cost=2, card_type=P, target=NO, color=R, rarity=RA,
         custom=lambda s, _h, _t, _u: setattr(s.player_powers, 'dark_embrace', s.player_powers.dark_embrace + 1))
register("DemonForm",   cost=3, card_type=P, target=NO, color=R, rarity=RA,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'demon_form', 2 + (1 if u else 0)))
register("DoubleTap",   cost=1, card_type=P, target=NO, color=R, rarity=RA,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'double_tap', 1 + (1 if u else 0)))
register("Juggernaut",  cost=2, card_type=P, target=NO, color=R, rarity=RA,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'juggernaut', 5 + (2 if u else 0)))
register("LimitBreak",  cost=1, card_type=P, target=NO, color=R, rarity=RA, exhausts=True,
         custom=_limit_break_custom)


# ---------------------------------------------------------------------------
# Colorless card custom handlers
# ---------------------------------------------------------------------------

def _blind_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .powers import DebuffKind, apply_debuff
    weak_amt = 2 + (1 if upgraded else 0)
    for ei, enemy in enumerate(state.enemies):
        if enemy.hp > 0 and enemy.name != "Empty":
            apply_debuff(state, enemy.powers, DebuffKind.WEAK, weak_amt, target_index=ei)


def _deep_breath_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    if state.piles.discard:
        state.piles.shuffle_draw_from_discard(state.rng)
    draw_n = 1 + (1 if upgraded else 0)
    state.piles.draw_cards(draw_n, state.rng)


def _impatience_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    has_attack = any(c.spec.card_type == CardType.ATTACK for c in state.piles.hand)
    if not has_attack:
        draw_n = 2 + (1 if upgraded else 0)
        state.piles.draw_cards(draw_n, state.rng)


def _jack_of_all_trades_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .card_pools import colorless_pool
    pool_cards = colorless_pool()
    if not pool_cards:
        return
    n = 1 + (1 if upgraded else 0)
    for _ in range(n):
        card_id = state.rng.choice(pool_cards)
        c = Card(card_id)
        state.piles.spawn_to_hand(c, state)
        from .events import emit as _emit, Event
        _emit(state, Event.CARD_CREATED, "player", card=c)


def _madness_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    playable = [c for c in state.piles.hand if c.spec.playable]
    if playable:
        card = state.rng.choice(playable)
        card.cost_override = 0
        card.cost_override_duration = "combat"


def _hand_of_greed_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    enemy = state.enemies[_ti]
    if enemy.hp <= 0:
        state.gold += 20 + (4 if upgraded else 0)


def _violence_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    n = 2 + (1 if upgraded else 0)
    attacks_in_draw = [c for c in state.piles.draw if c.spec.card_type == CardType.ATTACK]
    for _ in range(min(n, len(attacks_in_draw))):
        if not attacks_in_draw:
            break
        card = state.rng.choice(attacks_in_draw)
        state.piles.draw.remove(card)
        state.piles.hand.append(card)
        attacks_in_draw.remove(card)


def _apotheosis_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    all_cards = (
        list(state.piles.draw) + list(state.piles.hand) +
        list(state.piles.discard) + list(state.piles.exhaust)
    )
    for card in all_cards:
        spec = card.spec
        if spec.card_type not in (CardType.STATUS, CardType.CURSE):
            if not card.upgraded:
                card.card_id = card.card_id.rstrip("+") + "+"


def _discovery_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .card_pools import colorless_pool
    pool_cards = colorless_pool()
    if not pool_cards:
        return
    n = 3 + (1 if upgraded else 0)
    choices = []
    for _ in range(n):
        card_id = state.rng.choice(pool_cards)
        c = Card(card_id, cost_override=0, cost_override_duration="turn")
        choices.append(c)

    def on_choose(s: "CombatState", card: Card) -> None:
        s.piles.spawn_to_hand(card, s)
        from .events import emit as _emit, Event
        _emit(s, Event.CARD_CREATED, "player", card=card)

    state.pending_stack.append(
        ChoiceFrame(choices=choices, kind="discovery", on_choose=on_choose)
    )


def _forethought_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    upgradable = [c for c in state.piles.hand if c.spec.card_type not in (CardType.STATUS, CardType.CURSE)]
    if not upgradable:
        return

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.hand:
            s.piles.hand.remove(card)
        card.cost_override = 0
        card.cost_override_duration = "turn"
        s.piles.place_on_top(card)

    state.pending_stack.append(
        ChoiceFrame(choices=upgradable, kind="forethought", on_choose=on_choose)
    )


def _purity_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    max_exhaust = 3 + (3 if upgraded else 0)
    exhaustable = [c for c in state.piles.hand]
    if not exhaustable:
        return

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.hand:
            s.piles.hand.remove(card)
        s.piles.move_to_exhaust(card)
        from .events import Event, emit as _emit
        _emit(s, Event.CARD_EXHAUSTED, "player", card=card)
        # Allow choosing more if limit not reached
        remaining = [c for c in s.piles.hand if c in exhaustable]
        if remaining and max_exhaust > 1:
            pass  # simplified: one-shot for now

    state.pending_stack.append(
        ChoiceFrame(choices=exhaustable, kind="purity", on_choose=on_choose)
    )


def _secret_technique_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    skills_in_draw = [c for c in state.piles.draw if c.spec.card_type == CardType.SKILL]
    if not skills_in_draw:
        return

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.draw:
            s.piles.draw.remove(card)
        s.piles.hand.append(card)

    state.pending_stack.append(
        ChoiceFrame(choices=skills_in_draw, kind="secrettechnique", on_choose=on_choose)
    )


def _secret_weapon_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    attacks_in_draw = [c for c in state.piles.draw if c.spec.card_type == CardType.ATTACK]
    if not attacks_in_draw:
        return

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.draw:
            s.piles.draw.remove(card)
        s.piles.hand.append(card)

    state.pending_stack.append(
        ChoiceFrame(choices=attacks_in_draw, kind="secretweapon", on_choose=on_choose)
    )


def _thinking_ahead_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    draw_n = 2 + (1 if upgraded else 0)
    state.piles.draw_cards(draw_n, state.rng)
    hand_cards = list(state.piles.hand)
    if not hand_cards:
        return

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.hand:
            s.piles.hand.remove(card)
        s.piles.place_on_top(card)

    state.pending_stack.append(
        ChoiceFrame(choices=hand_cards, kind="thinkingahead", on_choose=on_choose)
    )


def _dark_shackles_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .powers import DebuffKind, apply_debuff
    strength_loss = 9 + (3 if upgraded else 0)
    enemy = state.enemies[_ti]
    apply_debuff(state, enemy.powers, DebuffKind.STRENGTH_DOWN_THIS_TURN, strength_loss, target_index=_ti)


def _enlightenment_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    for card in state.piles.hand:
        if card.spec.cost > 0 and card.cost_override is None:
            card.cost_override = 0
            card.cost_override_duration = "turn"


def _panacea_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    state.player_powers.artifact += 1 + (1 if upgraded else 0)


def _panic_button_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    state.player_powers.no_card_block_turns += 2 + (1 if upgraded else 0)
    state.energy += 2


def _mind_blast_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int) -> None:
    from .powers import calc_damage, apply_damage
    dmg = len(state.piles.draw)
    enemy = state.enemies[_ti]
    raw = calc_damage(dmg, state.player_powers, enemy.powers)
    nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block = nb
    enemy.hp = nhp


def _chrysalis_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .card_pools import pool, colorless_pool
    from .cards import CardColor
    all_skills = pool(CardColor.RED, Rarity.UNCOMMON) + pool(CardColor.RED, Rarity.RARE)
    if not all_skills:
        return
    n = 3 + (1 if upgraded else 0)
    for _ in range(n):
        card_id = state.rng.choice(all_skills)
        c = Card(card_id, cost_override=0, cost_override_duration="combat")
        state.piles.spawn_shuffled_into_draw(c, state, state.rng)
        from .events import emit as _emit, Event
        _emit(state, Event.CARD_CREATED, "player", card=c)


def _metamorphosis_custom(state: "CombatState", _hi: int, _ti: int, upgraded: int) -> None:
    from .card_pools import pool
    from .cards import CardColor
    all_attacks = pool(CardColor.RED, Rarity.COMMON) + pool(CardColor.RED, Rarity.UNCOMMON) + pool(CardColor.RED, Rarity.RARE)
    if not all_attacks:
        return
    n = 3 + (1 if upgraded else 0)
    for _ in range(n):
        card_id = state.rng.choice(all_attacks)
        c = Card(card_id, cost_override=0, cost_override_duration="combat")
        state.piles.spawn_shuffled_into_draw(c, state, state.rng)
        from .events import emit as _emit, Event
        _emit(state, Event.CARD_CREATED, "player", card=c)


def _transmutation_custom(state: "CombatState", _hi: int, _ti: int, _upgraded: int, x_energy: int = 0) -> None:
    from .card_pools import colorless_pool
    pool_cards = colorless_pool()
    if not pool_cards:
        return
    n = x_energy
    for _ in range(n):
        card_id = state.rng.choice(pool_cards)
        c = Card(card_id, cost_override=0, cost_override_duration="turn")
        state.piles.spawn_to_hand(c, state)
        from .events import emit as _emit, Event
        _emit(state, Event.CARD_CREATED, "player", card=c)


# ---------------------------------------------------------------------------
# Colorless card registrations
# ---------------------------------------------------------------------------

# --- Colorless Uncommon ---

# Bandage Up: Heal 4(6) HP, Exhaust
register("BandageUp", cost=0, card_type=S, target=NO, color=CL, rarity=U, exhausts=True,
         heal=4, upgrade={"heal": 2})

# Blind: Apply 2(3) Weak to ALL enemies
register("Blind", cost=0, card_type=S, target=AE, color=CL, rarity=U,
         custom=_blind_custom)

# Dark Shackles: Enemy loses 9(12) Strength this turn
register("DarkShackles", cost=0, card_type=S, target=SE, color=CL, rarity=U, exhausts=True,
         custom=_dark_shackles_custom)

# Deep Breath: Shuffle your discard pile into your draw pile. Draw 1(2)
register("DeepBreath", cost=0, card_type=S, target=NO, color=CL, rarity=U,
         custom=_deep_breath_custom)

# Discovery: Choose 1 of 3(4) random colorless cards. Costs 0 this turn. Exhaust.
register("Discovery", cost=1, card_type=S, target=NO, color=CL, rarity=U, exhausts=True,
         custom=_discovery_custom, upgrade={"cost": -1})

# Enlightenment: Reduce the cost of cards in your hand to 0 this turn
register("Enlightenment", cost=1, card_type=S, target=NO, color=CL, rarity=U,
         custom=_enlightenment_custom, upgrade={"cost": -1})

# Finesse: Gain 2(4) Block. Draw 1 card
register("Finesse", cost=0, card_type=S, target=NO, color=CL, rarity=U,
         block=2, draw=1, upgrade={"block": 2})

# Flash of Steel: Deal 3(6) damage. Draw 1 card
register("FlashOfSteel", cost=0, card_type=A, target=SE, color=CL, rarity=U,
         attack=3, draw=1, upgrade={"attack": 3})

# Forethought: Place a card from your hand on top of your draw pile. It costs 0 this turn
register("Forethought", cost=0, card_type=S, target=NO, color=CL, rarity=U,
         custom=_forethought_custom)

# Good Instincts: Gain 6(9) Block
register("GoodInstincts", cost=0, card_type=S, target=NO, color=CL, rarity=U,
         block=6, upgrade={"block": 3})

# Impatience: If you have no Attacks in your hand, draw 2(3) cards
register("Impatience", cost=0, card_type=S, target=NO, color=CL, rarity=U,
         custom=_impatience_custom)

# Jack of All Trades: Add 1(2) random colorless cards to your hand. Exhaust
register("JackOfAllTrades", cost=0, card_type=S, target=NO, color=CL, rarity=U, exhausts=True,
         custom=_jack_of_all_trades_custom)

# Madness: A random card in your hand costs 0 for the rest of this combat
register("Madness", cost=0, card_type=S, target=NO, color=CL, rarity=U, exhausts=True,
         custom=_madness_custom)

# Panacea: Gain 1(2) Artifact. Exhaust
register("Panacea", cost=0, card_type=S, target=NO, color=CL, rarity=U, exhausts=True,
         custom=_panacea_custom)

# Panic Button: Gain 2(3) Energy. You cannot gain Block from cards this turn or next turn. Exhaust
register("PanicButton", cost=0, card_type=S, target=NO, color=CL, rarity=U, exhausts=True,
         custom=_panic_button_custom)

# Purity: Exhaust up to 3(6) cards from your hand
register("Purity", cost=0, card_type=S, target=NO, color=CL, rarity=U, exhausts=True,
         custom=_purity_custom)

# Swift Strike: Deal 7(10) damage
register("SwiftStrike", cost=0, card_type=A, target=SE, color=CL, rarity=U,
         attack=7, upgrade={"attack": 3})

# Trip: Apply 2(3) Vulnerable
register("Trip", cost=0, card_type=S, target=SE, color=CL, rarity=U,
         vulnerable=2, upgrade={"vulnerable": 1})


# --- Colorless Rare ---

# Apotheosis: Upgrade ALL of your cards for the rest of the combat. Exhaust.
register("Apotheosis", cost=1, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         custom=_apotheosis_custom, upgrade={"cost": -1})

# Chrysalis: Shuffle 3(4) random Skills into your draw pile. They cost 0 this combat. Exhaust.
register("Chrysalis", cost=1, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         custom=_chrysalis_custom, upgrade={"cost": -1})

# Dramatic Entrance: Innate. Deal 8(12) damage to ALL enemies. Exhaust.
register("DramaticEntrance", cost=0, card_type=A, target=AE, color=CL, rarity=RA, exhausts=True,
         innate=True, attack=8, upgrade={"attack": 4})

# Hand of Greed: Deal 20(25) damage. If Fatal, gain 20(24) Gold
register("HandOfGreed", cost=2, card_type=A, target=SE, color=CL, rarity=RA,
         attack=20, upgrade={"attack": 5}, custom=_hand_of_greed_custom)

# Magnetism: At the start of each turn, add a random colorless card to your hand
register("Magnetism", cost=1, card_type=P, target=NO, color=CL, rarity=RA,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'magnetism', 1))

# Master of Strategy: Draw 3(4) cards. Exhaust.
register("MasterOfStrategy", cost=0, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         draw=3, upgrade={"draw": 1})

# Mayhem: At the start of each turn, play the top card of your draw pile
register("Mayhem", cost=1, card_type=P, target=NO, color=CL, rarity=RA,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'mayhem', 1))

# Metamorphosis: Shuffle 3(4) random Attacks into your draw pile. They cost 0 this combat. Exhaust.
register("Metamorphosis", cost=1, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         custom=_metamorphosis_custom, upgrade={"cost": -1})

# Mind Blast: Innate. Deal damage equal to the number of cards in your draw pile
register("MindBlast", cost=2, card_type=A, target=SE, color=CL, rarity=RA, innate=True,
         custom=_mind_blast_custom, upgrade={"cost": -1})

# Panache: Every 5th card you play each turn deals 10(14) damage to ALL enemies
register("Panache", cost=0, card_type=P, target=NO, color=CL, rarity=RA,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'panache_damage', 10 + (4 if u else 0)))

# Sadistic Nature: Whenever an enemy receives a debuff, deal 5(7) damage to it
register("SadisticNature", cost=0, card_type=P, target=NO, color=CL, rarity=RA,
         custom=lambda s, _h, _t, u: setattr(s.player_powers, 'sadistic_nature', 5 + (2 if u else 0)))

# Secret Technique: Choose a Skill from your draw pile and place it into your hand. Exhaust.
register("SecretTechnique", cost=0, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         custom=_secret_technique_custom)

# Secret Weapon: Choose an Attack from your draw pile and place it into your hand. Exhaust.
register("SecretWeapon", cost=0, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         custom=_secret_weapon_custom)

# The Bomb: At the end of 3 turns, deal 40(50) damage to ALL enemies
register("TheBomb", cost=2, card_type=S, target=NO, color=CL, rarity=RA,
         custom=lambda s, _h, _t, u: s.player_powers.bomb_fuses.append((3, 40 + (10 if u else 0))))

# Thinking Ahead: Draw 2(3) cards. Place a card from your hand on top of your draw pile. Exhaust.
register("ThinkingAhead", cost=1, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         custom=_thinking_ahead_custom, upgrade={"cost": -1})

# Transmutation: Add X random colorless cards to your hand that cost 0 this turn. Exhaust.
register("Transmutation", cost=-1, card_type=S, target=NO, color=CL, rarity=RA, x_cost=True, exhausts=True,
         custom=_transmutation_custom)

# Violence: Put 2(3) random Attacks from your draw pile into your hand. Exhaust.
register("Violence", cost=0, card_type=S, target=NO, color=CL, rarity=RA, exhausts=True,
         custom=_violence_custom)
