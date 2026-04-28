"""Act 1 map generation for Slay the Spire — faithful to sts_lightspeed.

Generates a branching map with 15 floors (rows 0..14) and 7 columns.

Algorithm (from sts_lightspeed/src/game/Map.cpp):
1. Create 6 independent paths from row 0 → row 14, each starting at a random
   column. Paths walk left/straight/right with ancestor-gap constraints.
   All paths converge to column 3 at row 14.
2. Filter redundant edges from the first row.
3. Assign fixed rooms: row 0 = MONSTER, row 8 = TREASURE, row 14 = REST.
4. Build a room pool from percentages of total reachable nodes, shuffle it.
5. Assign rooms row-by-row with spreading constraints (no same-room parent
   or sibling, no ELITE on rows ≤ 4, no REST on rows ≤ 4 or ≥ 13).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto

from ..combat.rng import RNG


# ---------------------------------------------------------------------------
# Constants (matching sts_lightspeed)
# ---------------------------------------------------------------------------

MAP_HEIGHT = 15
MAP_WIDTH = 7
PATH_DENSITY = 6

SHOP_ROOM_CHANCE = 0.05
REST_ROOM_CHANCE = 0.12
TREASURE_ROOM_CHANCE = 0.0
EVENT_ROOM_CHANCE = 0.22
ELITE_ROOM_CHANCE_A0 = 0.08
ELITE_ROOM_CHANCE_A1 = ELITE_ROOM_CHANCE_A0 * 1.6


# ---------------------------------------------------------------------------
# Room types
# ---------------------------------------------------------------------------

class RoomType(Enum):
    MONSTER = auto()
    ELITE = auto()
    REST = auto()
    BOSS = auto()
    EVENT = auto()
    SHOP = auto()
    TREASURE = auto()


# ---------------------------------------------------------------------------
# Map data structures
# ---------------------------------------------------------------------------

@dataclass
class MapNode:
    floor: int       # y (0-14)
    x: int           # column (0-6)
    room_type: RoomType
    edges: list[int] = field(default_factory=list)
    """Destination X values (to next row's column)."""
    parents: list[int] = field(default_factory=list)
    """Source X values (from previous row's column)."""

    def add_edge(self, dst_x: int) -> None:
        """Add edge, keeping sorted and deduplicated."""
        if dst_x in self.edges:
            return
        # Insert in sorted order
        for i, e in enumerate(self.edges):
            if dst_x < e:
                self.edges.insert(i, dst_x)
                return
        self.edges.append(dst_x)

    def add_parent(self, src_x: int) -> None:
        if src_x not in self.parents:
            self.parents.append(src_x)


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
                for edge in node.edges:
                    if isinstance(edge, tuple):
                        next_floor, next_x = edge
                    else:
                        next_floor, next_x = floor + 1, edge
                    dfs(next_floor, next_x, current_path)
            current_path.pop()

        for node in self.nodes.get(0, []):
            if node.edges:
                dfs(0, node.x, [])
        return paths

    def __str__(self) -> str:
        symbols = {
            RoomType.MONSTER: "M", RoomType.ELITE: "E", RoomType.REST: "R",
            RoomType.BOSS: "B", RoomType.EVENT: "?", RoomType.SHOP: "$",
            RoomType.TREASURE: "T",
        }
        lines: list[str] = []
        for floor in sorted(self.nodes.keys(), reverse=True):
            row_chars: list[str] = []
            for x in range(MAP_WIDTH):
                n = self.get_node(floor, x)
                if n is None or (not n.edges and not n.parents):
                    row_chars.append(" ")
                else:
                    row_chars.append(symbols.get(n.room_type, "?"))
            lines.append(f"F{floor:2d}: {' '.join(row_chars)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Path creation (faithful to sts_lightspeed)
# ---------------------------------------------------------------------------

def _get_common_ancestor(nodes: dict[int, dict[int, MapNode]], x1: int, x2: int, y: int) -> int:
    """Check if nodes at (x1,y) and (x2,y) share a common parent."""
    if y < 0:
        return -1
    l_x, r_x = (x1, x2) if x1 < x2 else (x2, x1)
    row = nodes.get(y, {})
    l_node = row.get(l_x)
    r_node = row.get(r_x)
    if not l_node or not r_node or not l_node.parents or not r_node.parents:
        return -1
    # left node's max parent == right node's min parent → common ancestor
    left_max = max(l_node.parents)
    right_min = min(r_node.parents)
    if left_max == right_min:
        return left_max
    return -1


def _choose_path_parent_loop_randomizer(
    nodes: dict[int, dict[int, MapNode]], rng: RNG, cur_x: int, cur_y: int, new_x: int
) -> int:
    """If destination node has parents sharing a common ancestor with cur_x, nudge new_x."""
    next_row = nodes.get(cur_y + 1, {})
    dest = next_row.get(new_x)
    if not dest:
        return new_x

    for parent_x in dest.parents:
        if cur_x == parent_x:
            continue
        if _get_common_ancestor(nodes, parent_x, cur_x, cur_y) == -1:
            continue
        # Common ancestor found — nudge away
        if new_x > cur_x:
            new_x = cur_x + rng.randint(-1, 0)
            if new_x < 0:
                new_x = cur_x
        elif new_x == cur_x:
            new_x = cur_x + rng.randint(-1, 1)
            if new_x > MAP_WIDTH - 1:
                new_x = cur_x - 1
            elif new_x < 0:
                new_x = cur_x + 1
        else:
            new_x = cur_x + rng.randint(0, 1)
            if new_x > MAP_WIDTH - 1:
                new_x = cur_x
    return new_x


def _choose_path_adjust_new_x(
    nodes: dict[int, dict[int, MapNode]], cur_x: int, cur_y: int, new_x: int
) -> int:
    """Prevent edge crossings with neighbor nodes' edges."""
    cur_row = nodes.get(cur_y, {})
    if cur_x > 0:
        left_node = cur_row.get(cur_x - 1)
        if left_node and left_node.edges:
            left_max_edge = max(left_node.edges)
            if left_max_edge > new_x:
                new_x = left_max_edge

    if cur_x < MAP_WIDTH - 1:
        right_node = cur_row.get(cur_x + 1)
        if right_node and right_node.edges:
            right_min_edge = min(right_node.edges)
            if right_min_edge < new_x:
                new_x = right_min_edge
    return new_x


def _choose_new_path(
    nodes: dict[int, dict[int, MapNode]], rng: RNG, cur_x: int, cur_y: int
) -> int:
    """Choose the next X for a path step."""
    if cur_x == 0:
        lo, hi = 0, 1
    elif cur_x == MAP_WIDTH - 1:
        lo, hi = -1, 0
    else:
        lo, hi = -1, 1

    new_x = cur_x + rng.randint(lo, hi)
    new_x = _choose_path_parent_loop_randomizer(nodes, rng, cur_x, cur_y, new_x)
    new_x = _choose_path_adjust_new_x(nodes, cur_x, cur_y, new_x)
    return new_x


def _create_path_iteration(
    nodes: dict[int, dict[int, MapNode]], rng: RNG, start_x: int
) -> None:
    """Create a single path from row 0 → row 14 starting at start_x."""
    cur_x = start_x
    for cur_y in range(MAP_HEIGHT - 1):
        new_x = _choose_new_path(nodes, rng, cur_x, cur_y)
        nodes[cur_y][cur_x].add_edge(new_x)
        nodes[cur_y + 1][new_x].add_parent(cur_x)
        cur_x = new_x


def _create_paths(nodes: dict[int, dict[int, MapNode]], rng: RNG) -> None:
    """Create PATH_DENSITY paths through the map."""
    first_x = rng.randint(0, MAP_WIDTH - 1)
    _create_path_iteration(nodes, rng, first_x)

    for i in range(1, PATH_DENSITY):
        start_x = rng.randint(0, MAP_WIDTH - 1)
        # Second path must differ from first
        while start_x == first_x and i == 1:
            start_x = rng.randint(0, MAP_WIDTH - 1)
        _create_path_iteration(nodes, rng, start_x)


def _filter_redundant_edges_first_row(nodes: dict[int, dict[int, MapNode]]) -> None:
    """From row 0, remove edges to destinations already targeted by a lower-x source."""
    visited: set[int] = set()
    row0 = nodes.get(0, {})
    for src_x in range(MAP_WIDTH):
        node = row0.get(src_x)
        if not node:
            continue
        # Process edges in reverse to safely remove
        new_edges: list[int] = []
        for dst_x in node.edges:
            if dst_x not in visited:
                visited.add(dst_x)
                new_edges.append(dst_x)
            else:
                # Remove parent from destination node
                next_row = nodes.get(1, {})
                dest = next_row.get(dst_x)
                if dest and src_x in dest.parents:
                    dest.parents.remove(src_x)
        node.edges = new_edges


# ---------------------------------------------------------------------------
# Room assignment (faithful to sts_lightspeed)
# ---------------------------------------------------------------------------

def _get_room_counts_and_assign_fixed(nodes: dict[int, dict[int, MapNode]]) -> tuple[float, int]:
    """Assign fixed rooms (row 0=MONSTER, row 8=TREASURE, row 14=REST).
    
    Returns (total_count, unassigned_count).
    """
    total = 0.0
    unassigned = 0

    for row in range(MAP_HEIGHT):
        for node in nodes[row].values():
            # A node is reachable if it has outgoing edges or parents
            # Row 14 has parents but no edges (boss convergence removed)
            if not node.edges and not node.parents:
                continue

            if row == 0:
                node.room_type = RoomType.MONSTER
                total += 1
            elif row == 8:
                node.room_type = RoomType.TREASURE
                total += 1
            elif row == 14:
                node.room_type = RoomType.REST
                total += 1
            elif row == 13:
                # restRowBug — counted as unassigned but NOT added to total
                unassigned += 1
            else:
                unassigned += 1
                total += 1

    return total, unassigned


def _fill_room_array(counts_total: float, unassigned: int, elite_chance: float) -> list[RoomType]:
    """Build shuffled room pool based on total node count."""
    shop_count = round(counts_total * SHOP_ROOM_CHANCE)
    rest_count = round(counts_total * REST_ROOM_CHANCE)
    treasure_count = round(counts_total * TREASURE_ROOM_CHANCE)
    elite_count = round(counts_total * elite_chance)
    event_count = round(counts_total * EVENT_ROOM_CHANCE)

    rooms: list[RoomType] = []
    rooms.extend([RoomType.SHOP] * shop_count)
    rooms.extend([RoomType.REST] * rest_count)
    rooms.extend([RoomType.TREASURE] * treasure_count)
    rooms.extend([RoomType.ELITE] * elite_count)
    rooms.extend([RoomType.EVENT] * event_count)
    # Fill remaining with MONSTER
    while len(rooms) < unassigned:
        rooms.append(RoomType.MONSTER)

    return rooms


def _shuffle_rooms(rooms: list[RoomType], rng: RNG) -> None:
    """Fisher-Yates shuffle."""
    for i in range(len(rooms) - 1, 0, -1):
        j = rng.randint(0, i)
        rooms[i], rooms[j] = rooms[j], rooms[i]


def _assign_rooms(nodes: dict[int, dict[int, MapNode]], rng: RNG, ascension: int = 0) -> None:
    """Assign rooms to all unassigned nodes with spreading constraints."""
    total, unassigned = _get_room_counts_and_assign_fixed(nodes)
    elite_chance = ELITE_ROOM_CHANCE_A1 if ascension > 0 else ELITE_ROOM_CHANCE_A0
    rooms = _fill_room_array(total, unassigned, elite_chance)
    _shuffle_rooms(rooms, rng)

    # Track what's been assigned for constraint checking
    # sibling_masks[x] tracks room types assigned to nodes that share a parent with column x
    # parent_masks[x] tracks room types assigned to parent of column x
    sibling_masks: list[set[RoomType]] = [set() for _ in range(MAP_WIDTH)]
    next_sibling_masks: list[set[RoomType]] = [set() for _ in range(MAP_WIDTH)]
    parent_masks: list[set[RoomType]] = [set() for _ in range(MAP_WIDTH)]
    next_parent_masks: list[set[RoomType]] = [set() for _ in range(MAP_WIDTH)]
    prev_row_rooms: dict[int, set[RoomType]] = {}  # x → room types assigned
    cur_row_rooms: dict[int, set[RoomType]] = {}

    room_idx = 0  # Current position in shuffled room array

    for row in range(MAP_HEIGHT - 1):
        prev_row_rooms = cur_row_rooms
        cur_row_rooms = {}

        # Rotate masks
        sibling_masks = next_sibling_masks
        next_sibling_masks = [set() for _ in range(MAP_WIDTH)]
        parent_masks = next_parent_masks
        next_parent_masks = [set() for _ in range(MAP_WIDTH)]

        for x in range(MAP_WIDTH):
            node = nodes[row][x]
            if not node.edges:
                continue

            # Row 0 and 8 already assigned (MONSTER / TREASURE)
            if row == 0 or row == 8:
                # Just track for next row's constraint checking
                for dst_x in node.edges:
                    next_parent_masks[dst_x].add(node.room_type)
                cur_row_rooms[x] = {node.room_type}
                continue

            # Row 7 and 13: only set cur data (not next data)
            is_rest_bug_row = (row == 13)

            # Try to assign a room from the pool
            assigned = False
            tried: set[RoomType] = set()

            for i in range(room_idx, len(rooms)):
                room = rooms[i]
                if room in tried:
                    continue
                tried.add(room)

                # Check constraints
                if room == RoomType.ELITE and row <= 4:
                    continue
                if room == RoomType.REST and (row <= 4 or row >= 13):
                    continue

                # For EVENT and MONSTER: only check siblings
                if room in (RoomType.EVENT, RoomType.MONSTER):
                    if room in sibling_masks[x]:
                        continue
                    node.room_type = room
                    cur_row_rooms[x] = cur_row_rooms.get(x, set()) | {room}
                    # Remove from pool by swapping with current idx
                    rooms[room_idx], rooms[i] = rooms[i], rooms[room_idx]
                    room_idx += 1
                    assigned = True
                    break

                # For SHOP, REST, ELITE, TREASURE: check parent AND sibling
                parent_conflict = room in parent_masks[x]
                # Also check previous row for same x
                prev_rooms_at_x = prev_row_rooms.get(x, set())
                parent_conflict = parent_conflict or (room in prev_rooms_at_x)
                sibling_conflict = room in sibling_masks[x]

                if not parent_conflict and not sibling_conflict:
                    node.room_type = room
                    cur_row_rooms[x] = cur_row_rooms.get(x, set()) | {room}
                    rooms[room_idx], rooms[i] = rooms[i], rooms[room_idx]
                    room_idx += 1
                    assigned = True
                    break

            if not assigned:
                node.room_type = RoomType.MONSTER
                cur_row_rooms[x] = cur_row_rooms.get(x, set()) | {RoomType.MONSTER}

            # Update masks for next row
            if is_rest_bug_row:
                pass  # Don't propagate masks from row 13
            elif len(node.edges) == 1:
                for dst_x in node.edges:
                    next_parent_masks[dst_x].add(node.room_type)
            else:
                sibling_mask: set[RoomType] = set()
                for dst_x in node.edges:
                    sibling_mask.add(node.room_type)  # All edges share this sibling
                    next_sibling_masks[dst_x] |= sibling_mask
                    next_parent_masks[dst_x].add(node.room_type)


# ---------------------------------------------------------------------------
# Map generation
# ---------------------------------------------------------------------------

def generate_act1_map(seed: int, ascension: int = 0) -> StSMap:
    """Generate an Act 1 map with 15 floors (0..14), 7 columns.

    Faithfully implements the sts_lightspeed map generation algorithm.
    """
    rng = RNG(seed)

    # Create 7x15 grid of nodes
    nodes: dict[int, dict[int, MapNode]] = {}
    for row in range(MAP_HEIGHT):
        nodes[row] = {}
        for x in range(MAP_WIDTH):
            nodes[row][x] = MapNode(floor=row, x=x, room_type=RoomType.MONSTER)

    # Create 6 paths
    _create_paths(nodes, rng)

    # Filter redundant first-row edges
    _filter_redundant_edges_first_row(nodes)

    # Assign rooms with constraints
    _assign_rooms(nodes, rng, ascension)

    # Convert to list-based format for StSMap compatibility
    list_nodes: dict[int, list[MapNode]] = {}
    for row in range(MAP_HEIGHT):
        row_list = [nodes[row][x] for x in range(MAP_WIDTH)]
        # Convert edges from list[int] to list[tuple[int,int]] for compatibility
        for node in row_list:
            node.edges = [(node.floor + 1, dst_x) for dst_x in node.edges]  # type: ignore[assignment]
        list_nodes[row] = row_list

    return StSMap(nodes=list_nodes, seed=seed)


# ---------------------------------------------------------------------------
# Encounter selection helpers
# ---------------------------------------------------------------------------

def get_encounter_for_room(
    room_type: RoomType,
    encounter_queue: "EncounterQueue",
) -> str | None:
    """Pick an encounter ID string for the given room type.

    Uses the pre-generated encounter queue for faithful StS behaviour:
    hallway monsters are consumed sequentially from a flat list (weak first,
    then strong), elites from a separate queue, and the boss was pre-selected.

    Returns ``None`` for REST/SHOP/EVENT/TREASURE rooms (non-combat).
    """
    from .encounter_queue import EncounterQueue  # noqa: F811

    if room_type == RoomType.REST:
        return None

    if room_type == RoomType.MONSTER:
        return encounter_queue.next_monster()

    if room_type == RoomType.ELITE:
        return encounter_queue.next_elite()

    if room_type == RoomType.BOSS:
        return encounter_queue.get_boss()

    # EVENT / SHOP / TREASURE — handled by runner, not encounter factory
    return None
