"""Act 1 event definitions for Slay the Spire.

Each event has an ID, flavour text, and a list of choices with deterministic
outcomes given the same RNG state.  Events are registered into a global
registry and resolved via ``resolve_event``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from ..combat.card_pools import colorless_pool, pool
from ..combat.cards import CardColor, Rarity
from ..combat.rng import RNG

if TYPE_CHECKING:
    from .character import Character


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EventChoice:
    """A single choice in an event."""

    label: str  # Human-readable choice text
    effect: Callable[["Character", RNG], str]  # Returns result description


@dataclass(frozen=True)
class EventSpec:
    """An event definition."""

    event_id: str
    description: str
    choices: list[EventChoice]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_EVENTS: dict[str, EventSpec] = {}


def register_event(spec: EventSpec) -> None:
    _EVENTS[spec.event_id] = spec


def get_event(event_id: str) -> EventSpec:
    return _EVENTS[event_id]


def random_act1_event(rng: RNG) -> EventSpec:
    """Pick a random Act 1 event."""
    keys = list(_EVENTS.keys())
    return _EVENTS[rng.choice(keys)]


def resolve_event(
    event_id: str, choice_index: int, character: "Character", rng: RNG
) -> str:
    """Resolve an event choice.  Returns result description string."""
    spec = _EVENTS[event_id]
    choice = spec.choices[choice_index]
    return choice.effect(character, rng)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Common relics pool for event rewards
_COMMON_RELICS: list[str] = [
    "Anchor",
    "BagOfMarbles",
    "BloodVial",
    "BronzeScales",
    "CentennialPuzzle",
    "CeramicFish",
    "DreamCatcher",
    "HappyFlower",
    "JuzuBracelet",
    "Lantern",
    "MawBank",
    "MealTicket",
    "Nunchaku",
    "OrnamentalFan",
    "Pantograph",
    "PenNib",
    "QuestionCard",
    "RedSkull",
    "RegalPillow",
    "SmilingMask",
    "Strawberry",
    "TheBoot",
    "TinyChest",
    "ToyOrnithopter",
    "Vajra",
    "WarPaint",
    "Whetstone",
]

# Priority order for card removal (worst cards first)
_REMOVAL_PRIORITY: dict[str, int] = {
    "AscendersBane": 0,
    "Slimed": 1,
    "Slimed+": 1,
    "Wound": 2,
    "Dazed": 3,
    "Strike": 4,
    "Strike+": 4,
    "Defend": 5,
    "Defend+": 5,
}
_DEFAULT_REMOVAL_PRIORITY = 99


def _pick_worst_card(deck: list[str]) -> str | None:
    """Return the worst card from the deck for removal, or None if empty."""
    if not deck:
        return None
    return min(
        deck,
        key=lambda c: _REMOVAL_PRIORITY.get(c, _DEFAULT_REMOVAL_PRIORITY),
    )


def _pct_max_hp(character: "Character", pct: float) -> int:
    """Return *pct* percent of max HP, rounded down (min 1)."""
    return max(1, math.floor(character.player_max_hp * pct))


def _missing_hp(character: "Character") -> int:
    return character.player_max_hp - character.player_hp


def _lose_max_hp(character: "Character", amount: int) -> None:
    """Reduce both max HP and current HP by *amount* (current clamped)."""
    amount = min(amount, character.player_max_hp)
    character.player_max_hp -= amount
    character.player_hp = min(character.player_hp, character.player_max_hp)


def _upgrade_random_card(character: "Character", rng: RNG) -> str | None:
    """Upgrade a random non-upgraded card in the deck.  Returns card id or None."""
    upgradable = [c for c in character.deck if not c.endswith("+")]
    if not upgradable:
        return None
    card = rng.choice(upgradable)
    idx = character.deck.index(card)
    character.deck[idx] = card + "+"
    return character.deck[idx]


# ---------------------------------------------------------------------------
# Event definitions — Act 1
# ---------------------------------------------------------------------------

# --- Big Fish ---------------------------------------------------------------

def _big_fish_gold(character: "Character", rng: RNG) -> str:
    loss = _pct_max_hp(character, 0.05)
    _lose_max_hp(character, loss)
    character.gold += 50
    return f"Lose {loss} max HP.  Gain 50 gold."


def _big_fish_upgrade(character: "Character", rng: RNG) -> str:
    result = _upgrade_random_card(character, rng)
    if result is None:
        return "No cards to upgrade."
    return f"Upgraded {result}."


def _big_fish_pay(character: "Character", rng: RNG) -> str:
    if character.gold < 7:
        return "Not enough gold.  Nothing happens."
    character.gold -= 7
    return "Lost 7 gold."


register_event(
    EventSpec(
        event_id="Big Fish",
        description=(
            "A big fish appears!  You may sacrifice some of your vitality "
            "for gold, upgrade a card, or pay a small fee to pass."
        ),
        choices=[
            EventChoice(
                label="Lose 5% max HP.  Gain 50 gold.",
                effect=_big_fish_gold,
            ),
            EventChoice(
                label="Upgrade a random card.",
                effect=_big_fish_upgrade,
            ),
            EventChoice(
                label="Lose 7 gold.",
                effect=_big_fish_pay,
            ),
        ],
    )
)


# --- Golden Idol ------------------------------------------------------------

def _golden_idol_navigate(character: "Character", rng: RNG) -> str:
    loss = _pct_max_hp(character, 0.05)
    _lose_max_hp(character, loss)
    character.gold += 50
    return f"Lose {loss} max HP.  Gain 50 gold."


def _golden_idol_flowers(character: "Character", rng: RNG) -> str:
    missing = _missing_hp(character)
    heal_amt = max(1, math.floor(missing * 0.25))
    character.heal(heal_amt)
    relic = rng.choice(_COMMON_RELICS)
    character.relics.append(relic)
    return f"Healed {heal_amt} HP.  Obtained {relic}."


register_event(
    EventSpec(
        event_id="Golden Idol",
        description=(
            "You discover a golden idol atop a pedestal.  You may carefully "
            "navigate the traps for gold, or step on the sacred flowers to "
            "gain a blessing."
        ),
        choices=[
            EventChoice(
                label="Navigate the traps.  Gain 50 gold, lose 5% max HP.",
                effect=_golden_idol_navigate,
            ),
            EventChoice(
                label="Step on the flowers.  Heal 25% of missing HP, gain a random common relic.",
                effect=_golden_idol_flowers,
            ),
        ],
    )
)


# --- The Cleric -------------------------------------------------------------

def _cleric_heal(character: "Character", rng: RNG) -> str:
    if character.gold < 15:
        return "Not enough gold.  Nothing happens."
    character.gold -= 15
    heal_amt = _pct_max_hp(character, 0.20)
    character.heal(heal_amt)
    return f"Paid 15 gold.  Healed {heal_amt} HP."


def _cleric_remove(character: "Character", rng: RNG) -> str:
    if character.gold < 50:
        return "Not enough gold.  Nothing happens."
    worst = _pick_worst_card(character.deck)
    if worst is None:
        return "Paid 50 gold but no cards to remove."
    character.gold -= 50
    character.deck.remove(worst)
    return f"Paid 50 gold.  Removed {worst} from deck."


def _cleric_leave(character: "Character", rng: RNG) -> str:
    return "You leave the cleric alone."


register_event(
    EventSpec(
        event_id="The Cleric",
        description=(
            "A travelling cleric offers their services.  For a donation they "
            "can heal your wounds or purify your deck."
        ),
        choices=[
            EventChoice(
                label="Pay 15 gold: Heal 20% of max HP.",
                effect=_cleric_heal,
            ),
            EventChoice(
                label="Pay 50 gold: Remove a card from your deck.",
                effect=_cleric_remove,
            ),
            EventChoice(
                label="Leave.",
                effect=_cleric_leave,
            ),
        ],
    )
)


# --- Dead Adventurer --------------------------------------------------------

def _dead_adventurer_fight(character: "Character", rng: RNG) -> str:
    loss = 5
    character.player_hp = max(0, character.player_hp - loss)
    # Determine a random reward (simulate double rewards)
    card_pool_list = (
        pool(character.character_class, Rarity.COMMON)
        + pool(character.character_class, Rarity.UNCOMMON)
    )
    card = rng.choice(card_pool_list)
    gold = rng.randint(20, 40)
    character.gold += gold
    return f"Took {loss} damage.  Found {gold} gold and {card} on the corpse."


def _dead_adventurer_leave(character: "Character", rng: RNG) -> str:
    return "You leave the remains undisturbed."


register_event(
    EventSpec(
        event_id="Dead Adventurer",
        description=(
            "You stumble upon the remains of a fallen adventurer.  You could "
            "search the body but the area looks dangerous."
        ),
        choices=[
            EventChoice(
                label="Take 5 damage and loot the corpse for double rewards.",
                effect=_dead_adventurer_fight,
            ),
            EventChoice(
                label="Leave.",
                effect=_dead_adventurer_leave,
            ),
        ],
    )
)


# --- Golden Wing ------------------------------------------------------------

def _golden_wing_gold(character: "Character", rng: RNG) -> str:
    loss = _pct_max_hp(character, 0.05)
    _lose_max_hp(character, loss)
    character.gold += 100
    return f"Lose {loss} max HP.  Gain 100 gold."


def _golden_wing_heal(character: "Character", rng: RNG) -> str:
    lost_gold = character.gold
    character.gold = 0
    heal_amt = _pct_max_hp(character, 0.25)
    character.heal(heal_amt)
    return f"Lost {lost_gold} gold.  Healed {heal_amt} HP."


register_event(
    EventSpec(
        event_id="Golden Wing",
        description=(
            "A golden-winged statue offers a trade.  Sacrifice your vitality "
            "for wealth, or surrender your wealth for health."
        ),
        choices=[
            EventChoice(
                label="Gain 100 gold, lose 5% max HP.",
                effect=_golden_wing_gold,
            ),
            EventChoice(
                label="Lose all gold, heal 25% max HP.",
                effect=_golden_wing_heal,
            ),
        ],
    )
)


# --- Liars Game -------------------------------------------------------------

def _liars_game_play(character: "Character", rng: RNG) -> str:
    if character.gold < 5:
        return "Not enough gold to play.  Nothing happens."
    character.gold -= 5
    if rng.random() < 0.5:
        character.gold += 50
        return "You win!  Gained 50 gold (net +45)."
    else:
        character.gold = max(0, character.gold - 5)
        return "You lose.  Lost an additional 5 gold."


def _liars_game_leave(character: "Character", rng: RNG) -> str:
    return "You walk away from the game."


register_event(
    EventSpec(
        event_id="Liars Game",
        description=(
            "A shady figure invites you to a game of chance.  Pay 5 gold to "
            "play — you could win big or lose more."
        ),
        choices=[
            EventChoice(
                label="Pay 5 gold: 50% chance gain 50 gold, 50% chance lose 5 more gold.",
                effect=_liars_game_play,
            ),
            EventChoice(
                label="Leave.",
                effect=_liars_game_leave,
            ),
        ],
    )
)


# --- Scrap Ooze -------------------------------------------------------------

def _scrap_ooze_card(character: "Character", rng: RNG) -> str:
    card = rng.choice(colorless_pool())
    character.add_card(card)
    return f"Obtained {card}."


def _scrap_ooze_pay(character: "Character", rng: RNG) -> str:
    if character.gold < 3:
        return "Not enough gold.  You scurry away."
    character.gold -= 3
    return "Lost 3 gold."


register_event(
    EventSpec(
        event_id="Scrap Ooze",
        description=(
            "A strange ooze holds a shimmering card.  You can try to extract "
            "it or pay the ooze a small toll to pass."
        ),
        choices=[
            EventChoice(
                label="Obtain a random colorless card.",
                effect=_scrap_ooze_card,
            ),
            EventChoice(
                label="Lose 3 gold.",
                effect=_scrap_ooze_pay,
            ),
        ],
    )
)
