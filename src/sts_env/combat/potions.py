"""Potion definitions aligned with sts_lightspeed.

Registry pattern mirrors cards.py. All Ironclad-pool potions are registered here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .card import Card
from .cards import (
    CardType,
    TargetType,
    _SPECS as _CARD_SPECS,
    _resolve_card_effects,
    apply_upgrade,
    get_spec as get_card_spec,
    is_upgradable,
)
from .pending import ChoiceFrame, ThunkFrame
from .powers import DebuffKind, Powers, apply_damage, apply_debuff, calc_damage

if TYPE_CHECKING:
    from .state import CombatState


@dataclass(frozen=True)
class PotionSpec:
    potion_id: str
    target: TargetType  # SINGLE_ENEMY, ALL_ENEMIES, or NONE (self-targeting)
    passive: bool = False


PotionHandler = Callable[["CombatState", int], None]  # (state, target_index)

_SPECS: dict[str, PotionSpec] = {}
_HANDLERS: dict[str, PotionHandler] = {}


def potion(potion_id: str, target: TargetType, passive: bool = False) -> Callable[[PotionHandler], PotionHandler]:
    def decorator(fn: PotionHandler) -> PotionHandler:
        _SPECS[potion_id] = PotionSpec(potion_id, target, passive=passive)
        _HANDLERS[potion_id] = fn
        return fn
    return decorator


def get_spec(potion_id: str) -> PotionSpec:
    try:
        return _SPECS[potion_id]
    except KeyError:
        raise KeyError(f"Unknown potion: {potion_id!r}") from None


def _potion_scale(state: "CombatState", base: int) -> int:
    """Double potion effects when Sacred Bark is held."""
    if "SacredBark" in state.relics:
        return base * 2
    return base


def use_potion(state: "CombatState", potion_index: int, target_index: int) -> None:
    """Execute a potion's effect and remove it from the slot list."""
    potion_id = state.potions[potion_index]
    spec = _SPECS[potion_id]
    if spec.passive:
        raise ValueError(f"Passive potion {potion_id!r} cannot be actively used")
    _HANDLERS[potion_id](state, target_index)
    state.potions.pop(potion_index)

    from .events import emit, Event
    emit(state, Event.POTION_USED, "player", potion_id=potion_id)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_potion_choice(
    state: "CombatState",
    pool_or_type: CardType | list[str],
) -> None:
    """Present up to 3 random cards; agent picks one for hand at cost 0."""
    if isinstance(pool_or_type, CardType):
        card_ids = [
            cid for cid, spec in _CARD_SPECS.items()
            if spec.card_type == pool_or_type
        ]
    else:
        card_ids = pool_or_type
    k = min(3, len(card_ids))
    choices = state.rng.sample(card_ids, k)
    cards = [Card(cid, cost_override=0, cost_override_duration="turn") for cid in choices]

    def on_choose(s: "CombatState", card: Card) -> None:
        from .events import emit, Event
        s.piles.hand.append(card)
        emit(s, Event.CARD_CREATED, "player", card=card)

    state.pending_stack.append(
        ChoiceFrame(choices=cards, kind="potion", on_choose=on_choose)
    )


def _play_top_card(state: "CombatState", *, random_target: bool = True) -> None:
    """Play the top card of the draw pile (Distilled Chaos / Mayhem pattern)."""
    if not state.piles.draw:
        if not state.piles.discard:
            return
        state.piles.shuffle_draw_from_discard(state.rng, state=state)
    if not state.piles.draw:
        return

    top_card = state.piles.draw.pop(0)
    top_id = top_card.card_id.rstrip("+")
    top_spec = get_card_spec(top_id)
    if not top_spec.playable:
        state.piles.move_to_discard(top_card)
        return

    if top_spec.target == TargetType.SINGLE_ENEMY:
        alive = [e for e in state.enemies if e.hp > 0 and e.name != "Empty"]
        if alive and random_target:
            ti = state.enemies.index(alive[state.rng.randint(0, len(alive) - 1)])
        elif alive:
            ti = state.enemies.index(alive[0])
        else:
            ti = 0
    else:
        ti = 0

    up = 1 if top_card.upgraded else 0
    _resolve_card_effects(state, top_spec, -1, ti, up, upgrade_count=up)
    if top_spec.exhausts:
        state.piles.move_to_exhaust(top_card)
    else:
        state.piles.move_to_discard(top_card)
    from .events import emit, Event
    emit(state, Event.CARD_PLAYED, "player", card=top_card)
    if top_spec.exhausts:
        emit(state, Event.CARD_EXHAUSTED, "player", card=top_card)


