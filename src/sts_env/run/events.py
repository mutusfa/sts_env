"""Act 1 event definitions for Slay the Spire.

Each event has an ID, flavour text, and a list of choices with deterministic
outcomes given the same RNG state.  Events are registered into a global
registry and resolved via ``resolve_event``.

All values match the C++ sts_lightspeed reference implementation for
non-Ascension difficulty (Asc 0–14).  Ascension 15+ adjustments are
deferred to a later phase.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from ..combat.card_pools import colorless_pool, curse_pool, pool
from ..combat.cards import CardColor, Rarity, get_spec
from ..combat.rng import RNG
from ..run.rewards import roll_elite_relic

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
    # If True, the orchestrator calls agent.pick_card_to_transform() after
    # resolving this choice.
    requires_card_transform: bool = False
    # If True, the orchestrator calls agent.pick_card_to_upgrade() after
    # resolving this choice.
    requires_card_upgrade: bool = False


@dataclass(frozen=True)
class EventSpec:
    """An event definition."""

    event_id: str
    description: str
    choices: list[EventChoice]
    # For events that can trigger combat (Dead Adventurer, Mushrooms, etc.).
    encounter_type: str | None = None
    encounter_id: str | None = None
    # All possible encounter IDs the agent might face if it picks a combat
    # choice.
    possible_encounters: tuple[str, ...] = ()
    # For multi-phase events: tracks current phase.
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

# Priority order for automatic card removal (worst cards first).
# Used by Wheel of Change card-removal outcome.
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


def _gain_max_hp(character: "Character", amount: int) -> None:
    """Increase both max HP and current HP by *amount*."""
    character.player_max_hp += amount
    character.player_hp += amount


def _damage_player(character: "Character", amount: int) -> None:
    """Reduce current HP by *amount* (event-level damagePlayer)."""
    character.player_hp = max(0, character.player_hp - amount)


def _upgrade_random_card(character: "Character", rng: RNG) -> str | None:
    """Upgrade a random non-upgraded card in the deck.  Returns card id or None."""
    upgradable = [c for c in character.deck if not c.endswith("+")]
    if not upgradable:
        return None
    card = rng.choice(upgradable)
    idx = character.deck.index(card)
    character.deck[idx] = card + "+"
    return character.deck[idx]


def transform_card(character: "Character", card_id: str, rng: RNG) -> str | None:
    """Remove a card and replace with a random card of the same color and rarity.

    Returns the new card ID, or None if no replacement was possible.
    """
    base_id = card_id.rstrip("+")
    try:
        spec = get_spec(base_id)
    except (KeyError, ValueError):
        # Unknown card (curse/status without spec) — just remove it
        if card_id in character.deck:
            character.deck.remove(card_id)
        return None

    # Determine candidate pool based on card properties
    if spec.color == CardColor.COLORLESS:
        candidates = colorless_pool(spec.rarity)
    elif spec.color in (CardColor.CURSE,):
        candidates = curse_pool()
    else:
        candidates = pool(spec.color, spec.rarity)

    # Remove old card
    if card_id in character.deck:
        character.deck.remove(card_id)

    # Pick a different card from the pool
    candidates = [c for c in candidates if c != base_id]
    if not candidates:
        return None

    new_card = rng.choice(candidates)
    character.add_card(new_card)
    return new_card


# ---------------------------------------------------------------------------
# Event definitions — Act 1 Events (11)
# ---------------------------------------------------------------------------

# --- 1. Big Fish ---------------------------------------------------------------
# C++: choice 0 = heal 33% max HP; choice 1 = gain 5 max HP; choice 2 = relic + Regret

def _big_fish_heal(character: "Character", rng: RNG) -> str:
    heal_amt = _pct_max_hp(character, 1 / 3)
    character.heal(heal_amt)
    return f"Healed {heal_amt} HP."


def _big_fish_max_hp(character: "Character", rng: RNG) -> str:
    _gain_max_hp(character, 5)
    return "Gained 5 Max HP."


def _big_fish_relic(character: "Character", rng: RNG) -> str:
    relic = roll_elite_relic(rng, owned=character.relics)
    if relic:
        character.add_relic(relic)
    character.add_card("Regret")
    relic_str = f"Obtained {relic} relic and " if relic else ""
    return f"{relic_str}Obtained Regret."


register_event(
    EventSpec(
        event_id="Big Fish",
        description=(
            "A big fish appears!  You may rest and heal, strengthen your "
            "vitality, or take a relic at the cost of a cursed card."
        ),
        choices=[
            EventChoice(label="Heal 33% of max HP.", effect=_big_fish_heal),
            EventChoice(label="Gain 5 Max HP.", effect=_big_fish_max_hp),
            EventChoice(
                label="Obtain a random relic.  Add Regret to your deck.",
                effect=_big_fish_relic,
            ),
        ],
    )
)


# --- 2. The Cleric -------------------------------------------------------------
# C++: choice 0 = pay 35 gold, heal 25% max HP; choice 1 = pay 50 gold, remove card; choice 2 = leave

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
                label="Pay 50 gold: Remove a card from your deck.",
                effect=_cleric_remove,
                requires_card_removal=True,
            ),
            EventChoice(label="Leave.", effect=_cleric_leave),
        ],
    )
)


# --- 3. Dead Adventurer --------------------------------------------------------
# C++: multi-phase. 3 shuffled rewards [gold, nothing, relic]. Random elite.
# Loot: encounter chance = phase * 25 + 25%.
# If encounter: fight elite, get combined remaining rewards.
# If safe: gold=30, relic=tier-based, card slot=nothing.
# Leave: end event.

_da_state: dict = {}


def _dead_adventurer_setup(rng: RNG) -> dict:
    """Initialize Dead Adventurer event state."""
    rewards = [0, 1, 2]  # 0=gold, 1=nothing, 2=relic
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
        # Fight the elite — collect remaining gold + relic rewards
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
        desc += " + card reward)"
        return desc

    else:
        # Safe — collect current reward
        reward = rewards[phase]
        result_desc = f"Looted safely (phase {phase + 1}/3). "

        if reward == 0:
            character.gold += 30
            result_desc += "Found 30 gold."
        elif reward == 2:
            relic = roll_elite_relic(rng, owned=character.relics)
            if relic:
                character.add_relic(relic)
                result_desc += f"Found {relic} relic."
            else:
                result_desc += "No relics available."
        else:
            # reward == 1: NOTHING (C++ gives nothing for safe-loot card slot)
            result_desc += "Found nothing."

        state["phase"] = phase + 1
        if state["phase"] >= 3:
            result_desc += " The corpse has been fully looted."
        return result_desc


def _dead_adventurer_leave(character: "Character", rng: RNG) -> str:
    _da_state["phase"] = 3  # End the event
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


# --- 4. Golden Idol ------------------------------------------------------------
# C++: 5 choices — relic, leave, Injury card, 25% HP damage, 8% max HP loss

def _golden_idol_relic(character: "Character", rng: RNG) -> str:
    character.add_relic("Golden Idol")
    return "Obtained Golden Idol relic."


def _golden_idol_leave(character: "Character", rng: RNG) -> str:
    return "You leave the idol."


def _golden_idol_injury(character: "Character", rng: RNG) -> str:
    character.add_card("Injury")
    return "Obtained Injury."


def _golden_idol_damage(character: "Character", rng: RNG) -> str:
    damage = _pct_max_hp(character, 0.25)
    _damage_player(character, damage)
    return f"Took {damage} damage."


def _golden_idol_lose_max_hp(character: "Character", rng: RNG) -> str:
    loss = _pct_max_hp(character, 0.08)
    _lose_max_hp(character, loss)
    return f"Lost {loss} Max HP."


register_event(
    EventSpec(
        event_id="Golden Idol",
        description=(
            "You discover a golden idol atop a pedestal.  You may take the idol, "
            "suffer its curses, or walk away."
        ),
        choices=[
            EventChoice(label="Take the Golden Idol relic.", effect=_golden_idol_relic),
            EventChoice(label="Leave.", effect=_golden_idol_leave),
            EventChoice(label="Obtain Injury.", effect=_golden_idol_injury),
            EventChoice(
                label="Take 25% of max HP as damage.",
                effect=_golden_idol_damage,
            ),
            EventChoice(
                label="Lose 8% max HP.",
                effect=_golden_idol_lose_max_hp,
            ),
        ],
    )
)


# --- 5. Wing Statue ------------------------------------------------------------
# C++: choice 0 = take 7 damage + remove card; choice 1 = gain 50–80 gold; choice 2 = leave

def _wing_statue_remove(character: "Character", rng: RNG) -> str:
    _damage_player(character, 7)
    return "WING_STATUE_REMOVAL"


def _wing_statue_gold(character: "Character", rng: RNG) -> str:
    gold_amt = rng.randint(50, 80)
    character.gold += gold_amt
    return f"Gained {gold_amt} gold."


def _wing_statue_leave(character: "Character", rng: RNG) -> str:
    return "You leave the statue undisturbed."


register_event(
    EventSpec(
        event_id="Wing Statue",
        description=(
            "A winged statue radiates a purifying aura.  You may sacrifice "
            "your blood to cleanse your deck, take its gold offering, or leave."
        ),
        choices=[
            EventChoice(
                label="Take 7 damage.  Remove a card from your deck.",
                effect=_wing_statue_remove,
                requires_card_removal=True,
            ),
            EventChoice(label="Gain 50-80 gold.", effect=_wing_statue_gold),
            EventChoice(label="Leave.", effect=_wing_statue_leave),
        ],
    )
)


# --- 6. World of Goop ----------------------------------------------------------
# C++: choice 0 = take 11 damage + gain 75 gold; choice 1 = lose 20–50 gold

def _world_of_goop_damage(character: "Character", rng: RNG) -> str:
    _damage_player(character, 11)
    character.gold += 75
    return "Took 11 damage.  Gained 75 gold."


def _world_of_goop_lose_gold(character: "Character", rng: RNG) -> str:
    loss = min(character.gold, rng.randint(20, 50))
    character.gold -= loss
    return f"Lost {loss} gold."


register_event(
    EventSpec(
        event_id="World of Goop",
        description=(
            "A massive puddle of goop blocks your path.  You can wade through "
            "it for gold at the cost of your health, or pay to go around."
        ),
        choices=[
            EventChoice(
                label="Take 11 damage.  Gain 75 gold.",
                effect=_world_of_goop_damage,
            ),
            EventChoice(
                label="Lose 20-50 gold.",
                effect=_world_of_goop_lose_gold,
            ),
        ],
    )
)


# --- 7. The Ssssserpent --------------------------------------------------------
# C++: choice 0 = gain 175 gold + Doubt card; choice 1 = leave

def _ssssserpent_gold(character: "Character", rng: RNG) -> str:
    character.gold += 175
    character.add_card("Doubt")
    return "Gained 175 gold.  Obtained Doubt."


def _ssssserpent_leave(character: "Character", rng: RNG) -> str:
    return "You decline the serpent's offer."


register_event(
    EventSpec(
        event_id="The Ssssserpent",
        description=(
            "A serpent offers you great wealth... for a price.  "
            "You may take its gold but your mind will be clouded with doubt."
        ),
        choices=[
            EventChoice(
                label="Gain 175 gold.  Add Doubt to your deck.",
                effect=_ssssserpent_gold,
            ),
            EventChoice(label="Leave.", effect=_ssssserpent_leave),
        ],
    )
)


# --- 8. Living Wall ------------------------------------------------------------
# C++: choice 0 = remove card; choice 1 = transform card; choice 2 = upgrade card

def _living_wall_remove(character: "Character", rng: RNG) -> str:
    return "LIVING_WALL_REMOVE"


def _living_wall_transform(character: "Character", rng: RNG) -> str:
    return "LIVING_WALL_TRANSFORM"


def _living_wall_upgrade(character: "Character", rng: RNG) -> str:
    return "LIVING_WALL_UPGRADE"


register_event(
    EventSpec(
        event_id="Living Wall",
        description=(
            "A wall of living stone blocks your path.  It offers to reshape "
            "your abilities — remove a burden, transform a skill, or empower one."
        ),
        choices=[
            EventChoice(
                label="Remove a card from your deck.",
                effect=_living_wall_remove,
                requires_card_removal=True,
            ),
            EventChoice(
                label="Transform a card in your deck.",
                effect=_living_wall_transform,
                requires_card_transform=True,
            ),
            EventChoice(
                label="Upgrade a card in your deck.",
                effect=_living_wall_upgrade,
                requires_card_upgrade=True,
            ),
        ],
    )
)


# --- 9. Hypnotizing Colored Mushrooms -----------------------------------------
# C++: choice 0 = fight two Fungi Beasts → gold (20–30) + Odd Mushroom relic + card reward
#       choice 1 = gain 99 gold (non-A15)
# Post-combat rewards applied by orchestrator.

def _mushrooms_fight(character: "Character", rng: RNG) -> str:
    return "FIGHT_MUSHROOMS"


def _mushrooms_gold(character: "Character", rng: RNG) -> str:
    character.gold += 99
    return "Gained 99 gold."


register_event(
    EventSpec(
        event_id="Hypnotizing Colored Mushrooms",
        description=(
            "Hypnotic colored mushrooms surround you.  You can either eat them "
            "and fight the mushroom creatures for valuable rewards, or simply "
            "gather the gold scattered around them."
        ),
        choices=[
            EventChoice(
                label=(
                    "Eat the mushrooms and fight (two Fungi Beasts). "
                    "Reward: gold + Odd Mushroom relic + card."
                ),
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


# --- 10. Scrap Ooze -----------------------------------------------------------
# C++: choice 0 = take 3 damage, escalating relic chance (25% + 10%/attempt)
#       Repeats until relic obtained or player leaves.
#       choice 1 = leave

_ooze_state: dict = {}


def _scrap_ooze_setup() -> dict:
    return {"attempts": 0, "done": False}


def _scrap_ooze_dig(character: "Character", rng: RNG) -> str:
    state = _ooze_state
    _damage_player(character, 3)
    attempts = state.get("attempts", 0)

    relic_chance = 25 + attempts * 10
    roll = rng.randint(0, 99)

    if roll < relic_chance:
        relic = roll_elite_relic(rng, owned=character.relics)
        if relic:
            character.add_relic(relic)
            state["done"] = True
            return f"Took 3 damage.  Found {relic} relic!"
        # No relics available
        state["done"] = True
        return "Took 3 damage.  No relics available."

    state["attempts"] = attempts + 1
    return f"Took 3 damage.  No relic yet... (chance was {relic_chance}%)"


def _scrap_ooze_leave(character: "Character", rng: RNG) -> str:
    _ooze_state["done"] = True
    return "You leave the ooze alone."


register_event(
    EventSpec(
        event_id="Scrap Ooze",
        description=(
            "A strange ooze holds a shimmering relic.  You can reach into the "
            "ooze to try to extract it (taking damage each time), but your "
            "chances improve with each attempt."
        ),
        choices=[
            EventChoice(
                label="Reach in (take 3 damage, escalating relic chance).",
                effect=_scrap_ooze_dig,
            ),
            EventChoice(label="Leave.", effect=_scrap_ooze_leave),
        ],
        multi_phase=True,
    )
)


# --- 11. Shining Light --------------------------------------------------------
# C++: choice 0 = take 20% max HP damage, then upgrade 2 random cards; choice 1 = leave

def _shining_light_step(character: "Character", rng: RNG) -> str:
    damage = _pct_max_hp(character, 0.20)
    _damage_player(character, damage)
    upgraded = []
    for _ in range(2):
        result = _upgrade_random_card(character, rng)
        if result is not None:
            upgraded.append(result)
    if not upgraded:
        return f"Took {damage} damage.  No cards to upgrade."
    return f"Took {damage} damage.  Upgraded {', '.join(upgraded)}."


def _shining_light_leave(character: "Character", rng: RNG) -> str:
    return "You avoid the light."


register_event(
    EventSpec(
        event_id="Shining Light",
        description=(
            "A brilliant light shines through the canopy.  You may step into "
            "it to empower your cards at the cost of your health."
        ),
        choices=[
            EventChoice(
                label="Step into the light.  Take 20% max HP damage.  Upgrade 2 random cards.",
                effect=_shining_light_step,
            ),
            EventChoice(label="Leave.", effect=_shining_light_leave),
        ],
    )
)


# ---------------------------------------------------------------------------
# Event definitions — Act 1 Shrines (6)
# ---------------------------------------------------------------------------

# --- 12. Match and Keep --------------------------------------------------------
# C++: complex memory card game. Generates 6 unique cards, duplicates to 12,
# shuffles into 4×3 grid. Player has 5 attempts to match pairs.
# Each matched pair adds both copies to deck.
# Card pool: rare, uncommon, common (character), colorless uncommon, curse, starter.
# Simplified: generate cards from pools, add them to deck.

def _match_and_keep_play(character: "Character", rng: RNG) -> str:
    """Simplified Match and Keep: generate 5 cards from mixed pools."""
    cards_added: list[str] = []

    # 1 rare from character pool
    rares = pool(character.character_class, Rarity.RARE)
    if rares:
        cards_added.append(rng.choice(rares))

    # 1 uncommon from character pool
    uncommons = pool(character.character_class, Rarity.UNCOMMON)
    if uncommons:
        cards_added.append(rng.choice(uncommons))

    # 1 common from character pool
    commons = pool(character.character_class, Rarity.COMMON)
    if commons:
        cards_added.append(rng.choice(commons))

    # 1 colorless uncommon
    colorless = colorless_pool(Rarity.UNCOMMON)
    if colorless:
        cards_added.append(rng.choice(colorless))

    # 1 curse
    curses = curse_pool()
    if curses:
        cards_added.append(rng.choice(curses))

    for card in cards_added:
        character.add_card(card)

    return f"Obtained {', '.join(cards_added)}."


def _match_and_keep_leave(character: "Character", rng: RNG) -> str:
    return "You walk away from the shrine."


register_event(
    EventSpec(
        event_id="Match and Keep",
        description=(
            "A mysterious shrine challenges you to a memory game.  Match pairs "
            "of cards to add them to your deck."
        ),
        choices=[
            EventChoice(label="Play the memory game.", effect=_match_and_keep_play),
            EventChoice(label="Leave.", effect=_match_and_keep_leave),
        ],
    )
)


# --- 13. Golden Shrine ---------------------------------------------------------
# C++: choice 0 = gain 100 gold; choice 1 = gain 275 gold + Regret; choice 2 = leave

def _golden_shrine_gold(character: "Character", rng: RNG) -> str:
    character.gold += 100
    return "Gained 100 gold."


def _golden_shrine_greed(character: "Character", rng: RNG) -> str:
    character.gold += 275
    character.add_card("Regret")
    return "Gained 275 gold.  Obtained Regret."


def _golden_shrine_leave(character: "Character", rng: RNG) -> str:
    return "You leave the shrine."


register_event(
    EventSpec(
        event_id="Golden Shrine",
        description=(
            "A golden shrine glows with wealth.  You may take a modest offering, "
            "or give in to greed for greater fortune at a cost."
        ),
        choices=[
            EventChoice(label="Pray.  Gain 100 gold.", effect=_golden_shrine_gold),
            EventChoice(
                label="Desecrate.  Gain 275 gold.  Add Regret to your deck.",
                effect=_golden_shrine_greed,
            ),
            EventChoice(label="Leave.", effect=_golden_shrine_leave),
        ],
    )
)


# --- 14. Transmorgrifier -------------------------------------------------------

def _transmorgrifier_transform(character: "Character", rng: RNG) -> str:
    return "TRANSMORGRIFIER_TRANSFORM"


def _transmorgrifier_leave(character: "Character", rng: RNG) -> str:
    return "You leave the shrine."


register_event(
    EventSpec(
        event_id="Transmorgrifier",
        description=(
            "A strange shrine offers to transform one of your cards into "
            "something different."
        ),
        choices=[
            EventChoice(
                label="Transform a card in your deck.",
                effect=_transmorgrifier_transform,
                requires_card_transform=True,
            ),
            EventChoice(label="Leave.", effect=_transmorgrifier_leave),
        ],
    )
)


# --- 15. Purifier --------------------------------------------------------------

def _purifier_remove(character: "Character", rng: RNG) -> str:
    return "PURIFIER_REMOVE"


def _purifier_leave(character: "Character", rng: RNG) -> str:
    return "You leave the shrine."


register_event(
    EventSpec(
        event_id="Purifier",
        description=(
            "A purifying shrine offers to cleanse your deck of an unwanted card."
        ),
        choices=[
            EventChoice(
                label="Remove a card from your deck.",
                effect=_purifier_remove,
                requires_card_removal=True,
            ),
            EventChoice(label="Leave.", effect=_purifier_leave),
        ],
    )
)


# --- 16. Upgrade Shrine --------------------------------------------------------

def _upgrade_shrine_upgrade(character: "Character", rng: RNG) -> str:
    return "UPGRADE_SHRINE_UPGRADE"


def _upgrade_shrine_leave(character: "Character", rng: RNG) -> str:
    return "You leave the shrine."


register_event(
    EventSpec(
        event_id="Upgrade Shrine",
        description="A mystical shrine offers to strengthen one of your cards.",
        choices=[
            EventChoice(
                label="Upgrade a card in your deck.",
                effect=_upgrade_shrine_upgrade,
                requires_card_upgrade=True,
            ),
            EventChoice(label="Leave.", effect=_upgrade_shrine_leave),
        ],
    )
)


# --- 17. Wheel of Change ------------------------------------------------------
# C++: roll 0–5 → gold(100), relic, full heal, Decay card, card remove, 10% HP loss

def _wheel_of_change_spin(character: "Character", rng: RNG) -> str:
    roll = rng.randint(0, 5)

    if roll == 0:
        # Gold: act * 100 = 100 for Act 1
        character.gold += 100
        return "The wheel lands on gold!  Gained 100 gold."

    elif roll == 1:
        # Random relic (tier-based)
        relic = roll_elite_relic(rng, owned=character.relics)
        if relic:
            character.add_relic(relic)
            return f"The wheel grants a relic!  Obtained {relic}."
        return "The wheel spins... but no relics are available."

    elif roll == 2:
        # Full heal
        old_hp = character.player_hp
        character.player_hp = character.player_max_hp
        healed = character.player_max_hp - old_hp
        return f"The wheel heals you!  Restored {healed} HP."

    elif roll == 3:
        # Decay curse card
        character.add_card("Decay")
        return "The wheel curses you!  Obtained Decay."

    elif roll == 4:
        # Card removal — pick worst card automatically (simplified from C++ screen)
        worst = _pick_worst_card(character.deck)
        if worst:
            character.deck.remove(worst)
            return f"The wheel strips away {worst} from your deck."
        return "The wheel spins... but your deck is empty."

    else:  # roll == 5
        # Lose 10% current HP
        loss = _pct_max_hp(character, 0.10)
        _damage_player(character, loss)
        return f"The wheel saps your strength!  Lost {loss} HP."


register_event(
    EventSpec(
        event_id="Wheel of Change",
        description=(
            "A massive wheel stands before you, covered in cryptic symbols. "
            "Spin it and let fate decide your reward... or punishment."
        ),
        choices=[
            EventChoice(label="Spin the wheel.", effect=_wheel_of_change_spin),
        ],
    )
)
