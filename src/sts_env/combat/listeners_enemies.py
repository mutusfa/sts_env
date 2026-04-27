"""Enemy-triggered event listeners.

Each handler corresponds to an enemy ability that subscribes to an event.
Some are name-based (slimes, Lagavulin), others are condition-based
(Curl Up, Spore Cloud).

Subscription table: ``ENEMY_SUBSCRIPTIONS[enemy_name] = [(Event, handler_name)]``
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .events import Event, register_listener

if TYPE_CHECKING:
    from .state import CombatState
    from .events import Owner


# ---------------------------------------------------------------------------
# HP_LOSS handlers (owner = enemy index)
# ---------------------------------------------------------------------------

_SPLIT_NAMES = frozenset({"AcidSlimeL", "SpikeSlimeL", "SlimeBoss"})


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


def _lagavulin_wake(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    hp_before = payload.get("hp_before", enemy.hp)
    if enemy.powers.asleep and enemy.hp < hp_before:
        enemy.powers.asleep = False
        enemy.powers.enemy_metallicize = 0


def _curl_up(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    hp_before = payload.get("hp_before", enemy.hp)
    if enemy.powers.curl_up > 0 and enemy.hp < hp_before:
        enemy.block += enemy.powers.curl_up
        enemy.powers.curl_up = 0


register_listener(Event.HP_LOSS, "slime_split", _slime_split)
register_listener(Event.HP_LOSS, "lagavulin_wake", _lagavulin_wake)
register_listener(Event.HP_LOSS, "curl_up", _curl_up)


# ---------------------------------------------------------------------------
# DEATH handlers (owner = enemy index)
# ---------------------------------------------------------------------------

def _spore_cloud(state: CombatState, owner: Owner, payload: dict) -> None:
    if not isinstance(owner, int):
        return
    enemy = state.enemies[owner]
    hp_before = payload.get("hp_before", 1)
    if hp_before > 0 and enemy.hp <= 0 and enemy.powers.spore_cloud > 0:
        state.player_powers.vulnerable += enemy.powers.spore_cloud
        enemy.powers.spore_cloud = 0


register_listener(Event.DEATH, "spore_cloud", _spore_cloud)


# ---------------------------------------------------------------------------
# CARD_PLAYED handlers (owner = "player" for Gremlin Nob)
# ---------------------------------------------------------------------------

def _gremlin_nob_skill(state: CombatState, owner: Owner, payload: dict) -> None:
    from .cards import CardType
    card_spec = payload.get("card_spec")
    if card_spec is None or card_spec.card_type != CardType.SKILL:
        return
    for enemy in state.enemies:
        if enemy.alive and enemy.skill_played_str > 0:
            enemy.powers.strength += enemy.skill_played_str


register_listener(Event.CARD_PLAYED, "gremlin_nob_skill", _gremlin_nob_skill)


# ---------------------------------------------------------------------------
# Subscription tables
# ---------------------------------------------------------------------------

# Name-based subscriptions (subscribe in Combat.reset for matching enemies)
ENEMY_SUBSCRIPTIONS: dict[str, list[tuple[Event, str]]] = {
    "AcidSlimeL": [(Event.HP_LOSS, "slime_split")],
    "SpikeSlimeL": [(Event.HP_LOSS, "slime_split")],
    "SlimeBoss": [(Event.HP_LOSS, "slime_split")],
    "Lagavulin": [(Event.HP_LOSS, "lagavulin_wake")],
    "GremlinNob": [(Event.CARD_PLAYED, "gremlin_nob_skill")],
}

# Condition-based subscriptions (subscribe in Combat.reset if power > 0)
# key is checked against enemy powers; value is (event, handler_name, owner_override)
# owner_override: None means use enemy index; "player" means subscribe to player events
ENEMY_CONDITION_SUBSCRIPTIONS: list[tuple[str, Event, str, str | None]] = [
    # (power_attr, event, handler_name, owner_override)
    ("curl_up", Event.HP_LOSS, "curl_up", None),       # owner = enemy index
    ("spore_cloud", Event.DEATH, "spore_cloud", None),  # owner = enemy index
    ("ritual", Event.TURN_END, "ritual", None),          # owner = enemy index
    ("vulnerable", Event.TURN_START, "tick_vulnerable", None),
    ("weak", Event.TURN_START, "tick_weak", None),
    ("frail", Event.TURN_START, "tick_frail", None),
]
