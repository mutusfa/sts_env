"""Act 1 map generation for Slay the Spire.

Generates a branching map with 15 floors (0..14):
- Floor 0:  MONSTER (easy hallway)
- Floor 7:  REST
- Floor 14: BOSS
- Other floors: weighted random {MONSTER 60%, ELITE 20%, REST 20%}
- No two consecutive all-Rest floors (except forced floors 7/14).
- Each floor has 3 nodes (x-position 0, 1, 2).
- Each node connects to 1-3 nodes on the next floor.
- All paths from floor 0 reach floor 14.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Sequence

from ..combat.rng import RNG


# ---------------------------------------------------------------------------
# Room types
# ---------------------------------------------------------------------------

class RoomType(Enum):
    MONSTER = auto()
    ELITE = auto()
    REST = auto()
    BOSS = auto()
    EVENT = auto()      # v2
    SHOP = auto()       # v2
    TREASURE = auto()   # v2


# ---------------------------------------------------------------------------
# Map data structures
# ---------------------------------------------------------------------------

@dataclass
class MapNode:
    floor: int
    x: int  # 0, 1, 2
    room_type: RoomType
    edges: list[tuple[int, int]] = field(default_factory=list)
    """(floor, x) targets of outgoing edges."""


@dataclass
class StSMap:
    nodes: dict[int, list[MapNode]]  # floor → list of nodes
    seed: int

    def get_node(self, floor: int, x: int) -> MapNode | None:
        for n in self.nodes.get(floor, []):
            if n.x == x:
                return n
        return None

    def all_paths(self) -> list[list[tuple[int, int]]]:
        """Enumerate all root-to-boss paths (floor 0 → floor 14)."""
        paths: list[list[tuple[int, int]]] = []

        def dfs(floor: int, x: int, current_path: list[tuple[int, int]]) -> None:
            node = self.get_node(floor, x)
            if node is None:
                return
            current_path.append((floor, x))
            if floor == 14:
                paths.append(list(current_path))
            else:
                for next_floor, next_x in node.edges:
                    dfs(next_floor, next_x, current_path)
            current_path.pop()

        for node in self.nodes.get(0, []):
            dfs(0, node.x, [])
        return paths

    def __str__(self) -> str:
        symbols = {
            RoomType.MONSTER: "M",
            RoomType.ELITE: "E",
            RoomType.REST: "R",
            RoomType.BOSS: "B",
        }
        lines: list[str] = []
        for floor in sorted(self.nodes.keys()):
            parts: list[str] = []
            for x in range(3):
                n = self.get_node(floor, x)
                if n is None:
                    parts.append("   ")
                else:
                    parts.append(f"[{symbols.get(n.room_type, '?')}]")
            lines.append(f"F{floor:2d}: {' '.join(parts)}")
        return "\n".join(reversed(lines))


# ---------------------------------------------------------------------------
# Map generation
# ---------------------------------------------------------------------------

_MAP_SEED_SALT = 0xBEEFCA7E


def generate_act1_map(seed: int) -> StSMap:
    """Generate an Act 1 map with 15 floors (0..14)."""
    rng = RNG(seed ^ _MAP_SEED_SALT % (2**31))

    nodes: dict[int, list[MapNode]] = {}

    # --- Assign room types ---
    # StS1 Act 1 approximate room weights (mid-floors):
    #   MONSTER 35%, ELITE 15%, REST 12%, EVENT 15%, SHOP 8%, TREASURE 15%
    _ROOM_WEIGHTS = [
        (0.35, RoomType.MONSTER),
        (0.50, RoomType.ELITE),
        (0.62, RoomType.REST),
        (0.77, RoomType.EVENT),
        (0.85, RoomType.SHOP),
        (1.00, RoomType.TREASURE),
    ]

    for floor in range(15):
        floor_nodes: list[MapNode] = []
        for x in range(3):
            if floor == 0:
                rt = RoomType.MONSTER
            elif floor == 7:
                rt = RoomType.REST
            elif floor == 14:
                rt = RoomType.BOSS
            else:
                roll = rng.random()
                rt = RoomType.MONSTER  # default fallback
                for threshold, room_type in _ROOM_WEIGHTS:
                    if roll < threshold:
                        rt = room_type
                        break
            floor_nodes.append(MapNode(floor, x, rt))
        nodes[floor] = floor_nodes

    # --- Enforce: no 2 consecutive all-Rest floors (except forced 7/14) ---
    for floor in range(1, 15):
        if floor == 7 or floor == 14:
            continue
        prev_all_rest = all(
            n.room_type == RoomType.REST for n in nodes.get(floor - 1, [])
        )
        if prev_all_rest:
            for n in nodes[floor]:
                if n.room_type == RoomType.REST:
                    n.room_type = RoomType.MONSTER

    # --- Generate edges: floors 0..12 → floor+1 ---
    for floor in range(13):
        next_floor = floor + 1
        next_nodes = nodes.get(next_floor, [])
        if not next_nodes:
            continue
        indices = list(range(len(next_nodes)))
        for node in nodes[floor]:
            num_edges = min(rng.randint(1, 3), len(next_nodes))
            targets = rng.sample(indices, num_edges)
            for t in targets:
                node.edges.append((next_floor, next_nodes[t].x))

    # --- Floor 13 → Floor 14 (boss): every node connects to all boss nodes ---
    boss_nodes = nodes.get(14, [])
    for node in nodes.get(13, []):
        for bn in boss_nodes:
            node.edges.append((14, bn.x))

    return StSMap(nodes=nodes, seed=seed)


# ---------------------------------------------------------------------------
# Encounter selection helpers
# ---------------------------------------------------------------------------

# Act 1 encounter IDs (string keys matching encounter factory names).
_ACT1_WEAK_ENCOUNTERS = [
    "cultist",
    "jaw_worm",
    "two_louses",
    "small_slimes",
]

_ACT1_ELITE_ENCOUNTERS = [
    "Gremlin Nob",
    "Lagavulin",
    "Three Sentries",
]

_ACT1_STRONG_ENCOUNTERS = [
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

_ACT1_STRONG_WEIGHTS = [1.0, 1.0, 1.0, 1.5, 1.5, 2.0, 2.0, 2.0, 2.0, 2.0]
_ACT1_STRONG_TOTAL = sum(_ACT1_STRONG_WEIGHTS)

_ACT1_BOSS_ENCOUNTERS = ["slime_boss", "guardian", "hexaghost"]


def get_encounter_for_room(room_type: RoomType, rng: RNG) -> str | None:
    """Pick an encounter ID string for the given room type.

    Returns ``None`` for REST rooms (no combat).
    """
    if room_type == RoomType.REST:
        return None

    if room_type == RoomType.MONSTER:
        idx = rng.randint(0, len(_ACT1_WEAK_ENCOUNTERS) - 1)
        return _ACT1_WEAK_ENCOUNTERS[idx]

    if room_type == RoomType.ELITE:
        return _ACT1_ELITE_ENCOUNTERS[rng.randint(0, len(_ACT1_ELITE_ENCOUNTERS) - 1)]

    if room_type == RoomType.BOSS:
        return rng.choice(_ACT1_BOSS_ENCOUNTERS)

    # EVENT / SHOP / TREASURE — v2
    return None
