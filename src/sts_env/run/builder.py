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
        "easy", "hard", "boss", or "elite".
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
    if character is not None:
        deck = list(character.deck)
        player_hp = character.player_hp
        player_max_hp = character.player_max_hp
        potions = list(character.potions)
    else:
        if deck is None:
            deck = list(IRONCLAD_STARTER)
        if potions is None:
            potions = []

    if encounter_type == "elite":
        return _build_elite(encounter_id, seed, deck, player_hp, player_max_hp, potions)

    if encounter_type == "boss":
        return _build_boss(encounter_id, seed, deck, player_hp, player_max_hp, potions)

    # Easy / hard — look up by encounter factory name
    factory = _ENCOUNTER_FACTORY_MAP.get(encounter_id)
    if factory is None:
        raise ValueError(f"Unknown encounter: {encounter_type}/{encounter_id}")

    # Use the factory, then override deck/hp/potions from run state
    combat = factory(seed, deck=deck, player_hp=player_hp)
    # Fix max_hp and potions (factories don't expose these kwargs)
    combat._player_max_hp = player_max_hp
    combat._starting_potions = list(potions)
    return combat


def _build_elite(
    encounter_id: str,
    seed: int,
    deck: list[str],
    player_hp: int,
    player_max_hp: int,
    potions: list[str],
) -> Combat:
    """Build an elite Combat from the encounter_id string."""
    for enemy_spec, label in _ELITE_POOLS:
        if label == encounter_id:
            if isinstance(enemy_spec, list):
                enemies = enemy_spec
            else:
                enemies = [enemy_spec]
            return Combat(
                deck=deck,
                enemies=enemies,
                seed=seed,
                player_hp=player_hp,
                player_max_hp=player_max_hp,
                potions=potions,
            )
    raise ValueError(f"Unknown elite: {encounter_id}")


def _build_boss(
    encounter_id: str,
    seed: int,
    deck: list[str],
    player_hp: int,
    player_max_hp: int,
    potions: list[str],
) -> Combat:
    """Build a boss Combat from the encounter_id string."""
    factory = _ENCOUNTER_FACTORY_MAP.get(encounter_id)
    if factory is None:
        raise ValueError(f"Unknown boss: {encounter_id}")
    combat = factory(seed, deck=deck, player_hp=player_hp)
    combat._player_max_hp = player_max_hp
    combat._starting_potions = list(potions)
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
}