def _upgrade_all_in_hand(state: "CombatState") -> None:
    for card in state.piles.hand:
        if is_upgradable(card.card_id):
            card.card_id = apply_upgrade(card.card_id)


def _exhaust_from_hand(state: "CombatState", count: int) -> None:
    """Exhaust up to *count* player-chosen cards from hand (Elixir / ExhaustMany)."""
    if count <= 0 or not state.piles.hand:
        return

    def push_exhaust_choice(s: "CombatState", remaining: int) -> None:
        if remaining <= 0 or not s.piles.hand:
            return
        choices = list(s.piles.hand)

        def on_choose(cs: "CombatState", card: Card) -> None:
            if card in cs.piles.hand:
                cs.piles.hand.remove(card)
            cs.piles.move_to_exhaust(card)
            from .events import emit, Event
            emit(cs, Event.CARD_EXHAUSTED, "player", card=card)
            push_exhaust_choice(cs, remaining - 1)

        s.pending_stack.append(
            ChoiceFrame(choices=choices, kind="elixir", on_choose=on_choose)
        )

    push_exhaust_choice(state, count)


# ---------------------------------------------------------------------------
# Damage potions
# ---------------------------------------------------------------------------

@potion("FirePotion", TargetType.SINGLE_ENEMY)
def _fire_potion(state: "CombatState", ti: int) -> None:
    raw = calc_damage(_potion_scale(state, 20), Powers(), Powers())
    enemy = state.enemies[ti]
    nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
    enemy.block, enemy.hp = nb, nhp


@potion("ExplosivePotion", TargetType.ALL_ENEMIES)
def _explosive_potion(state: "CombatState", _ti: int) -> None:
    raw = calc_damage(_potion_scale(state, 10), Powers(), Powers())
    for enemy in state.enemies:
        if enemy.hp > 0 and enemy.name != "Empty":
            nb, nhp = apply_damage(raw, enemy.block, enemy.hp)
            enemy.block, enemy.hp = nb, nhp


@potion("FearPotion", TargetType.SINGLE_ENEMY)
def _fear_potion(state: "CombatState", ti: int) -> None:
    state.enemies[ti].powers.vulnerable += _potion_scale(state, 3)


@potion("WeakPotion", TargetType.SINGLE_ENEMY)
def _weak_potion(state: "CombatState", ti: int) -> None:
    apply_debuff(
        state,
        state.enemies[ti].powers,
        DebuffKind.WEAK,
        _potion_scale(state, 3),
        target_index=ti,
    )


# ---------------------------------------------------------------------------
# Block / energy / draw
# ---------------------------------------------------------------------------

@potion("BlockPotion", TargetType.NONE)
def _block_potion(state: "CombatState", _ti: int) -> None:
    from .engine import gain_player_block
    gain_player_block(state, _potion_scale(state, 12), source="potion")


@potion("EnergyPotion", TargetType.NONE)
def _energy_potion(state: "CombatState", _ti: int) -> None:
    state.energy += _potion_scale(state, 2)


@potion("SwiftPotion", TargetType.NONE)
def _swift_potion(state: "CombatState", _ti: int) -> None:
    state.piles.draw_cards(_potion_scale(state, 3), state.rng, state=state)


