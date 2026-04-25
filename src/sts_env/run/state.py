"""Run-level state that persists across multiple combats.

Tracks player HP, deck composition, relics, potions, gold, and floor number.
Provides methods for healing, adding cards/potions, and constructing the
combat-state dict needed to start a new Combat.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunState:
    """State carried between combats in a single run.

    Attributes:
        player_hp: Current HP (carried between combats).
        player_max_hp: Max HP (80 for Ironclad).
        deck: Current deck list (grows as cards are added from rewards).
        potions: Current potion slots (max 3, carried between combats).
        relics: Current relics (start with ["BurningBlood"]).
        gold: Gold count (not used strategically, just tracked).
        floor: Current floor number.
    """

    player_hp: int = 80
    player_max_hp: int = 80
    deck: list[str] = field(default_factory=lambda: [
        "Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    )
    potions: list[str] = field(default_factory=list)
    relics: list[str] = field(default_factory=lambda: ["BurningBlood"])
    gold: int = 99
    floor: int = 0

    _MAX_POTION_SLOTS: int = 3

    def heal(self, amount: int) -> None:
        """Heal the player, capped at max_hp."""
        self.player_hp = min(self.player_max_hp, self.player_hp + amount)

    def add_card(self, card_id: str) -> None:
        """Add a card to the deck (from card rewards)."""
        self.deck.append(card_id)

    def add_potion(self, potion_id: str) -> None:
        """Add a potion if a slot is available, otherwise discard it."""
        if len(self.potions) < self._MAX_POTION_SLOTS:
            self.potions.append(potion_id)
        # else: potion is discarded (no slot available)

    def combat_state(self) -> dict:
        """Return a dict with the state needed to construct a Combat.

        The returned dict can be unpacked into Combat() or used by
        encounter factories.
        """
        return {
            "deck": list(self.deck),
            "player_hp": self.player_hp,
            "player_max_hp": self.player_max_hp,
            "potions": list(self.potions),
        }
