"""Resolve scenario encounter definitions into Combat objects.

Maps encounter_type + encounter_id strings to Combat instances configured
with the player's current PlayerState (deck, HP, relics, potions, gold).
"""

from __future__ import annotations

from ..combat import Combat
from ..combat import encounters as enc
from ..combat.player_state import PlayerState
from .character import Character


def build_combat(
    encounter_type: str,
    encounter_id: str,
    seed: int,
    *,
    character: Character | PlayerState | None = None,
) -> Combat:
    """Create a Combat for the given encounter.

    Parameters
    ----------
    encounter_type:
        "easy", "hard", "monster", "boss", "elite", or "event".
        "monster" is treated identically to "easy"/"hard" (hallway fight).
        "event" tries the factory map first, then falls back to the elite
        factories with ``is_elite=False`` (event elites don't give elite relics).
    encounter_id:
        String identifier (e.g. ``"cultist"``, ``"Lagavulin"``).
    seed:
        Combat seed.
    character:
        A :class:`Character` (or bare :class:`PlayerState`) whose deck/HP/
        relics/potions/gold are forwarded directly to the factory.  When
        ``None`` a fresh Ironclad starter state is used.

    Returns
    -------
    A fully initialized :class:`Combat` (subscriptions, pre-battle hooks, opening
    hand) ready to ``observe()`` / ``step()``.  No second-phase setup.  For
    multiple independent runs from the same built instance, use
    :meth:`Combat.clone`.
    """
    ps: PlayerState = character if character is not None else PlayerState.ironclad_starter()

    is_elite = encounter_type == "elite"

    factory = _ENCOUNTER_FACTORY_MAP.get(encounter_id)

    if encounter_type == "event":
        if factory is not None:
            return factory(seed, ps, is_elite=False)
        raise ValueError(f"Unknown event encounter: {encounter_id}")

    if factory is None:
        raise ValueError(f"Unknown encounter: {encounter_type}/{encounter_id}")

    return factory(seed, ps, is_elite=is_elite)


def sync_combat_counters(character: Character, combat: Combat) -> None:
    """Sync relic_state from CombatState back to Character.

    Call after combat ends to persist per-run relic counters across fights.
    """
    if combat._state is not None:
        character.relic_state = dict(combat._state.relic_state)


# Map encounter_id strings to encounter factory functions.
# Factories have signature: (seed: int, character: PlayerState, *, is_elite: bool) -> Combat
_ENCOUNTER_FACTORY_MAP: dict[str, object] = {
    # Easy (weak) pool
    "cultist": enc.cultist,
    "jaw_worm": enc.jaw_worm,
    "two_louses": enc.two_louses,
    "small_slimes": enc.small_slimes,
    # Hard (strong) pool
    "gremlin_gang": enc.gremlin_gang,
    "lots_of_slimes": enc.lots_of_slimes,
    "red_slaver": enc.red_slaver,
    "exordium_thugs": enc.exordium_thugs,
    "exordium_wildlife": enc.exordium_wildlife,
    "blue_slaver": enc.blue_slaver,
    "looter": enc.looter,
    "large_slime": enc.large_slime,
    "three_louse": enc.three_louse,
    "two_fungi_beasts": enc.two_fungi_beasts,
    # Extra singles (used in events / direct construction)
    "acid_slime_m": enc.acid_slime_m,
    "spike_slime_m": enc.spike_slime_m,
    "acid_slime_l": enc.acid_slime_l,
    "spike_slime_l": enc.spike_slime_l,
    # Elites — keyed by display label (same as ELITE_POOL entries)
    "Gremlin Nob": enc.gremlin_nob,
    "Lagavulin": enc.lagavulin,
    "Three Sentries": enc.three_sentries,
    # Bosses
    "slime_boss": enc.slime_boss,
    "guardian": enc.guardian,
    "hexaghost": enc.hexaghost,
    # Event encounters
    "three_fungi_beasts_event": enc.three_fungi_beasts_event,
    "lagavulin_event": enc.lagavulin_event,
}