# ---------------------------------------------------------------------------
# Buff potions
# ---------------------------------------------------------------------------

@potion("StrengthPotion", TargetType.NONE)
def _strength_potion(state: "CombatState", _ti: int) -> None:
    state.player_powers.strength += _potion_scale(state, 2)


@potion("SteroidPotion", TargetType.NONE)
def _steroid_potion(state: "CombatState", _ti: int) -> None:
    amt = _potion_scale(state, 5)
    state.player_powers.strength += amt
    apply_debuff(state, state.player_powers, DebuffKind.STRENGTH_DOWN_EOT, amt)


@potion("DexterityPotion", TargetType.NONE)
def _dexterity_potion(state: "CombatState", _ti: int) -> None:
    state.player_powers.dexterity += _potion_scale(state, 2)


@potion("SpeedPotion", TargetType.NONE)
def _speed_potion(state: "CombatState", _ti: int) -> None:
    amt = _potion_scale(state, 5)
    state.player_powers.dexterity += amt
    apply_debuff(state, state.player_powers, DebuffKind.DEXTERITY_DOWN_EOT, amt)


@potion("AncientPotion", TargetType.NONE)
def _ancient_potion(state: "CombatState", _ti: int) -> None:
    state.player_powers.artifact += _potion_scale(state, 1)


@potion("LiquidBronze", TargetType.NONE)
def _liquid_bronze(state: "CombatState", _ti: int) -> None:
    state.player_powers.thorns += _potion_scale(state, 3)


@potion("CultistPotion", TargetType.NONE)
def _cultist_potion(state: "CombatState", _ti: int) -> None:
    state.player_powers.ritual += _potion_scale(state, 1)
    state.player_powers.ritual_just_applied = True


@potion("RegenPotion", TargetType.NONE)
def _regen_potion(state: "CombatState", _ti: int) -> None:
    state.player_powers.regen += _potion_scale(state, 5)


@potion("EssenceOfSteel", TargetType.NONE)
def _essence_of_steel(state: "CombatState", _ti: int) -> None:
    state.player_powers.plated_armor += _potion_scale(state, 4)


@potion("DuplicationPotion", TargetType.NONE)
def _duplication_potion(state: "CombatState", _ti: int) -> None:
    state.player_powers.duplication += _potion_scale(state, 1)


@potion("BlessingOfTheForge", TargetType.NONE)
def _blessing_of_the_forge(state: "CombatState", _ti: int) -> None:
    _upgrade_all_in_hand(state)


# ---------------------------------------------------------------------------
# Ironclad-specific
# ---------------------------------------------------------------------------

@potion("BloodPotion", TargetType.NONE)
def _blood_potion(state: "CombatState", _ti: int) -> None:
    pct = 0.20 if "SacredBark" not in state.relics else 0.40
    heal = math.floor(state.player_max_hp * pct)
    from .healing import heal_player
    heal_player(state, heal)


@potion("HeartOfIron", TargetType.NONE)
def _heart_of_iron(state: "CombatState", _ti: int) -> None:
    state.player_powers.metallicize += _potion_scale(state, 6)


@potion("ElixirPotion", TargetType.NONE)
def _elixir_potion(state: "CombatState", _ti: int) -> None:
    _exhaust_from_hand(state, 10)


@potion("FruitJuice", TargetType.NONE)
def _fruit_juice(state: "CombatState", _ti: int) -> None:
    gain = _potion_scale(state, 5)
    state.player_max_hp += gain
    from .healing import heal_player
    heal_player(state, gain)


@potion("FairyPotion", TargetType.NONE, passive=True)
def _fairy_potion(state: "CombatState", _ti: int) -> None:
    """Passive revive — logic in listeners_potions.py."""
    pass


@potion("SmokeBomb", TargetType.NONE, passive=True)
def _smoke_bomb(state: "CombatState", _ti: int) -> None:
    """Unimplemented escape mechanic (matches C++ todo)."""
    pass


