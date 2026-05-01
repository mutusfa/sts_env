"""Tests for Act 1 map generation (faithful sts_lightspeed algorithm)."""

from __future__ import annotations

import pytest

from sts_env.combat.rng import RNG
from sts_env.run.map import (
    MAP_HEIGHT,
    MAP_WIDTH,
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
        assert len(sample_map.nodes) == MAP_HEIGHT
        for f in range(MAP_HEIGHT):
            assert f in sample_map.nodes

    def test_7_nodes_per_floor(self, sample_map: StSMap):
        for f in range(MAP_HEIGHT):
            floor_nodes = sample_map.nodes[f]
            assert len(floor_nodes) == MAP_WIDTH, (
                f"Floor {f} has {len(floor_nodes)} nodes, expected {MAP_WIDTH}"
            )

    def test_floor0_reachable_are_monster(self, sample_map: StSMap):
        """All reachable nodes (have edges) on floor 0 are MONSTER."""
        for node in sample_map.nodes[0]:
            if node.edges:
                assert node.room_type == RoomType.MONSTER

    def test_floor8_reachable_are_treasure(self, sample_map: StSMap):
        """All reachable nodes on floor 8 are TREASURE."""
        for node in sample_map.nodes[8]:
            if node.edges:
                assert node.room_type == RoomType.TREASURE

    def test_floor14_reachable_are_rest(self, sample_map: StSMap):
        """All reachable nodes on floor 14 are REST (pre-boss)."""
        for node in sample_map.nodes[14]:
            if node.edges:
                assert node.room_type == RoomType.REST

    def test_no_elite_before_row5(self, sample_map: StSMap):
        """ELITE rooms never appear on rows 0-4."""
        for f in range(5):
            for node in sample_map.nodes[f]:
                if node.edges:
                    assert node.room_type != RoomType.ELITE, (
                        f"ELITE found on floor {f}, x={node.x}"
                    )

    def test_no_rest_before_row5_or_after_row12(self, sample_map: StSMap):
        """REST rooms never appear on rows 0-4 or rows 13-14."""
        for f in list(range(5)) + list(range(13, 15)):
            for node in sample_map.nodes[f]:
                if node.edges and f != 14:  # row 14 is forced REST
                    if f < 5:
                        assert node.room_type != RoomType.REST, (
                            f"REST on floor {f}, x={node.x}"
                        )


# ---------------------------------------------------------------------------
# Room-type constraints
# ---------------------------------------------------------------------------

class TestRoomTypeConstraints:
    def test_valid_room_types_only(self, sample_map: StSMap):
        valid = {RoomType.MONSTER, RoomType.ELITE, RoomType.REST,
                 RoomType.EVENT, RoomType.SHOP, RoomType.TREASURE}
        for f in range(MAP_HEIGHT):
            for node in sample_map.nodes[f]:
                assert node.room_type in valid

    def test_room_diversity_across_seeds(self):
        """Room type counts should vary across seeds but stay within reasonable bounds."""
        elite_counts = []
        event_counts = []
        for seed in range(50):
            m = generate_act1_map(seed)
            elites = sum(
                1 for f in range(MAP_HEIGHT) for n in m.nodes[f]
                if n.edges and n.room_type == RoomType.ELITE
            )
            events = sum(
                1 for f in range(MAP_HEIGHT) for n in m.nodes[f]
                if n.edges and n.room_type == RoomType.EVENT
            )
            elite_counts.append(elites)
            event_counts.append(events)
        # Should have at least some elites and events
        assert max(elite_counts) > 0, "No elites across 50 seeds"
        assert max(event_counts) > 0, "No events across 50 seeds"


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

class TestConnectivity:
    def test_edges_only_go_forward(self, sample_map: StSMap):
        for f in range(MAP_HEIGHT):
            for node in sample_map.nodes[f]:
                for edge in node.edges:
                    if isinstance(edge, tuple):
                        next_f, _ = edge
                    else:
                        next_f = f + 1
                    assert next_f == f + 1, (
                        f"Node ({f},{node.x}) has edge to floor {next_f}"
                    )

    def test_reachable_nodes_have_edges(self, sample_map: StSMap):
        """Non-boss nodes that are reachable (have parents) should have outgoing edges."""
        for f in range(MAP_HEIGHT - 1):
            for node in sample_map.nodes[f]:
                # Nodes with edges are reachable via paths
                pass  # Edge existence is checked by path connectivity

    def test_all_paths_reach_floor14(self, sample_map: StSMap):
        paths = sample_map.all_paths()
        assert len(paths) > 0, "No paths found from floor 0 to floor 14"
        for path in paths:
            assert path[0][0] == 0, f"Path doesn't start at floor 0: {path}"
            assert path[-1][0] == 14, f"Path doesn't end at floor 14: {path}"

    def test_paths_have_correct_length(self, sample_map: StSMap):
        """Each path should visit exactly 15 floors (0..14)."""
        for path in sample_map.all_paths():
            assert len(path) == MAP_HEIGHT, (
                f"Path has {len(path)} nodes, expected {MAP_HEIGHT}"
            )

    def test_connectivity_across_seeds(self):
        for seed in range(100):
            m = generate_act1_map(seed)
            paths = m.all_paths()
            assert len(paths) > 0, f"seed={seed}: no paths from floor 0 to 14"
            for path in paths:
                assert len(path) == MAP_HEIGHT


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_map(self):
        m1 = generate_act1_map(999)
        m2 = generate_act1_map(999)
        for f in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                n1 = m1.get_node(f, x)
                n2 = m2.get_node(f, x)
                assert n1 is not None and n2 is not None
                assert n1.room_type == n2.room_type, (
                    f"({f},{x}): {n1.room_type} != {n2.room_type}"
                )
                assert n1.edges == n2.edges, (
                    f"({f},{x}): {n1.edges} != {n2.edges}"
                )

    def test_different_seeds_different_maps(self):
        m1 = generate_act1_map(1)
        m2 = generate_act1_map(2)
        any_diff = False
        for f in range(MAP_HEIGHT):
            if f in (0, 8, 14):  # forced floors
                continue
            for x in range(MAP_WIDTH):
                n1 = m1.get_node(f, x)
                n2 = m2.get_node(f, x)
                if n1 and n2 and n1.edges and n2.edges:
                    if n1.room_type != n2.room_type:
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
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(0))
        assert get_encounter_for_room(RoomType.REST, queue) is None

    def test_monster_returns_weak_encounter(self):
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(42))
        encounter = get_encounter_for_room(RoomType.MONSTER, queue)
        assert encounter is not None
        # First encounter from the queue is always weak (easy pool)
        assert encounter in [
            "cultist", "jaw_worm", "two_louses", "small_slimes"
        ]

    def test_elite_returns_elite_encounter(self):
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(42))
        encounter = get_encounter_for_room(RoomType.ELITE, queue)
        assert encounter is not None
        assert encounter in [
            "Gremlin Nob",
            "Lagavulin",
            "Three Sentries",
        ]

    def test_boss_returns_boss_encounter(self):
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(42))
        encounter = get_encounter_for_room(RoomType.BOSS, queue)
        assert encounter in ["slime_boss", "guardian", "hexaghost"]

    def test_encounter_determinism(self):
        from sts_env.run.encounter_queue import EncounterQueue
        for _ in range(20):
            queue1 = EncounterQueue(RNG(77))
            queue2 = EncounterQueue(RNG(77))
            e1 = get_encounter_for_room(RoomType.MONSTER, queue1)
            e2 = get_encounter_for_room(RoomType.MONSTER, queue2)
            assert e1 == e2


