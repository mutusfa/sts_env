"""Run orchestrator for Act 1 — chains rooms into a full run.

Defines the seam between the game engine and an external agent:

* :class:`RunAgentProtocol` — duck-typed interface an agent must satisfy.
* :class:`FloorObserver` — optional hook for per-floor observability.
* :func:`run_act1` — the top-level entry point.

All game-state mutations (relic effects, reward rolling, rest execution) live
here. The agent is only asked to *make decisions*; it never touches state
directly.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator, Protocol, runtime_checkable

from .character import Character
from .map import generate_act1_map, get_encounter_for_room, RoomType
from .rooms import RestChoice, rest_heal, rest_upgrade, _best_upgrade_target
from .events import random_act1_event, resolve_event
from .shop import generate_shop
from .treasure import open_treasure
from .neow import roll_neow_options, apply_neow
from .rewards import Room as _RewardRoom, roll_combat_reward_offer, roll_elite_relic, roll_boss_relic_choices
from .encounter_queue import EncounterQueue
from . import relics as relics_mod
from . import builder
from ..combat import Combat
from ..combat.rng import RNG

if TYPE_CHECKING:
    from .events import EventSpec
    from .map import StSMap
    from .neow import NeowChoice, NeowOption
    from .shop import ShopInventory

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """Result of a completed (or failed) Act 1 run."""

    victory: bool
    floors_cleared: int
    total_floors: int
    final_hp: int
    max_hp: int
    damage_taken_total: int
    max_hp_gained_total: int
    damage_per_floor: list[int] = field(default_factory=list)
    encounter_types: list[str] = field(default_factory=list)
    cards_added: list[str] = field(default_factory=list)
    potions_gained: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class RunAgentProtocol(Protocol):
    """Duck-typed interface satisfied by any run-layer agent.

    The orchestrator calls these methods to request decisions; the agent never
    mutates game state directly.
    """

    def run_battle(self, combat: Combat) -> int:
        """Run a combat to completion and return damage taken."""
        ...

    def pick_neow(self, options: list[NeowOption]) -> NeowChoice:
        """Choose a Neow blessing from the given options."""
        ...

    def plan_route(
        self,
        sts_map: StSMap,
        character: Character,
        seed: int,
    ) -> list[tuple[int, int]]:
        """Return a full path through the map as (floor, x) pairs."""
        ...

    def pick_card(
        self,
        character: Character,
        card_choices: list[str],
        upcoming_encounters: list[tuple[str, str]],
        seed: int,
        **kwargs: Any,
    ) -> str | None:
        """Choose a card from the offered list, or None to skip."""
        ...

    def pick_rest_choice(self, character: Character) -> RestChoice:
        """Choose REST or UPGRADE at a rest site."""
        ...

    def pick_event_choice(self, event: EventSpec, character: Character) -> int:
        """Choose an event branch by index."""
        ...

    def shop(self, inventory: ShopInventory, character: Character) -> None:
        """Interact with a shop (may mutate character.gold / deck / etc.)."""
        ...

    def pick_boss_relic(
        self,
        character: Character,
        choices: list[str],
    ) -> str | None:
        """Choose a boss relic from the offered list, or None to skip."""
        ...


# ---------------------------------------------------------------------------
# Observer protocol
# ---------------------------------------------------------------------------

class FloorObserver(Protocol):
    """Optional per-floor observability hook.

    ``floor_scope`` is a context manager that wraps each floor iteration.
    It receives an ``attrs`` dict (yielded empty) that the orchestrator fills
    with outcome data before exiting; observers can read it in their
    ``__exit__`` / ``finally`` block.

    Example (MLflow)::

        class MlflowObserver:
            @contextmanager
            def floor_scope(self, floor, room_type, character):
                with mlflow.start_span(name=f"floor_{floor}_{room_type}") as span:
                    span.set_attributes({"floor": floor, "hp_before": character.player_hp})
                    attrs = {}
                    yield attrs
                    span.set_attributes(attrs)
    """

    @contextmanager
    def floor_scope(
        self,
        floor: int,
        room_type: str,
        character: Character,
    ) -> Iterator[dict[str, Any]]:
        """Context manager wrapping a single floor. Yields a mutable attrs dict."""
        ...


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_act1(
    seed: int,
    agent: RunAgentProtocol,
    *,
    use_map: bool = True,
    observer: FloorObserver | None = None,
) -> RunResult:
    """Run a full Act 1 scenario.

    Parameters
    ----------
    seed:
        Master seed for all RNG.
    agent:
        Object satisfying :class:`RunAgentProtocol` — provides both battle
        execution and all strategic decisions.
    use_map:
        If True (default), generate a branching 15-floor map.
        If False, use the old fixed 8-floor linear encounter list.
    observer:
        Optional :class:`FloorObserver` for per-floor instrumentation
        (e.g. MLflow spans). Defaults to a no-op.

    Returns
    -------
    :class:`RunResult`
    """
    character = Character.ironclad()
    reward_rng = RNG(seed ^ 0xBEEF)
    neow_rng = RNG(seed ^ 0xCA7)

    neow_options = roll_neow_options(neow_rng)
    neow_pick = agent.pick_neow(neow_options)
    neow_desc = apply_neow(neow_pick, character, neow_rng)
    log.info("NEOW: %s", neow_desc)

    if use_map:
        return _run_map(seed, agent, character, reward_rng, observer=observer)
    else:
        return _run_linear(seed, agent, character, reward_rng, observer=observer)


# ---------------------------------------------------------------------------
# Map-based loop
# ---------------------------------------------------------------------------

def _run_map(
    seed: int,
    agent: RunAgentProtocol,
    character: Character,
    reward_rng: RNG,
    *,
    observer: FloorObserver | None,
) -> RunResult:
    sts_map = generate_act1_map(seed)
    encounter_rng = RNG(seed ^ 0xCAFE)
    encounter_queue = EncounterQueue(encounter_rng)

    path = agent.plan_route(sts_map, character, seed)
    total_floors = len(path)

    result = RunResult(
        victory=False,
        floors_cleared=0,
        total_floors=total_floors,
        final_hp=character.player_hp,
        max_hp=character.player_max_hp,
        damage_taken_total=0,
        max_hp_gained_total=0,
    )

    for step_idx, (floor_num, x_pos) in enumerate(path):
        node = sts_map.get_node(floor_num, x_pos)
        if node is None:
            log.warning("Path step %d: no node at (%d, %d), skipping", step_idx, floor_num, x_pos)
            continue

        character.floor = floor_num + 1
        room_type = node.room_type
        room_type_str = room_type.name.lower()

        died = False
        with _floor_scope(observer, floor_num + 1, room_type_str, character) as attrs:

            if room_type == RoomType.REST:
                rest_result = _execute_rest_choice(agent, character)
                if rest_result.choice == RestChoice.REST:
                    log.info("FLOOR %d REST: healed %d HP (hp=%d/%d)",
                             floor_num + 1, rest_result.hp_healed,
                             character.player_hp, character.player_max_hp)
                    attrs.update({"rest_choice": "rest", "hp_healed": rest_result.hp_healed})
                else:
                    log.info("FLOOR %d REST: upgraded %s (hp=%d/%d)",
                             floor_num + 1, rest_result.card_upgraded,
                             character.player_hp, character.player_max_hp)
                    attrs.update({"rest_choice": "upgrade", "card_upgraded": str(rest_result.card_upgraded)})
                result.encounter_types.append("rest")
                result.damage_per_floor.append(0)
                result.floors_cleared += 1
                result.final_hp = character.player_hp
                result.max_hp = character.player_max_hp

            elif room_type == RoomType.EVENT:
                event = random_act1_event(encounter_rng, character.seen_events)
                character.seen_events.append(event.event_id)
                log.info("FLOOR %d EVENT: %s", floor_num + 1, event.event_id)
                choice_idx = agent.pick_event_choice(event, character)
                desc = resolve_event(event.event_id, choice_idx, character, encounter_rng)
                log.info("  Event result: %s", desc)
                attrs.update({
                    "event_id": event.event_id,
                    "choice_idx": choice_idx,
                    "event_result": str(desc),
                })
                result.encounter_types.append("event")
                result.damage_per_floor.append(0)
                result.floors_cleared += 1

            elif room_type == RoomType.SHOP:
                log.info("FLOOR %d SHOP", floor_num + 1)
                shop_inv = generate_shop(encounter_rng, character)
                agent.shop(shop_inv, character)
                result.encounter_types.append("shop")
                result.damage_per_floor.append(0)
                result.floors_cleared += 1

            elif room_type == RoomType.TREASURE:
                log.info("FLOOR %d TREASURE", floor_num + 1)
                tres = open_treasure(character, encounter_rng)
                log.info("  Found %d gold and %s", tres.gold_found, tres.relic_found)
                attrs.update({
                    "gold_found": tres.gold_found,
                    "relic_found": tres.relic_found,
                })
                result.encounter_types.append("treasure")
                result.damage_per_floor.append(0)
                result.floors_cleared += 1

            else:
                # Combat rooms: MONSTER / ELITE / BOSS
                encounter_id = get_encounter_for_room(room_type, encounter_queue)
                if encounter_id is None:
                    log.warning("FLOOR %d %s: no encounter assigned, skipping",
                                floor_num + 1, room_type.name)
                else:
                    encounter_type = room_type_str
                    result.encounter_types.append(encounter_type)

                    combat_seed = seed * 1000 + floor_num
                    combat = builder.build_combat(
                        encounter_type, encounter_id, combat_seed, character=character,
                    )

                    damage = agent.run_battle(combat)
                    result.damage_per_floor.append(damage)
                    result.damage_taken_total += damage
                    result.max_hp_gained_total += combat.max_hp_gained

                    obs = combat.observe()
                    attrs.update({
                        "encounter_id": encounter_id,
                        "damage_taken": damage,
                        "max_hp_gained": combat.max_hp_gained,
                        "survived": not obs.player_dead,
                        "turns": obs.turn,
                    })

                    if obs.player_dead:
                        log.info("FLOOR %d (%s/%s): DIED (damage=%d)",
                                 floor_num + 1, encounter_type, encounter_id, damage)
                        character.player_hp = 0
                        result.final_hp = 0
                        died = True
                    else:
                        character.player_hp = obs.player_hp
                        character.player_max_hp = obs.player_max_hp
                        character.potions = list(combat._state.potions)
                        builder.sync_combat_counters(character, combat)
                        relics_mod.on_combat_end(character)
                        result.final_hp = character.player_hp
                        result.max_hp = character.player_max_hp

                        log.info("FLOOR %d (%s/%s): WON (damage=%d, hp=%d/%d)",
                                 floor_num + 1, encounter_type, encounter_id, damage,
                                 character.player_hp, character.player_max_hp)

                        _apply_combat_rewards(
                            character, result, encounter_type, combat_seed, reward_rng,
                            agent,
                            sts_map=sts_map,
                            current_position=(floor_num, x_pos),
                            remaining_path=path[step_idx + 1:],
                        )

                        result.floors_cleared += 1

        if died:
            return result

    result.victory = True
    result.final_hp = character.player_hp
    result.max_hp = character.player_max_hp
    return result


# ---------------------------------------------------------------------------
# Linear loop (legacy 8-floor fixed encounter list)
# ---------------------------------------------------------------------------

def _run_linear(
    seed: int,
    agent: RunAgentProtocol,
    character: Character,
    reward_rng: RNG,
    *,
    observer: FloorObserver | None,
) -> RunResult:
    from .scenarios import act1_encounters

    encounter_list = act1_encounters(seed)

    result = RunResult(
        victory=False,
        floors_cleared=0,
        total_floors=len(encounter_list),
        final_hp=character.player_hp,
        max_hp=character.player_max_hp,
        damage_taken_total=0,
        max_hp_gained_total=0,
    )

    for floor_idx, (encounter_type, encounter_id) in enumerate(encounter_list):
        character.floor = floor_idx + 1
        result.encounter_types.append(encounter_type)

        combat_seed = seed * 1000 + floor_idx

        with _floor_scope(observer, floor_idx + 1, encounter_type, character) as attrs:
            combat = builder.build_combat(
                encounter_type, encounter_id, combat_seed, character=character,
            )

            damage = agent.run_battle(combat)
            result.damage_per_floor.append(damage)
            result.damage_taken_total += damage
            result.max_hp_gained_total += combat.max_hp_gained

            obs = combat.observe()
            attrs.update({
                "encounter_id": encounter_id,
                "damage_taken": damage,
                "max_hp_gained": combat.max_hp_gained,
                "survived": not obs.player_dead,
                "turns": obs.turn,
            })

            if obs.player_dead:
                log.info("FLOOR %d (%s/%s): DIED (damage=%d)",
                         floor_idx + 1, encounter_type, encounter_id, damage)
                character.player_hp = 0
                result.final_hp = 0
                return result

            character.player_hp = obs.player_hp
            character.player_max_hp = obs.player_max_hp
            character.potions = list(combat._state.potions)
            builder.sync_combat_counters(character, combat)
            relics_mod.on_combat_end(character)
            result.final_hp = character.player_hp
            result.max_hp = character.player_max_hp

            log.info("FLOOR %d (%s/%s): WON (damage=%d, hp=%d/%d)",
                     floor_idx + 1, encounter_type, encounter_id, damage,
                     character.player_hp, character.player_max_hp)

            _apply_combat_rewards(
                character, result, encounter_type, combat_seed, reward_rng, agent,
                remaining_path=[(floor_idx + 1 + i, 0) for i in range(len(encounter_list) - floor_idx - 1)],
            )

            result.floors_cleared += 1

    result.victory = True
    result.final_hp = character.player_hp
    result.max_hp = character.player_max_hp
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _floor_scope(
    observer: FloorObserver | None,
    floor: int,
    room_type: str,
    character: Character,
) -> Iterator[dict[str, Any]]:
    """Wrap a floor in the observer's scope, or yield an empty dict if no observer."""
    if observer is None:
        attrs: dict[str, Any] = {}
        yield attrs
    else:
        with observer.floor_scope(floor, room_type, character) as attrs:
            yield attrs


