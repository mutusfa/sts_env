"""Resolve scenario encounter definitions into Combat objects.

Maps encounter_type + encounter_id strings from scenarios.py to Combat
instances configured with the player's current deck, HP, and potions.
"""

from __future__ import annotations

from ..combat import Combat
from ..combat.engine import IRONCLAD_STARTER
from ..combat import encounters as enc
from ..combat.rng import RNG
from .character import Character
from .scenarios import _ELITE_POOLS


def build_combat(
    encounter_type: str,
    encounter_id: str,
    seed: int,
    *,
    character: Character | None = None,
    deck: list[str] | None = None,
    player_hp: int = 80,
    player_max_hp: int = 80,
    potions: list[str] | None = None,
) -> Combat:
    """Create a Combat for the given encounter.

    Parameters
    ----------
    encounter_type:
        "easy", "hard", "monster", "boss", or "elite".
        "monster" is treated identically to "easy"/"hard" (hallway fight).
    encounter_id:
        String identifier from scenario3_encounters (e.g. "cultist",
        "red_slaver", "Lagavulin").
    seed:
        Combat seed.
    character:
        A :class:`Character` instance.  When provided, its deck/hp/potions
        are used and the individual ``deck`` / ``player_hp`` / etc. kwargs
        are ignored.
    deck, player_hp, player_max_hp, potions:
        Override defaults for run-level state (ignored when *character* is
        given).

    Returns
    -------
    Combat ready for reset().
    """
    # Extract run-level state from Character or use defaults
    relics: frozenset[str] = frozenset()
    gold: int = 99
    relic_state: dict[str, int] = {}

    if character is not None:
        deck = list(character.deck)
        player_hp = character.player_hp
        player_max_hp = character.player_max_hp
        potions = list(character.potions)
        relics = frozenset(character.relics)
        gold = character.gold
        relic_state = dict(character.relic_state)
    else:
        if deck is None:
            deck = list(IRONCLAD_STARTER)
        if potions is None:
            potions = []

    is_elite = encounter_type == "elite"

    if encounter_type == "elite":
        return _build_elite(
            encounter_id, seed, deck, player_hp, player_max_hp, potions,
            relics=relics, gold=gold, is_elite=is_elite,
            relic_state=relic_state,
        )

    if encounter_type == "boss":
        return _build_boss(
            encounter_id, seed, deck, player_hp, player_max_hp, potions,
            relics=relics, gold=gold, relic_state=relic_state,
        )

    # Easy / hard / monster — look up by encounter factory name
    factory = _ENCOUNTER_FACTORY_MAP.get(encounter_id)
    if factory is None:
        raise ValueError(f"Unknown encounter: {encounter_type}/{encounter_id}")

    # Use the factory, then override deck/hp/potions from run state
    combat = factory(seed, deck=deck, player_hp=player_hp)
    # Fix max_hp and potions (factories don't expose these kwargs)
    combat._player_max_hp = player_max_hp
    combat._starting_potions = list(potions)
    combat._starting_relics = relics
    combat._starting_gold = gold
    combat._relic_state = relic_state
    return combat


def sync_combat_counters(character: Character, combat: Combat) -> None:
    """Sync relic_state from CombatState back to Character.

    Call after combat ends to persist per-run relic counters across fights.
    """
    if combat._state is not None:
        character.relic_state = dict(combat._state.relic_state)


def _build_elite(
    encounter_id: str,
    seed: int,
    deck: list[str],
    player_hp: int,
    player_max_hp: int,
    potions: list[str],
    *,
    relics: frozenset[str] = frozenset(),
    gold: int = 99,
    is_elite: bool = True,
    relic_state: dict[str, int] | None = None,
) -> Combat:
    """Build an elite Combat from the encounter_id string."""
    for enemy_spec, label in _ELITE_POOLS:
        if label == encounter_id:
            if isinstance(enemy_spec, list):
                enemies = enemy_spec
            else:
                enemies = [enemy_spec]
            combat = Combat(
                deck=deck,
                enemies=enemies,
                seed=seed,
                player_hp=player_hp,
                player_max_hp=player_max_hp,
                potions=potions,
                relics=relics,
                gold=gold,
                is_elite=is_elite,
            )
            combat._relic_state = dict(relic_state) if relic_state else {}
            return combat
    raise ValueError(f"Unknown elite: {encounter_id}")


def _build_boss(
    encounter_id: str,
    seed: int,
    deck: list[str],
    player_hp: int,
    player_max_hp: int,
    potions: list[str],
    *,
    relics: frozenset[str] = frozenset(),
    gold: int = 99,
    relic_state: dict[str, int] | None = None,
) -> Combat:
    """Build a boss Combat from the encounter_id string."""
    factory = _ENCOUNTER_FACTORY_MAP.get(encounter_id)
    if factory is None:
        raise ValueError(f"Unknown boss: {encounter_id}")
    combat = factory(seed, deck=deck, player_hp=player_hp)
    combat._player_max_hp = player_max_hp
    combat._starting_potions = list(potions)
    combat._starting_relics = relics
    combat._starting_gold = gold
    combat._relic_state = dict(relic_state) if relic_state else {}
    return combat


# Map encounter_id strings to encounter factory functions
_ENCOUNTER_FACTORY_MAP: dict[str, object] = {
    # Single enemies (easy pool)
    "cultist": enc.cultist,
    "jaw_worm": enc.jaw_worm,
    # Multi-enemy (easy pool)
    "two_louses": enc.two_louses,
    "small_slimes": enc.small_slimes,
    # Single enemies (hard pool entries)
    "blue_slaver": enc.blue_slaver,
    "red_slaver": enc.red_slaver,
    "looter": enc.looter,
    # Multi-enemy (hard pool entries)
    "gremlin_gang": enc.gremlin_gang,
    "lots_of_slimes": enc.lots_of_slimes,
    "three_louse": enc.three_louse,
    "two_fungi_beasts": enc.two_fungi_beasts,
    "acid_slime_l": enc.acid_slime_l,
    "spike_slime_l": enc.spike_slime_l,
    "large_slime": enc.large_slime,
    "exordium_thugs": enc.exordium_thugs,
    "exordium_wildlife": enc.exordium_wildlife,
    # Single enemies (also in strong pool)
    "acid_slime_m": enc.acid_slime_m,
    "spike_slime_m": enc.spike_slime_m,
    # Boss encounters
    "slime_boss": enc.slime_boss,
    "guardian": enc.guardian,
    "hexaghost": enc.hexaghost,
}
