"""Act 1 event definitions for Slay the Spire.

Each event has an ID, flavour text, and a list of choices with deterministic
outcomes given the same RNG state.  Events are registered into a global
registry and resolved via ``resolve_event``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from ..combat.card_pools import colorless_pool, curse_pool, pool
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
    effect: Callable[[Character, RNG], str]  # Returns result description
    # If True, the orchestrator calls agent.pick_card_to_remove() after
    # resolving this choice.
    requires_card_removal: bool = False
    # If True, choosing this triggers a combat (encounter info on EventSpec).
    triggers_combat: bool = False


@dataclass(frozen=True)
class EventSpec:
    """An event definition."""

    event_id: str
    description: str
    choices: list[EventChoice]
    # For events that can trigger combat (Dead Adventurer, Mushrooms, etc.).
    # Each combat-triggering choice stores encounter info here.
    encounter_type: str | None = None  # e.g. "event", "monster"
    encounter_id: str | None = None   # e.g. "three_fungi_beasts_event"
    # All possible encounter IDs the agent might face if it picks a combat
    # choice.  Populated for events where the encounter is random or there
    # are multiple options.  Empty for non-combat events.
    possible_encounters: tuple[str, ...] = ()
    # For multi-phase events (Dead Adventurer): tracks current phase and reward schedule.
    multi_phase: bool = False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_EVENTS: dict[str, EventSpec] = {}


def register_event(spec: EventSpec) -> None:
    _EVENTS[spec.event_id] = spec


def get_event(event_id: str) -> EventSpec:
    return _EVENTS[event_id]


def random_act1_event(rng: RNG, seen_events: list[str] | None = None) -> EventSpec:
    """Pick a random Act 1 event, excluding already-seen events."""
    exclude = set(seen_events) if seen_events else set()
    keys = [k for k in _EVENTS if k not in exclude]
    if not keys:
        # All events seen — allow repeats (shouldn't happen in normal play)
        keys = list(_EVENTS.keys())
    return _EVENTS[rng.choice(keys)]


def resolve_event(
    event_id: str, choice_index: int, character: "Character", rng: RNG,
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
    "HappyFlower",
    "JuzuBracelet",
    "Lantern",
    "Nunchaku",
    "Orichalcum",
    "OrnamentalFan",
    "PreservedInsect",
    "RedSkull",
    "RegalPillow",
    "Shuriken",
    "Strawberry",
    "Sundial",
    "TheBoot",
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
    character.add_relic(relic)
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
    if character.gold < 35:
        return "Not enough gold.  Nothing happens."
    character.gold -= 35
    heal_amt = _pct_max_hp(character, 0.25)
    character.heal(heal_amt)
    return f"Paid 35 gold.  Healed {heal_amt} HP."


def _cleric_remove(character: "Character", rng: RNG) -> str:
    """Pay 50 gold for card removal.  The orchestrator handles the actual
    card pick via ``agent.pick_card_to_remove()``."""
    if character.gold < 50:
        return "Not enough gold.  Nothing happens."
    character.gold -= 50
    return "PAID_FOR_REMOVAL"


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
                label="Pay 35 gold: Heal 25% of max HP.",
                effect=_cleric_heal,
            ),
            EventChoice(
                label="Pay 50 gold: Remove a card from your deck (specify which card in your response).",
                effect=_cleric_remove,
                requires_card_removal=True,
            ),
            EventChoice(
                label="Leave.",
                effect=_cleric_leave,
            ),
        ],
    )
)


# --- Dead Adventurer --------------------------------------------------------

# Per C++ reference: multi-phase event with escalating elite encounter chance.
# On setup: 3 shuffled reward slots (0=gold, 1=card, 2=relic) and a random
# elite encounter chosen from [Three Sentries, Gremlin Nob, lagavulin_event].
# Each "Loot" attempt: encounter chance = phase * 25 + 25%.
# If encounter triggers: fight the elite, get combined remaining rewards.
# If no encounter: collect reward for current phase, increment phase.

# Module-level state for multi-phase event (set during resolve_event).
_da_state: dict = {}


def _dead_adventurer_setup(rng: RNG) -> dict:
    """Initialize Dead Adventurer event state."""
    import random
    rewards = [0, 1, 2]  # 0=gold, 1=card, 2=relic
    rng.shuffle(rewards)
    encounter_id = rng.choice(["Three Sentries", "Gremlin Nob", "lagavulin_event"])
    return {
        "phase": 0,
        "rewards": rewards,
        "encounter_id": encounter_id,
    }


def _dead_adventurer_loot(character: "Character", rng: RNG) -> str:
    state = _da_state
    phase = state["phase"]
    rewards = state["rewards"]
    encounter_id = state["encounter_id"]

    if phase >= 3:
        return "There is nothing left to loot."

    # Encounter chance: phase * 25 + 25%
    encounter_chance = phase * 25 + 25
    did_encounter = rng.randint(0, 99) < encounter_chance

    if did_encounter:
        # Fight the elite — collect remaining rewards
        gold_amt = rng.randint(25, 35)
        relic_added = False

        for i in range(phase, 3):
            if rewards[i] == 0:
                gold_amt += 30
            elif rewards[i] == 2:
                relic_added = True

        # Mark combat needed for orchestrator
        state["combat_needed"] = True
        state["combat_encounter_type"] = "event"
        state["combat_encounter_id"] = encounter_id
        state["combat_gold_reward"] = gold_amt
        state["combat_relic_reward"] = relic_added
        state["phase"] = 3  # Event ends after combat

        desc = (
            f"You are ambushed by {encounter_id}! "
            f"(Combat reward: {gold_amt} gold"
        )
        if relic_added:
            desc += " + relic"
        desc += f" + card reward)"
        return desc

    else:
        # Safe — collect current reward
        reward = rewards[phase]
        result_desc = f"Looted safely (phase {phase + 1}/3). "

        if reward == 0:
            # GOLD
            character.gold += 30
            result_desc += "Found 30 gold."
        elif reward == 1:
            # CARD — add to deck
            card_pool_list = (
                pool(character.character_class, Rarity.COMMON)
                + pool(character.character_class, Rarity.UNCOMMON)
            )
            card = rng.choice(card_pool_list)
            character.add_card(card)
            result_desc += f"Found {card}."
        elif reward == 2:
            # RELIC
            relic = rng.choice(_COMMON_RELICS)
            character.add_relic(relic)
            result_desc += f"Found {relic} relic."

        state["phase"] = phase + 1
        if state["phase"] >= 3:
            result_desc += " The corpse has been fully looted."
        return result_desc


def _dead_adventurer_leave(character: "Character", rng: RNG) -> str:
    return "You leave the remains undisturbed."


register_event(
    EventSpec(
        event_id="Dead Adventurer",
        description=(
            "You stumble upon the remains of a fallen adventurer.  "
            "You can repeatedly loot the body for rewards, but each attempt "
            "risks an encounter with a powerful elite monster (Three Sentries, "
            "Gremlin Nob, or Lagavulin).  The risk increases with each loot attempt. "
            "If you are ambushed, you must fight the elite for combined rewards."
        ),
        choices=[
            EventChoice(
                label="Loot the corpse (risk elite encounter, increasing chance).",
                effect=_dead_adventurer_loot,
                triggers_combat=True,
            ),
            EventChoice(
                label="Leave.",
                effect=_dead_adventurer_leave,
            ),
        ],
        possible_encounters=("Three Sentries", "Gremlin Nob", "lagavulin_event"),
        multi_phase=True,
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


# --- Shining Light ----------------------------------------------------------


def _shining_light_upgrade(character: "Character", rng: RNG) -> str:
    upgraded = []
    for _ in range(2):
        result = _upgrade_random_card(character, rng)
        if result is not None:
            upgraded.append(result)
    if not upgraded:
        return "No cards to upgrade."
    return f"Upgraded {', '.join(upgraded)}."


def _shining_light_damage(character: "Character", rng: RNG) -> str:
    damage = 7
    character.player_hp = max(0, character.player_hp - damage)
    return f"Took {damage} damage."


register_event(
    EventSpec(
        event_id="Shining Light",
        description=(
            "A brilliant light shines through the canopy.  You may step into "
            "it to empower your cards or step away to avoid potential harm."
        ),
        choices=[
            EventChoice(
                label="Step into the light.  Upgrade 2 random cards.",
                effect=_shining_light_upgrade,
            ),
            EventChoice(
                label="Step away.  Take 7 damage.",
                effect=_shining_light_damage,
            ),
        ],
    )
)


# --- Bonfire ----------------------------------------------------------------


def _bonfire_upgrade(character: "Character", rng: RNG) -> str:
    from .rooms import _best_upgrade_target

    target = _best_upgrade_target(character)
    if target is None:
        return "No cards to upgrade."
    idx = character.deck.index(target)
    character.deck[idx] = target + "+"
    _lose_max_hp(character, 5)
    return f"Upgraded {target}.  Lost 5 Max HP."


def _bonfire_leave(character: "Character", rng: RNG) -> str:
    return "You leave the bonfire burning."


register_event(
    EventSpec(
        event_id="Bonfire",
        description=(
            "A mystical bonfire crackles before you.  You may toss a fragment "
            "of your life essence into the flames to strengthen a card."
        ),
        choices=[
            EventChoice(
                label="Upgrade a card.  Lose 5 Max HP.",
                effect=_bonfire_upgrade,
            ),
            EventChoice(
                label="Leave.",
                effect=_bonfire_leave,
            ),
        ],
    )
)


# --- Wing Statue ------------------------------------------------------------


def _wing_statue_remove(character: "Character", rng: RNG) -> str:
    candidates = [c for c in character.deck if c in ("Strike", "Strike+", "Defend", "Defend+")]
    if not candidates:
        return "No Strike or Defend cards to remove."
    card = rng.choice(candidates)
    character.deck.remove(card)
    return f"Removed {card} from deck."


def _wing_statue_leave(character: "Character", rng: RNG) -> str:
    return "You leave the statue undisturbed."


register_event(
    EventSpec(
        event_id="Wing Statue",
        description=(
            "A winged statue radiates a purifying aura.  It offers to strip "
            "away a basic defensive or offensive instinct from your mind."
        ),
        choices=[
            EventChoice(
                label="Remove a Strike or Defend from your deck.",
                effect=_wing_statue_remove,
            ),
            EventChoice(
                label="Leave.",
                effect=_wing_statue_leave,
            ),
        ],
    )
)


# --- Wheel of Change ---------------------------------------------------------


def _wheel_of_change_spin(character: "Character", rng: RNG) -> str:
    roll = rng.randint(1, 5)
    if roll == 1:
        character.gold += 50
        return "The wheel lands on gold!  Gained 50 gold."
    elif roll == 2:
        curses = curse_pool()
        if curses:
            curse = rng.choice(curses)
            character.add_card(curse)
            return f"The wheel curses you!  Obtained {curse}."
        return "The wheel spins… but nothing happens."
    elif roll == 3:
        card_pool_list = (
            pool(character.character_class, Rarity.COMMON)
            + pool(character.character_class, Rarity.UNCOMMON)
        )
        if card_pool_list:
            card = rng.choice(card_pool_list)
            character.add_card(card)
            return f"The wheel grants a card!  Obtained {card}."
        return "The wheel spins… but nothing happens."
    else:
        return "The wheel spins… nothing happens."


register_event(
    EventSpec(
        event_id="Wheel of Change",
        description=(
            "A massive wheel stands before you, covered in cryptic symbols. "
            "You may spin it and let fate decide your reward… or punishment."
        ),
        choices=[
            EventChoice(
                label="Spin the wheel.",
                effect=_wheel_of_change_spin,
            ),
        ],
    )
)


# --- Hypnotizing Colored Mushrooms -----------------------------------------

# Per C++ reference (Act 1 event, only appears after floor 6):
# Choice 0: Fight two Fungi Beasts → gold (20-30) + Odd Mushroom relic + card reward
# Choice 1: Gain 99 gold (non-Asc15) or 50 gold (Asc15)


def _mushrooms_fight(character: "Character", rng: RNG) -> str:
    gold_amt = rng.randint(20, 30)
    character.gold += gold_amt
    # Odd Mushroom relic — grants "Mushroom" effect (not yet in relic system)
    # For now, add as a named relic
    character.add_relic("Odd Mushroom")
    desc = f"Fought the mushrooms!  Gained {gold_amt} gold and Odd Mushroom relic."
    return desc


def _mushrooms_gold(character: "Character", rng: RNG) -> str:
    gold_amt = 99
    character.gold += gold_amt
    return f"Took the gold.  Gained {gold_amt} gold."


register_event(
    EventSpec(
        event_id="Hypnotizing Colored Mushrooms",
        description=(
            "Hypnotic colored mushrooms surround you.  You can either eat them "
            "and fight the mushroom creatures for valuable rewards (Odd Mushroom "
            "relic + gold + card), or simply gather the gold scattered around them."
        ),
        choices=[
            EventChoice(
                label="Eat the mushrooms and fight (two Fungi Beasts). Reward: gold + Odd Mushroom relic + card.",
                effect=_mushrooms_fight,
                triggers_combat=True,
            ),
            EventChoice(
                label="Take the gold (99 gold) and leave.",
                effect=_mushrooms_gold,
            ),
        ],
        encounter_type="event",
        encounter_id="three_fungi_beasts_event",
        possible_encounters=("three_fungi_beasts_event",),
    )
)
