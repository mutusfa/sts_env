"""Character state for the strategic (run) layer.

Bundles all player state that persists between combats: deck, HP, potions,
relics, gold, and floor.  Provides factory methods, mutation helpers, and
serialisation for the LLM agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Import the canonical definition from the combat engine.
# Re-exported here for convenience (``from sts_env.run.character import IRONCLAD_STARTER``).
from ..combat.engine import IRONCLAD_STARTER  # noqa: F401

# Default Ironclad values
_IRONCLAD_HP = 80
_IRONCLAD_MAX_HP = 80
_IRONCLAD_STARTER_RELICS: list[str] = ["BurningBlood"]
_IRONCLAD_STARTER_GOLD = 99
_MAX_POTION_SLOTS = 3


@dataclass
class Character:
    """Player state carried across the strategic layer of a run.

    Attributes:
        deck: Current deck list (grows as cards are added from rewards).
        player_hp: Current HP (carried between combats).
        player_max_hp: Maximum HP.
        potions: Current potion slots.
        max_potion_slots: Maximum number of potion slots (default 3).
        gold: Gold count.
        floor: Current floor number.
        relics: Current relics.
    """

    deck: list[str] = field(default_factory=lambda: list(IRONCLAD_STARTER))
    player_hp: int = _IRONCLAD_HP
    player_max_hp: int = _IRONCLAD_MAX_HP
    potions: list[str] = field(default_factory=list)
    max_potion_slots: int = _MAX_POTION_SLOTS
    gold: int = _IRONCLAD_STARTER_GOLD
    floor: int = 0
    relics: list[str] = field(default_factory=lambda: list(_IRONCLAD_STARTER_RELICS))

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def ironclad(cls) -> Character:
        """Return a fresh Ironclad starter character."""
        return cls()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_card(self, card_id: str) -> None:
        """Add a card to the deck (from card rewards)."""
        self.deck.append(card_id)

    def add_potion(self, potion_id: str) -> None:
        """Add a potion if a slot is available, otherwise discard it."""
        if len(self.potions) < self.max_potion_slots:
            self.potions.append(potion_id)
        # else: potion is discarded (no slot available)

    def has_relic(self, relic_name: str) -> bool:
        """Return True if the character possesses the named relic."""
        return relic_name in self.relics

    def heal(self, amount: int) -> None:
        """Heal the player, capped at max_hp."""
        self.player_hp = min(self.player_max_hp, self.player_hp + amount)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable one-liner for the LLM agent."""
        return (
            f"HP={self.player_hp}/{self.player_max_hp} "
            f"Gold={self.gold} "
            f"Floor={self.floor} "
            f"Deck({len(self.deck)}) "
            f"Potions{self.potions} "
            f"Relics{self.relics}"
        )

    def snapshot(self) -> dict:
        """Return all state as a plain dict (for LLM context)."""
        return {
            "deck": list(self.deck),
            "player_hp": self.player_hp,
            "player_max_hp": self.player_max_hp,
            "potions": list(self.potions),
            "max_potion_slots": self.max_potion_slots,
            "gold": self.gold,
            "floor": self.floor,
            "relics": list(self.relics),
        }

    # ------------------------------------------------------------------
    # Unpacking support (for builder.build_combat)
    # ------------------------------------------------------------------

    def combat_kwargs(self) -> dict:
        """Return kwargs suitable for ``builder.build_combat``."""
        return {
            "deck": list(self.deck),
            "player_hp": self.player_hp,
            "player_max_hp": self.player_max_hp,
            "potions": list(self.potions),
        }
