"""Tests for Act 1 map generation."""

from __future__ import annotations

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.map import (
    RoomType,
    StSMap,
    generate_act1_map,
    get_encounter_for_room,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_map() -> StSMap:
    return generate_act1_map(42)


@pytest.fixture
def another_map() -> StSMap:
    return generate_act1_map(12345)


# ---------------------------------------------------------------------------
# Floor structure
# ---------------------------------------------------------------------------

class TestFloorStructure:
    def test_15_floors_generated(self, sample_map: StSMap):
        assert len(sample_map.nodes) == 15
        for f in range(15):
            assert f in sample_map.nodes

    def test_3_nodes_per_floor(self, sample_map: StSMap):
        for f in range(15):
            floor_nodes = sample_map.nodes[f]
            assert len(floor_nodes) == 3, f"Floor {f} has {len(floor_nodes)} nodes"

    def test_floor0_is_monster(self, sample_map: StSMap):
        for node in sample_map.nodes[0]:
            assert node.room_type == RoomType.MONSTER

    def test_floor7_is_rest(self, sample_map: StSMap):
        for node in sample_map.nodes[7]:
            assert node.room_type == RoomType.REST

    def test_floor14_is_boss(self, sample_map: StSMap):
        for node in sample_map.nodes[14]:
            assert node.room_type == RoomType.BOSS


# ---------------------------------------------------------------------------
# Room-type constraints
# ---------------------------------------------------------------------------

class TestRoomTypeConstraints:
    def test_no_consecutive_all_rest_floors(self, sample_map: StSMap):
        """No two consecutive floors where ALL nodes are REST (except forced 7/14)."""
        for f in range(1, 15):
            prev_rest = all(n.room_type == RoomType.REST for n in sample_map.nodes[f - 1])
            curr_rest = all(n.room_type == RoomType.REST for n in sample_map.nodes[f])
            if prev_rest and curr_rest:
                # Only allowed if one of them is the forced rest floor
                assert f == 7 or f == 14, (
                    f"Floors {f-1} and {f} are both all-REST but neither is forced"
                )

    def test_no_consecutive_rest_across_seeds(self):
        """Check the constraint holds for many seeds."""
        for seed in range(200):
            m = generate_act1_map(seed)
            for f in range(1, 15):
                prev_rest = all(n.room_type == RoomType.REST for n in m.nodes[f - 1])
                if prev_rest and f not in (7, 14):
                    for node in m.nodes[f]:
                        assert node.room_type != RoomType.REST, (
                            f"seed={seed}: floor {f} has REST after all-REST floor {f-1}"
                        )

    def test_valid_room_types_only(self, sample_map: StSMap):
        valid = {RoomType.MONSTER, RoomType.ELITE, RoomType.REST, RoomType.BOSS}
        for f in range(15):
            for node in sample_map.nodes[f]:
                assert node.room_type in valid


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

class TestConnectivity:
    def test_edges_only_go_forward(self, sample_map: StSMap):
        for f in range(15):
            for node in sample_map.nodes[f]:
                for next_f, _ in node.edges:
                    assert next_f == f + 1, (
                        f"Node ({f},{node.x}) has edge to floor {next_f}"
                    )

    def test_each_node_has_at_least_one_edge(self, sample_map: StSMap):
        """Every non-boss node must have at least one outgoing edge."""
        for f in range(14):
            for node in sample_map.nodes[f]:
                assert len(node.edges) >= 1, (
                    f"Node ({f},{node.x}) has no outgoing edges"
                )

    def test_boss_nodes_have_no_edges(self, sample_map: StSMap):
        for node in sample_map.nodes[14]:
            assert len(node.edges) == 0

    def test_all_paths_reach_floor14(self, sample_map: StSMap):
        paths = sample_map.all_paths()
        assert len(paths) > 0, "No paths found from floor 0 to floor 14"
        for path in paths:
            assert path[0][0] == 0, f"Path doesn't start at floor 0: {path}"
            assert path[-1][0] == 14, f"Path doesn't end at floor 14: {path}"

    def test_all_floor0_nodes_are_starting_points(self, sample_map: StSMap):
        paths = sample_map.all_paths()
        starting_xs = {p[0][1] for p in paths}
        for node in sample_map.nodes[0]:
            assert node.x in starting_xs, (
                f"Floor 0 node x={node.x} is unreachable"
            )

    def test_paths_have_correct_length(self, sample_map: StSMap):
        """Each path should visit exactly 15 floors (0..14)."""
        for path in sample_map.all_paths():
            assert len(path) == 15, f"Path has {len(path)} nodes, expected 15: {path}"

    def test_connectivity_across_seeds(self):
        for seed in range(100):
            m = generate_act1_map(seed)
            paths = m.all_paths()
            assert len(paths) > 0, f"seed={seed}: no paths from floor 0 to 14"
            for path in paths:
                assert len(path) == 15


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_map(self):
        m1 = generate_act1_map(999)
        m2 = generate_act1_map(999)
        for f in range(15):
            for x in range(3):
                n1 = m1.get_node(f, x)
                n2 = m2.get_node(f, x)
                assert n1 is not None and n2 is not None
                assert n1.room_type == n2.room_type
                assert n1.edges == n2.edges

    def test_different_seeds_different_maps(self):
        m1 = generate_act1_map(1)
        m2 = generate_act1_map(2)
        # At least one floor should differ in room types
        any_diff = False
        for f in range(15):
            for x in range(3):
                if f in (0, 7, 14):
                    continue  # forced floors
                n1 = m1.get_node(f, x)
                n2 = m2.get_node(f, x)
                if n1 and n2 and n1.room_type != n2.room_type:
                    any_diff = True
                    break
            if any_diff:
                break
        assert any_diff, "Different seeds produced identical maps"


# ---------------------------------------------------------------------------
# Encounter selection
# ---------------------------------------------------------------------------

class TestEncounterSelection:
    def test_rest_returns_none(self):
        rng = RNG(0)
        assert get_encounter_for_room(RoomType.REST, rng) is None

    def test_monster_returns_weak_encounter(self):
        rng = RNG(42)
        encounter = get_encounter_for_room(RoomType.MONSTER, rng)
        assert encounter is not None
        assert encounter in [
            "cultist", "jaw_worm", "two_louses", "small_slimes"
        ]

    def test_elite_returns_elite_encounter(self):
        rng = RNG(42)
        encounter = get_encounter_for_room(RoomType.ELITE, rng)
        assert encounter is not None
        elites = [
            "Gremlin Nob",
            "Lagavulin",
            "Three Sentries",
        ]
        assert encounter in elites

    def test_boss_returns_boss_encounter(self):
        rng = RNG(42)
        encounter = get_encounter_for_room(RoomType.BOSS, rng)
        assert encounter in ["slime_boss"]

    def test_encounter_determinism(self):
        for _ in range(20):
            rng1 = RNG(77)
            rng2 = RNG(77)
            e1 = get_encounter_for_room(RoomType.MONSTER, rng1)
            e2 = get_encounter_for_room(RoomType.MONSTER, rng2)
            assert e1 == e2


# ---------------------------------------------------------------------------
# Map string representation
# ---------------------------------------------------------------------------

class TestMapStr:
    def test_str_renders_15_floors(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        assert len(lines) == 15

    def test_str_shows_boss_at_bottom(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        # Reversed, so line 0 = floor 14
        assert "[B]" in lines[0]

    def test_str_shows_monster_at_top(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        # line 14 = floor 0
        assert "[M]" in lines[14]
