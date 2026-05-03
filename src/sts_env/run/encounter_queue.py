"""Pre-generated encounter queues matching real StS behavior.

In the real game, encounter lists are pre-generated at the start of each act
and consumed sequentially as the player enters monster/elite rooms. This avoids
repetition and creates a natural weak→strong progression.

Monster list (Act 1):
  - 3 weak encounters (from the easy pool, no 2-back repeat)
  - 1 "first strong" encounter (with thematic constraints vs last weak)
  - 12 strong encounters (from the hard pool, no 2-back repeat)
  = 16 total

Elite list (Act 1):
  - 10 entries from {Gremlin Nob, Lagavulin, Three Sentries}
  - No consecutive repeats

Both lists regenerate when exhausted:
  - Monsters regenerate with only strong encounters (12)
  - Elites regenerate with the same rules

Reference: sts_lightspeed/src/game/GameContext.cpp
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..combat.rng import RNG

# ---------------------------------------------------------------------------
# Act 1 encounter pools
# ---------------------------------------------------------------------------

# Weak (easy) hallway encounters — encounter_id strings matching builder.py
WEAK_POOL: list[str] = ["cultist", "jaw_worm", "two_louses", "small_slimes"]
WEAK_WEIGHTS: list[float] = [0.25, 0.25, 0.25, 0.25]

# Strong (hard) hallway encounters
STRONG_POOL: list[str] = [
    "gremlin_gang",
    "lots_of_slimes",
    "red_slaver",
    "exordium_thugs",
    "exordium_wildlife",
    "blue_slaver",
    "looter",
    "large_slime",
    "three_louse",
    "two_fungi_beasts",
]
STRONG_WEIGHTS: list[float] = [
    1 / 16, 1 / 16, 1 / 16,       # uncommon: gremlin_gang, lots_of_slimes, red_slaver
    1.5 / 16, 1.5 / 16,            # exordium_thugs, exordium_wildlife
    2 / 16, 2 / 16, 2 / 16,        # common: blue_slaver, looter, large_slime
    2 / 16, 2 / 16,                 # common: three_louse, two_fungi_beasts
]

# Elite encounters — display labels matching builder.py _ELITE_POOLS
ELITE_POOL: list[str] = ["Gremlin Nob", "Lagavulin", "Three Sentries"]

# Boss encounters — encounter_id strings matching builder.py
BOSS_POOL: list[str] = ["slime_boss", "guardian", "hexaghost"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _weighted_pick(rng: RNG, items: list[str], weights: list[float]) -> str:
    """Pick a random item using weighted selection."""
    total = sum(weights)
    roll = rng.random() * total
    cumulative = 0.0
    for item, w in zip(items, weights):
        cumulative += w
        if roll < cumulative:
            return item
    return items[-1]


def _populate_monster_list(
    rng: RNG,
    pool: list[str],
    weights: list[float],
    count: int,
    existing: list[str] | None = None,
) -> list[str]:
    """Generate monster list entries with the 2-back no-repeat rule.

    A new entry must differ from the previous entry AND the one before that.
    This matches the C++ populateMonsterList() logic.
    """
    result = list(existing) if existing else []
    target = len(result) + count
    safety = 0
    while len(result) < target and safety < 10_000:
        pick = _weighted_pick(rng, pool, weights)
        # No repeat of the last entry
        if result and pick == result[-1]:
            safety += 1
            continue
        # No repeat of 2-back entry
        if len(result) >= 2 and pick == result[-2]:
            safety += 1
            continue
        result.append(pick)
        safety = 0
    return result


def _pick_first_strong(rng: RNG, existing: list[str]) -> str:
    """Generate the first strong encounter with thematic constraints.

    Matches C++ populateFirstStrongEnemy():
      - Large Slime / Lots of Slimes can't follow Small Slimes
      - Three Louse can't follow Two Louses
    """
    last = existing[-1] if existing else None
    while True:
        pick = _weighted_pick(rng, STRONG_POOL, STRONG_WEIGHTS)
        if pick in ("large_slime", "lots_of_slimes") and last == "small_slimes":
            continue
        if pick == "three_louse" and last == "two_louses":
            continue
        return pick


def _generate_elite_list(rng: RNG) -> list[str]:
    """Generate 10 elite encounters with no consecutive repeats."""
    result: list[str] = []
    while len(result) < 10:
        idx = rng.randint(0, len(ELITE_POOL) - 1)
        pick = ELITE_POOL[idx]
        if result and pick == result[-1]:
            continue
        result.append(pick)
    return result


# ---------------------------------------------------------------------------
# EncounterQueue
# ---------------------------------------------------------------------------

class EncounterQueue:
    """Pre-generated encounter queues for a single act.

    Created at act start with a seeded RNG. Monster and elite encounters
    are consumed sequentially via next_monster() / next_elite().
    """

    def __init__(self, rng: RNG) -> None:
        self._rng = rng
        self.monster_list: list[str] = []
        self.monster_offset: int = 0
        self.elite_list: list[str] = []
        self.elite_offset: int = 0
        self.boss: str = ""
        self._generate_all()

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate_all(self) -> None:
        """Pre-generate all encounter lists for the act."""
        self._generate_monsters()
        self._generate_elites()
        self._pick_boss()

    def _generate_monsters(self) -> None:
        """Generate: 3 weak + 1 first-strong + 12 strong = 16 total."""
        self.monster_list = []
        self.monster_offset = 0

        # 3 weak encounters (2-back no-repeat among themselves)
        weak = _populate_monster_list(self._rng, WEAK_POOL, WEAK_WEIGHTS, 3)
        self.monster_list = weak

        # 1 first-strong with thematic constraints vs last weak
        first_strong = _pick_first_strong(self._rng, self.monster_list)
        self.monster_list.append(first_strong)

        # 12 more strong (2-back no-repeat, continuing from the list)
        strong = _populate_monster_list(
            self._rng, STRONG_POOL, STRONG_WEIGHTS, 12,
            existing=self.monster_list,
        )
        # _populate_monster_list returns the full list (existing + new)
        self.monster_list = strong

    def _generate_strong_only(self) -> None:
        """Regenerate with only strong encounters (when list exhausted)."""
        self.monster_list = _populate_monster_list(
            self._rng, STRONG_POOL, STRONG_WEIGHTS, 12,
        )
        self.monster_offset = 0

    def _generate_elites(self) -> None:
        """Generate 10 elite encounters (no consecutive repeats)."""
        self.elite_list = _generate_elite_list(self._rng)
        self.elite_offset = 0

    def _pick_boss(self) -> None:
        """Randomly pick a boss from the pool."""
        self.boss = self._rng.choice(BOSS_POOL)

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def next_monster(self) -> str:
        """Pop next hallway monster from the queue.

        Regenerates with strong-only encounters when the list is exhausted.
        """
        if self.monster_offset >= len(self.monster_list):
            self._generate_strong_only()
        result = self.monster_list[self.monster_offset]
        self.monster_offset += 1
        return result

    def next_elite(self) -> str:
        """Pop next elite from the queue. Regenerates when exhausted."""
        if self.elite_offset >= len(self.elite_list):
            self._generate_elites()
        result = self.elite_list[self.elite_offset]
        self.elite_offset += 1
        return result

    def get_boss(self) -> str:
        """Return the pre-selected boss encounter_id."""
        return self.boss

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def is_weak(self, encounter_id: str) -> bool:
        """Check if an encounter is from the weak (easy) pool."""
        return encounter_id in WEAK_POOL

    # ------------------------------------------------------------------
    # Open-knowledge helper (no hidden state)
    # ------------------------------------------------------------------

    def possible_encounters(
        self,
        hallway_seen: list[str],
        elites_seen: list[str],
    ) -> dict[str, list[str] | str]:
        """Return the set of encounters that could still appear, using only
        information a real player would know (pools + rules + what they've seen).

        This does **not** peek at the pre-generated queue — it derives the
        possible set from pool composition and filtering rules.

        Parameters
        ----------
        hallway_seen:
            Ordered list of hallway encounter_ids the player has already fought.
        elites_seen:
            Ordered list of elite encounter_ids the player has already fought.

        Returns
        -------
        Dict with keys:

        - ``"monster_weak"`` — weak pool entries still possible for the next
          hallway fight (filtered by 2-back no-repeat).  Empty if we're past
          the weak phase (≥ 3 weak fights seen).
        - ``"monster_strong"`` — strong pool entries still possible for the
          next hallway fight (filtered by 2-back no-repeat and thematic
          constraints on the first-strong transition).
        - ``"elite"`` — elite pool entries possible for the next elite fight
          (filtered by no-consecutive-repeat).
        - ``"boss"`` — the fixed boss encounter_id.

        Example
        -------
        >>> eq.possible_encounters(
        ...     hallway_seen=["cultist", "jaw_worm"],
        ...     elites_seen=["Gremlin Nob"],
        ... )
        {
            "monster_weak": ["two_louses", "small_slimes"],
            "monster_strong": ["gremlin_gang", "lots_of_slimes", ...],
            "elite": ["Lagavulin", "Three Sentries"],
            "boss": "hexaghost",
        }
        """
        # --- Hallway monsters ---
        weak_seen = [e for e in hallway_seen if e in WEAK_POOL]
        still_in_weak_phase = len(weak_seen) < 3

        if still_in_weak_phase and hallway_seen:
            # 2-back no-repeat: exclude last 2 seen
            exclude = set(hallway_seen[-2:])
            possible_weak = [e for e in WEAK_POOL if e not in exclude]
        elif still_in_weak_phase:
            # No hallway fights yet — full weak pool is possible
            possible_weak = list(WEAK_POOL)
        else:
            possible_weak: list[str] = []

        if hallway_seen:
            # Strong pool: 2-back no-repeat from ALL seen (weak+strong)
            exclude_strong = set(hallway_seen[-2:])

            # If the last weak fight was small_slimes, apply thematic constraint
            # on the first-strong entry: large_slime and lots_of_slimes excluded.
            # After the first-strong, this constraint no longer applies.
            strong_seen_count = len(
                [e for e in hallway_seen if e not in WEAK_POOL]
            )
            if strong_seen_count == 0 and len(weak_seen) == 3:
                # Next fight is first-strong — check thematic constraints
                last_weak = hallway_seen[-1] if hallway_seen else None
                if last_weak == "small_slimes":
                    exclude_strong.update(
                        e for e in ("large_slime", "lots_of_slimes")
                        if e in STRONG_POOL
                    )
                if last_weak == "two_louses":
                    exclude_strong.update(
                        e for e in ("three_louse",)
                        if e in STRONG_POOL
                    )

            possible_strong = [
                e for e in STRONG_POOL if e not in exclude_strong
            ]
        else:
            # No hallway fights seen yet — next is from weak pool, but also
            # list full strong pool for reference
            possible_strong = list(STRONG_POOL)

        # --- Elites: no consecutive repeat ---
        if elites_seen:
            last_elite = elites_seen[-1]
            possible_elite = [e for e in ELITE_POOL if e != last_elite]
        else:
            possible_elite = list(ELITE_POOL)

        return {
            "monster_weak": possible_weak,
            "monster_strong": possible_strong,
            "elite": possible_elite,
            "boss": self.boss,
        }