# ---------------------------------------------------------------------------
# Choice / deck manipulation potions
# ---------------------------------------------------------------------------

@potion("AttackPotion", TargetType.NONE)
def _attack_potion(state: "CombatState", _ti: int) -> None:
    _make_potion_choice(state, CardType.ATTACK)


@potion("SkillPotion", TargetType.NONE)
def _skill_potion(state: "CombatState", _ti: int) -> None:
    _make_potion_choice(state, CardType.SKILL)


@potion("PowerPotion", TargetType.NONE)
def _power_potion(state: "CombatState", _ti: int) -> None:
    _make_potion_choice(state, CardType.POWER)


@potion("ColorlessPotion", TargetType.NONE)
def _colorless_potion(state: "CombatState", _ti: int) -> None:
    from .card_pools import colorless_pool
    _make_potion_choice(state, colorless_pool())


def _finish_gamble(state: "CombatState", discarded_count: int) -> None:
    if discarded_count > 0:
        state.piles.draw_cards(discarded_count, state.rng, state=state)


def _push_gamble_choice(state: "CombatState", discarded_count: int = 0) -> None:
    """Let the player discard hand cards one at a time; skip to draw that many."""
    if not state.piles.hand:
        _finish_gamble(state, discarded_count)
        return

    choices = list(state.piles.hand)

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.hand:
            s.piles.hand.remove(card)
        s.piles.move_to_discard(card)
        new_count = discarded_count + 1
        if s.piles.hand:
            _push_gamble_choice(s, new_count)
        else:
            _finish_gamble(s, new_count)

    def on_skip(s: "CombatState") -> None:
        _finish_gamble(s, discarded_count)

    state.pending_stack.append(
        ChoiceFrame(choices=choices, kind="gamble", on_choose=on_choose, on_skip=on_skip)
    )


@potion("GamblersBrew", TargetType.NONE)
def _gamblers_brew(state: "CombatState", _ti: int) -> None:
    _push_gamble_choice(state)


@potion("DistilledChaos", TargetType.NONE)
def _distilled_chaos(state: "CombatState", _ti: int) -> None:
    plays = _potion_scale(state, 3)

    def _run(s: "CombatState") -> None:
        for _ in range(plays):
            _play_top_card(s)

    state.pending_stack.append(
        ThunkFrame(run=_run, label="distilled-chaos")
    )


@potion("LiquidMemories", TargetType.NONE)
def _liquid_memories(state: "CombatState", _ti: int) -> None:
    pick = _potion_scale(state, 1)
    if not state.piles.discard:
        return
    choices = list(state.piles.discard)

    def on_choose(s: "CombatState", card: Card) -> None:
        if card in s.piles.discard:
            s.piles.discard.remove(card)
        card.cost_override = 0
        card.cost_override_duration = "turn"
        s.piles.hand.append(card)
        from .events import emit, Event
        emit(s, Event.CARD_CREATED, "player", card=card)

    for _ in range(pick):
        state.pending_stack.append(
            ChoiceFrame(choices=choices, kind="liquid-memories", on_choose=on_choose)
        )


@potion("SneckoOil", TargetType.NONE)
def _snecko_oil(state: "CombatState", _ti: int) -> None:
    state.piles.draw_cards(_potion_scale(state, 5), state.rng, state=state)
    for card in state.piles.hand:
        card.cost_override = state.rng.randint(0, 3)
        card.cost_override_duration = "combat"


@potion("EntropicBrew", TargetType.NONE)
def _entropic_brew(state: "CombatState", _ti: int) -> None:
    from .potion_pools import roll_random_potion
    slots = state.max_potion_slots - len(state.potions)
    for _ in range(slots):
        if len(state.potions) >= state.max_potion_slots:
            break
        state.potions.append(roll_random_potion(state.rng, limited=True))
