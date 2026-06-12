"""Combat-relevant player state shared between the combat and run layers.

:class:`PlayerState` carries only the fields that encounter factories and
:class:`Combat` need.  The run-level :class:`~sts_env.run.character.Character`
inherits from this and adds run-only fields (floor, event_bus, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import CardColor

# Re-use the canonical starter list from the engine module.
# Imported here to avoid a circular import; engine.py imports from combat
# sub-modules but not from player_state.
_IRONCLAD_STARTER: list[str] = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"] * 1
_IRONCLAD_HP = 80
_IRONCLAD_STARTER_RELICS: list[str] = ["BurningBlood"]
_IRONCLAD_STARTER_GOLD = 99
_MAX_POTION_SLOTS = 3


@dataclass
class PlayerState:
    """Combat-relevant snapshot of the player.

    This is the minimal set of fields that encounter factories and
    :class:`~sts_env.combat.engine.Combat` need.  All fields default to
    Ironclad starter values so factories and tests can be terse.

    Attributes:
        deck: Card IDs in the player's deck.
        player_hp: Current HP at the start of this combat.
        player_max_hp: Maximum HP (may differ from player_hp after damage).
        potions: Active potions held by the player.
        max_potion_slots: Maximum potion capacity (default 3).
        relics: Relic IDs the player carries.
        gold: Current gold (used by relics like Midas Blood).
        relic_state: Per-relic mutable counters (persists across combats).
        relic_data: Run-persistent relic charges/enable flags (C++ RelicInstance.data).
        character_class: Colour/class of the player character.
    """

    deck: list[str] = field(default_factory=lambda: list(_IRONCLAD_STARTER))
    player_hp: int = _IRONCLAD_HP
    player_max_hp: int = _IRONCLAD_HP
    potions: list[str] = field(default_factory=list)
    max_potion_slots: int = _MAX_POTION_SLOTS
    relics: list[str] = field(default_factory=lambda: list(_IRONCLAD_STARTER_RELICS))
    gold: int = _IRONCLAD_STARTER_GOLD
    relic_state: dict[str, int] = field(default_factory=dict)
    relic_data: dict[str, int] = field(default_factory=dict)
    character_class: CardColor = CardColor.RED

    @classmethod
    def ironclad_starter(cls) -> PlayerState:
        """Return a :class:`PlayerState` for a fresh Ironclad run."""
        return cls()
