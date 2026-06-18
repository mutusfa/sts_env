"""Card and potion reward system for after winning combat.

After winning a combat encounter, the player receives:
  - 3 card choices drawn from the character's card pool (with rarity weighting).
  - An optional potion reward (40% chance).
  - Gold based on the encounter type.

Card rarity mechanics mirror C++ GameContext::createCardReward / rollCardRarity:
  - MONSTER: rare 3 %, uncommon 37 %, common 60 %  (roll = rng(0..99) + factor)
  - ELITE:   rare 10 %, uncommon 40 %, common 50 %
  - BOSS:    100 % rare
  - A persistent ``card_rarity_factor`` (pity counter) adjusts the roll:
      COMMON drawn → max(factor - 1, -40)
      RARE drawn   → factor reset to 5
      UNCOMMON     → no change
  - Within a single reward, re-roll until all card IDs are distinct.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from ..combat.card_pools import pool
from ..combat.cards import CardColor, Rarity
from ..combat.potion_pools import roll_random_potion
from ..helpers import below_d100, d100_threshold, roll_d100
from .bus import RunEvent

if TYPE_CHECKING:
    from ..combat.rng import RNG
    from .bus import RunEventBus
    from .rng_streams import RunRNG


# ---------------------------------------------------------------------------
# Room type enum (mirrors C++ Room, used for rarity roll thresholds)
# ---------------------------------------------------------------------------

class Room(Enum):
    MONSTER = auto()
    ELITE = auto()
    BOSS = auto()
    REST = auto()
    EVENT = auto()


# ---------------------------------------------------------------------------
# Rarity roll — matches C++ GameContext::rollCardRarity
# ---------------------------------------------------------------------------

# Thresholds: (rare_chance, uncommon_chance) per room type — proportions in [0, 1].
# roll = rng.randint(0, 99) + card_rarity_factor
# if roll < d100_threshold(rare)          → RARE
# elif roll < d100_threshold(rare+uncommon) → UNCOMMON
# else                                    → COMMON
_RARE_CHANCE: dict[Room, float] = {
    Room.MONSTER: 0.03,
    Room.ELITE:   0.10,
    Room.BOSS:    1.0,  # always rare
    Room.REST:    0.03,
    Room.EVENT:   0.03,
}
_UNCOMMON_CHANCE: dict[Room, float] = {
    Room.MONSTER: 0.37,
    Room.ELITE:   0.40,
    Room.BOSS:    0.0,
    Room.REST:    0.37,
    Room.EVENT:   0.37,
}

_FACTOR_FLOOR = -40


def roll_card_rarity(rng: "RNG", room: Room, factor: int) -> tuple[Rarity, int]:
    """Roll one card rarity and return (rarity, updated_factor).

    Mirrors C++ GameContext::rollCardRarity + the inline factor update in
    createCardReward.
    """
    rare_chance = _RARE_CHANCE[room]
    uncommon_chance = _UNCOMMON_CHANCE[room]
    rare_thresh = d100_threshold(rare_chance)
    uncommon_thresh = d100_threshold(rare_chance + uncommon_chance)

    roll = roll_d100(rng) + factor

    if roll < rare_thresh:
        rarity = Rarity.RARE
        new_factor = 5
    elif roll < uncommon_thresh:
        rarity = Rarity.UNCOMMON
        new_factor = factor  # unchanged
    else:
        rarity = Rarity.COMMON
        new_factor = max(factor - 1, _FACTOR_FLOOR)

    return rarity, new_factor


# ---------------------------------------------------------------------------
# Card reward generation
# ---------------------------------------------------------------------------

def roll_card_rewards(
    rng: "RNG",
    color: CardColor = CardColor.RED,
    room: Room = Room.MONSTER,
    card_rarity_factor: int = 0,
    event_bus: "RunEventBus | None" = None,
    relics: list[str] | None = None,
) -> tuple[list[str], int]:
    """Return (card_ids, new_card_rarity_factor) for one reward screen.

    Mirrors C++ GameContext::createCardReward:
    - Per-slot rarity rolls using the pity counter.
    - Re-roll card ID (within the same rarity) until it does not duplicate an
      already-chosen card in this reward (C++ hasDuplicate loop).
    - BOSS room is always 100 % rare.

    The caller is responsible for persisting the returned factor on the run
    state (e.g. ``character.card_rarity_factor = new_factor``).
    """
    num_cards = 3
    if event_bus is not None:
        payload = event_bus.emit(RunEvent.CARD_REWARD_COUNT, count=num_cards)
        num_cards = payload["count"]

    rewards: list[str] = []
    factor = card_rarity_factor

    for _ in range(num_cards):
        rarity, factor = roll_card_rarity(rng, room, factor)
        card_pool = pool(color, rarity)
        if not card_pool:
            continue

        # Re-roll until unique within this reward (C++ hasDuplicate loop).
        # Safety guard: if pool is exhausted (tiny pool), accept duplicate.
        card = rng.choice(card_pool)
        attempts = 0
        while card in rewards and attempts < len(card_pool):
            card = rng.choice(card_pool)
            attempts += 1
        rewards.append(card)

    if relics:
        from .relic_hooks import apply_egg_upgrade

        rewards = [apply_egg_upgrade(c, relics) for c in rewards]

    return rewards, factor


# ---------------------------------------------------------------------------
# Potion rewards
# ---------------------------------------------------------------------------

# 40% base chance to receive a potion after combat (pity timer in roll_potion_reward)
_POTION_DROP_BASE = 0.40
POTION_PITY_STEP = 0.10


def roll_potion_reward(
    rng: "RNG",
    *,
    potion_chance: float = 0.0,
    reward_screen_size: int = 0,
    has_white_beast_statue: bool = False,
) -> tuple[str | None, float]:
    """Return (potion_id or None, updated_potion_chance).

    Mirrors GameContext::addPotionRewards.
    """
    chance = _POTION_DROP_BASE + potion_chance
    if has_white_beast_statue:
        chance = 1.0
    if reward_screen_size >= 4:
        chance = 0.0

    if roll_d100(rng) >= d100_threshold(chance):
        return None, potion_chance + POTION_PITY_STEP

    return roll_random_potion(rng), potion_chance - POTION_PITY_STEP


# ---------------------------------------------------------------------------
# Relic rewards (elite drops)
# ---------------------------------------------------------------------------

class RelicTier(Enum):
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    BOSS = auto()
    SHOP = auto()


# Ironclad pools aligned with C++ RelicPools.h::Ironclad (33 common / 30 uncommon /
# 28 rare / 22 boss). Previously Python used a 60-ID subset with several tier
# misplacements (e.g. Shuriken/Sundial as common, PenNib as uncommon).
COMMON_RELICS: list[str] = [
    "Whetstone", "TheBoot", "BloodVial", "MealTicket", "PenNib", "Akabeko",
    "Lantern", "RegalPillow", "BagOfPreparation", "AncientTeaSet", "SmilingMask",
    "PotionBelt", "PreservedInsect", "Omamori", "MawBank", "ArtOfWar",
    "ToyOrnithopter", "CeramicFish", "Vajra", "CentennialPuzzle", "Strawberry",
    "HappyFlower", "OddlySmoothStone", "WarPaint", "BronzeScales", "JuzuBracelet",
    "DreamCatcher", "Nunchaku", "TinyChest", "Orichalcum", "Anchor",
    "BagOfMarbles", "RedSkull",
]

UNCOMMON_RELICS: list[str] = [
    "BottledTornado", "Sundial", "Kunai", "Pear", "BlueCandle", "EternalFeather",
    "StrikeDummy", "SingingBowl", "Matryoshka", "InkBottle", "TheCourier",
    "FrozenEgg", "OrnamentalFan", "BottledLightning", "GremlinHorn", "HornCleat",
    "ToxicEgg", "LetterOpener", "QuestionCard", "BottledFlame", "Shuriken",
    "MoltenEgg", "MeatOnTheBone", "DarkstonePeriapt", "MummifiedHand",
    "Pantograph", "WhiteBeastStatue", "MercuryHourglass", "SelfFormingClay",
    "PaperPhrog",
]

RARE_RELICS: list[str] = [
    "Ginger", "OldCoin", "BirdFacedUrn", "UnceasingTop", "Torii", "StoneCalendar",
    "Shovel", "WingBoots", "ThreadAndNeedle", "Turnip", "IceCream", "Calipers",
    "LizardTail", "PrayerWheel", "Girya", "DeadBranch", "DuVuDoll", "Pocketwatch",
    "Mango", "IncenseBurner", "GamblingChip", "PeacePipe", "CaptainsWheel",
    "FossilizedHelix", "TungstenRod", "MagicFlower", "CharonsAshes", "ChampionBelt",
]

ALL_RELICS = COMMON_RELICS + UNCOMMON_RELICS + RARE_RELICS

_RELIC_POOL: dict[RelicTier, list[str]] = {
    RelicTier.COMMON: COMMON_RELICS,
    RelicTier.UNCOMMON: UNCOMMON_RELICS,
    RelicTier.RARE: RARE_RELICS,
}

BOSS_RELICS: list[str] = [
    "FusionHammer", "VelvetChoker", "RunicDome", "SlaversCollar", "SneckoEye",
    "PandorasBox", "CursedKey", "BustedCrown", "Ectoplasm", "TinyHouse", "Sozu",
    "PhilosophersStone", "Astrolabe", "BlackStar", "SacredBark", "EmptyCage",
    "RunicPyramid", "CallingBell", "CoffeeDripper", "BlackBlood", "MarkOfPain",
    "RunicCube",
]


_ELITE_RELIC_COMMON = 0.50
_ELITE_RELIC_RARE = 0.83  # roll >= threshold → RARE (~17%)


def roll_elite_relic_tier(rng: "RNG") -> RelicTier:
    """Roll the rarity tier for an elite relic drop.

    Mirrors C++ returnRandomRelicTierElite:
      roll < 0.50  → COMMON   (~50%)
      roll >= 0.83 → RARE     (~17%)
      else         → UNCOMMON (~33%)
    """
    roll = roll_d100(rng)
    if below_d100(roll, _ELITE_RELIC_COMMON):
        return RelicTier.COMMON
    elif roll >= d100_threshold(_ELITE_RELIC_RARE):
        return RelicTier.RARE
    else:
        return RelicTier.UNCOMMON


def roll_elite_relic(rng: "RNG", owned: list[str] | None = None) -> str | None:
    """Return a relic ID for an elite drop, rolling tier first then picking from that pool.

    Tier probabilities mirror C++ returnRandomRelicTierElite:
    50% COMMON, 33% UNCOMMON, 17% RARE. Falls back up the tier ladder
    (COMMON→UNCOMMON→RARE) if the rolled tier's pool is exhausted.
    Returns None only if every relic across all tiers is owned.
    """
    owned_set = set(owned) if owned else set()
    tier = roll_elite_relic_tier(rng)

    # Try tier, then cascade up (mirrors C++ pool-empty fallback logic).
    for t in _tier_fallback_order(tier):
        available = [r for r in _RELIC_POOL[t] if r not in owned_set]
        if available:
            return rng.choice(available)
    return None


def _tier_fallback_order(tier: RelicTier) -> list[RelicTier]:
    """Return tier priority order starting from tier, cascading up to RARE."""
    order = [RelicTier.COMMON, RelicTier.UNCOMMON, RelicTier.RARE]
    start = order.index(tier)
    return order[start:]


def roll_boss_relic_choices(
    rng: "RNG",
    owned: list[str] | None = None,
    count: int = 3,
) -> list[str]:
    """Return up to *count* distinct boss relics not already owned by the player.

    Mirrors the pattern used by ``roll_elite_relic``: shuffle by drawing without
    replacement via the provided RNG so results are deterministic.  Returns an
    empty list if the entire pool is already owned.
    """
    owned_set = set(owned) if owned else set()
    available = [r for r in BOSS_RELICS if r not in owned_set]
    choices: list[str] = []
    while available and len(choices) < count:
        pick = rng.choice(available)
        choices.append(pick)
        available.remove(pick)
    return choices


# ---------------------------------------------------------------------------
# Combined combat reward offer
# ---------------------------------------------------------------------------

COMBAT_GOLD: dict[Room, int] = {
    Room.MONSTER: 10,
    Room.ELITE: 30,
    Room.BOSS: 20,
}


@dataclass
class CombatRewardOffer:
    """The full set of rewards offered after winning a combat encounter."""

    card_choices: list[str]
    potion: str | None
    gold: int


def roll_combat_reward_offer(
    run_rng: "RunRNG",
    floor: int,
    room: Room,
    card_rarity_factor: int = 0,
    potion_chance: float = 0.0,
    event_bus: "RunEventBus | None" = None,
    relics: list[str] | None = None,
) -> tuple[CombatRewardOffer, int, float]:
    """Roll a complete post-combat reward offer.

    Returns ``(offer, new_card_rarity_factor, new_potion_chance)``.
    """
    rng = run_rng.derive("card_reward", floor)
    card_choices, new_factor = roll_card_rewards(
        rng,
        room=room,
        card_rarity_factor=card_rarity_factor,
        event_bus=event_bus,
        relics=relics,
    )
    # One card-reward screen + one gold line (C++ Rewards counters, not card count).
    reward_screen_size = 2
    has_wbs = relics is not None and "WhiteBeastStatue" in relics
    potion, new_potion_chance = roll_potion_reward(
        rng,
        potion_chance=potion_chance,
        reward_screen_size=reward_screen_size,
        has_white_beast_statue=has_wbs,
    )
    gold = COMBAT_GOLD.get(room, COMBAT_GOLD[Room.MONSTER])
    return (
        CombatRewardOffer(card_choices=card_choices, potion=potion, gold=gold),
        new_factor,
        new_potion_chance,
    )