@dataclass
class _RestExecResult:
    choice: RestChoice
    hp_healed: int = 0
    card_upgraded: str | None = None


def _execute_rest_choice(
    agent: RunAgentProtocol,
    character: Character,
) -> _RestExecResult:
    """Ask the agent for a RestChoice, then execute it.

    Falls back to healing if UPGRADE was chosen but no targets exist.
    """
    choice = agent.pick_rest_choice(character)

    if choice == RestChoice.UPGRADE:
        target = _best_upgrade_target(character)
        if target is not None:
            rest_upgrade(character, target)
            return _RestExecResult(RestChoice.UPGRADE, card_upgraded=target)
        healed = rest_heal(character)
        return _RestExecResult(RestChoice.REST, hp_healed=healed)

    healed = rest_heal(character)
    return _RestExecResult(RestChoice.REST, hp_healed=healed)


def _upcoming_from_path(
    remaining_path: list[tuple[int, int]],
    sts_map: StSMap | None,
) -> list[tuple[str, str]]:
    """Derive upcoming (type, id) hints from the remaining path nodes."""
    upcoming: list[tuple[str, str]] = []
    for floor_num, x_pos in remaining_path:
        node = sts_map.get_node(floor_num, x_pos) if sts_map is not None else None
        if node is None:
            continue
        upcoming.append((node.room_type.name.lower(), ""))
    return upcoming