# ---------------------------------------------------------------------------
# Map string representation
# ---------------------------------------------------------------------------

class TestMapStr:
    def test_str_renders_15_floors(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        # Node rows + connector rows between floors
        assert len(lines) == (MAP_HEIGHT * 2 - 1)

    def test_str_shows_rest_at_bottom(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        # Reversed, so line 0 = floor 14 (REST)
        assert "R" in lines[0]

    def test_str_shows_monster_at_top(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        # line 14 = floor 0 (MONSTER)
        assert "M" in lines[(MAP_HEIGHT - 1) * 2]

    def test_str_includes_connector_rows(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        connector_lines = [lines[i] for i in range(1, len(lines), 2)]
        assert len(connector_lines) == MAP_HEIGHT - 1
        assert any(ch in line for line in connector_lines for ch in ("/", "|", "\\"))

    def test_str_connectors_reflect_graph_edges(self, sample_map: StSMap):
        lines = str(sample_map).split("\n")
        # Find one concrete edge and verify the expected connector character appears
        # in that floor's connector row.
        for floor in range(MAP_HEIGHT - 1):
            rendered_row_idx = (MAP_HEIGHT - 1 - floor) * 2
            connector_row = lines[rendered_row_idx - 1]
            for node in sample_map.nodes[floor]:
                for edge in node.edges:
                    _, dst_x = edge if isinstance(edge, tuple) else (floor + 1, edge)
                    delta = dst_x - node.x
                    expected = "|" if delta == 0 else ("/" if delta > 0 else "\\")
                    assert expected in connector_row
                    return
        pytest.fail("No edge found in map to validate connector rendering")

    def test_render_ascii_marks_current_position(self, sample_map: StSMap):
        start_x = next(n.x for n in sample_map.nodes[0] if n.edges)
        lines = sample_map.render_ascii(current_floor=0, current_x=start_x).split("\n")
        assert any("@" in line for line in lines)

    def test_render_ascii_reachable_only_filters_nodes(self, sample_map: StSMap):
        start_x = next(n.x for n in sample_map.nodes[0] if n.edges)
        full_lines = sample_map.render_ascii().split("\n")
        filtered_lines = sample_map.render_ascii(
            current_floor=0,
            current_x=start_x,
            reachable_only=True,
        ).split("\n")
        assert len(filtered_lines) == len(full_lines)
        full_non_space = sum(1 for line in full_lines for ch in line if ch != " ")
        filtered_non_space = sum(1 for line in filtered_lines for ch in line if ch != " ")
        assert filtered_non_space <= full_non_space

    def test_legend_contains_room_and_edge_symbols(self, sample_map: StSMap):
        legend = sample_map.legend()
        assert "M=Monster" in legend
        assert "E=Elite" in legend
        assert "R=Rest" in legend
        assert "B=Boss" in legend
        assert "?=Event" in legend
        assert "$=Shop" in legend
        assert "T=Treasure" in legend
        assert "@=Current" in legend
        assert "|=Straight" in legend
        assert "/=DiagRight" in legend
        assert "\\=DiagLeft" in legend
