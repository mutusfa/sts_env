"""Enemy-triggered event listeners.

Each handler corresponds to an enemy ability that subscribes to an event.
Some are name-based (slimes, Lagavulin), others are condition-based
(Curl Up, Spore Cloud).

Subscription table: ``ENEMY_SUBSCRIPTIONS[enemy_name] = [(Event, handler_name)]``
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .events import Event, listener

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# Subscription tables
# ---------------------------------------------------------------------------

# Name-based subscriptions (subscribe in Combat.reset for matching enemies)
ENEMY_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {}


# ---------------------------------------------------------------------------
# HP_LOSS handlers (owner = enemy index)
# ---------------------------------------------------------------------------

_SPLIT_NAMES = frozenset({"AcidSlimeL", "SpikeSlimeL", "SlimeBoss"})


@listener(Event.HP_LOSS, "slime_split", subscriptions=[
    (ENEMY_SUBSCRIPTIONS, "AcidSlimeL"),
    (ENEMY_SUBSCRIPTIONS, "SpikeSlimeL"),
    (ENEMY_SUBSCRIPTIONS, "SlimeBoss"),
])
def _slime_split(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    hp_before = payload.get("hp_before", enemy.hp)
    if (
        enemy.name in _SPLIT_NAMES
        and not enemy.pending_split
        and enemy.hp > 0
        and enemy.hp <= enemy.max_hp // 2
        and hp_before > enemy.max_hp // 2
    ):
        enemy.pending_split = True


@listener(Event.HP_LOSS, "lagavulin_wake", subscriptions=[(ENEMY_SUBSCRIPTIONS, "Lagavulin")])
def _lagavulin_wake(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    hp_before = payload.get("hp_before", enemy.hp)
    if enemy.powers.asleep and enemy.hp < hp_before:
        enemy.powers.asleep = False
        enemy.powers.enemy_metallicize = 0


@listener(Event.HP_LOSS, "guardian_mode_shift", subscriptions=[(ENEMY_SUBSCRIPTIONS, "Guardian")])
def _guardian_mode_shift(state: CombatState, owner: Owner, payload: dict) -> None:
    """Decrement Guardian's Mode Shift by damage dealt. Trigger defensive mode when depleted."""
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    if enemy.powers.mode_shift <= 0:
        return  # already triggered or not active
    hp_before = payload.get("hp_before", enemy.hp)
    damage_dealt = hp_before - enemy.hp
    if damage_dealt <= 0:
        return
    enemy.powers.mode_shift -= damage_dealt
    if enemy.powers.mode_shift <= 0:
        enemy.powers.mode_shift = 0
        enemy.pending_mode_shift = True
        enemy.block += 20  # gain 20 block immediately on transition


@listener(Event.ATTACK_DAMAGED, "curl_up", subscriptions=[])
def _curl_up(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    hp_before = payload.get("hp_before", enemy.hp)
    if enemy.powers.curl_up > 0 and enemy.hp < hp_before:
        enemy.block += enemy.powers.curl_up
        enemy.powers.curl_up = 0


# ---------------------------------------------------------------------------
# DEATH handlers (owner = enemy index)
# ---------------------------------------------------------------------------

@listener(Event.DEATH, "spore_cloud", subscriptions=[])
def _spore_cloud(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    hp_before = payload.get("hp_before", 1)
    if hp_before > 0 and enemy.hp <= 0 and enemy.powers.spore_cloud > 0:
        state.player_powers.vulnerable += enemy.powers.spore_cloud
        enemy.powers.spore_cloud = 0


@listener(Event.DEATH, "refund_stolen_gold", subscriptions=[])
def _refund_stolen_gold(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    if enemy.gold_stolen > 0:
        state.gold += enemy.gold_stolen
        enemy.gold_stolen = 0


# ---------------------------------------------------------------------------
# CARD_PLAYED handlers (owner = "player" for Gremlin Nob)
# ---------------------------------------------------------------------------

@listener(Event.CARD_PLAYED, "gremlin_nob_skill", subscriptions=[(ENEMY_SUBSCRIPTIONS, "GremlinNob")])
def _gremlin_nob_skill(state: CombatState, owner: Owner, payload: dict) -> None:
    from .cards import CardType
    card = payload.get("card")
    if card is None or card.spec.card_type != CardType.SKILL:
        return
    for enemy in state.enemies:
        if enemy.alive and enemy.skill_played_str > 0:
            enemy.powers.strength += enemy.skill_played_str


@listener(Event.CARD_PLAYED, "sharp_hide", subscriptions=[])
def _sharp_hide(state: CombatState, owner: Owner, payload: dict) -> None:
    """When the player plays an Attack, enemies with Sharp Hide deal damage back."""
    from .cards import CardType
    from .powers import apply_damage
    card = payload.get("card")
    if card is None or card.spec.card_type != CardType.ATTACK:
        return
    for enemy in state.enemies:
        if enemy.alive and enemy.powers.sharp_hide > 0:
            hp_before = state.player_hp
            nb, nhp = apply_damage(enemy.powers.sharp_hide, state.player_block, state.player_hp)
            state.player_block = nb
            state.player_hp = nhp
            if nhp < hp_before:
                from .events import Event, emit as _emit
                _emit(state, Event.HP_LOSS, "player", hp_before=hp_before)


# ---------------------------------------------------------------------------
# Condition-based subscriptions (subscribe in Combat.reset if power > 0)
# key is checked against enemy powers; value is (event, handler_name, owner_override)
# owner_override: None means use enemy index; "player" means subscribe to player events
ENEMY_CONDITION_SUBSCRIPTIONS: list[tuple[str, Event, str, str | None]] = [
    # (power_attr, event, handler_name, owner_override)
    ("curl_up", Event.ATTACK_DAMAGED, "curl_up", None),  # only card-attack damage
    ("spore_cloud", Event.DEATH, "spore_cloud", None),    # owner = enemy index
    ("ritual", Event.TURN_END, "ritual", None),          # owner = enemy index
    ("vulnerable", Event.TURN_START, "tick_vulnerable", None),
    ("weak", Event.TURN_START, "tick_weak", None),
    ("frail", Event.TURN_START, "tick_frail", None),
    # Always reset per-turn strength loss for enemies
    ("strength_loss_this_turn", Event.TURN_END, "reset_strength_loss_this_turn", None),
    # Refund stolen gold when Looter/Mugger is killed
    ("gold_stolen", Event.DEATH, "refund_stolen_gold", None),
    # Guardian: Sharp Hide deals damage when player plays an Attack
    ("sharp_hide", Event.CARD_PLAYED, "sharp_hide", "player"),
]