def _apply_combat_rewards(
    character: Character,
    result: RunResult,
    encounter_type: str,
    combat_seed: int,
    reward_rng: RNG,
    agent: RunAgentProtocol,
    *,
    sts_map: StSMap | None = None,
    current_position: tuple[int, int] | None = None,
    remaining_path: list[tuple[int, int]] | None = None,
) -> None:
    """Roll and apply post-combat rewards, delegating card pick to the agent."""
    room = (
        _RewardRoom.ELITE if encounter_type == "elite"
        else _RewardRoom.BOSS if encounter_type == "boss"
        else _RewardRoom.MONSTER
    )
    offer, new_factor = roll_combat_reward_offer(
        reward_rng, room,
        card_rarity_factor=character.card_rarity_factor,
        event_bus=character.event_bus,
    )
    character.card_rarity_factor = new_factor

    upcoming = _upcoming_from_path(remaining_path or [], sts_map)
    picked = agent.pick_card(
        character,
        list(offer.card_choices),
        upcoming,
        combat_seed,
        sts_map=sts_map,
        current_position=current_position,
    )

    if picked is not None:
        character.add_card(picked)
        result.cards_added.append(picked)
        log.info("  Card reward: picked %s from %s", picked, offer.card_choices)
    else:
        log.info("  Card reward: skipped %s", offer.card_choices)

    if offer.potion is not None:
        if len(character.potions) < character.max_potion_slots:
            character.add_potion(offer.potion)
            result.potions_gained.append(offer.potion)
            log.info("  Potion reward: %s (slots: %s)", offer.potion, character.potions)
        else:
            log.info("  Potion reward: %s discarded (no slot)", offer.potion)

    character.gold += offer.gold

    if room == _RewardRoom.ELITE:
        relic = roll_elite_relic(reward_rng, owned=character.relics)
        if relic is not None:
            character.add_relic(relic)
            log.info("  Elite relic reward: %s", relic)
    elif room == _RewardRoom.BOSS:
        available = roll_boss_relic_choices(reward_rng, owned=character.relics)
        if available:
            relic = agent.pick_boss_relic(character, available)
            if relic is None:
                log.info("  Boss relic reward: skipped %s", available)
            else:
                character.add_relic(relic)
                log.info("  Boss relic reward: %s", relic)
