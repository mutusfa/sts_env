"""Tests for sts_env.run.orchestrator — run_act1, RunResult, RunAgentProtocol."""

from __future__ import annotations

import pytest

from sts_env.combat import Combat
from sts_env.combat.rng import RNG
from sts_env.combat.state import Action
from sts_env.run.character import Character
from sts_env.run.rooms import RestChoice, RestResult
from sts_env.run.orchestrator import RunResult, run_act1, _apply_combat_rewards
from sts_env.run.rewards import ALL_RELICS, BOSS_RELICS


# ---------------------------------------------------------------------------
# Minimal MockAgent — satisfies RunAgentProtocol via duck typing
# ---------------------------------------------------------------------------

class _MockAgent:
    """Deterministic stub: always picks first option, ends-turn-spam in combat."""

    def run_battle(self, combat: Combat) -> int:
        obs = combat.reset()
        while not obs.done:
            actions = combat.valid_actions()
            if not actions:
                break
            combat.step(actions[0])
        obs = combat.observe()
        return combat.damage_taken

    def pick_neow(self, options):
        return options[0].choice

    def plan_route(self, sts_map, character, seed):
        path = []
        floor0_nodes = sts_map.nodes.get(0, [])
        candidates = [n for n in floor0_nodes if n.edges]
        if not candidates:
            return path
        current = (0, candidates[0].x)
        path.append(current)
        while True:
            f, x = current
            node = sts_map.get_node(f, x)
            if node is None or not node.edges:
                break
            next_coord = node.edges[0]
            path.append(next_coord)
            if next_coord[0] == 14:
                break
            current = next_coord
        return path

    def pick_card(self, character, card_choices, upcoming_encounters, seed, **kwargs):
        return card_choices[0] if card_choices else None

    def pick_rest_choice(self, character, **kwargs):
        return RestResult(choice=RestChoice.REST)

    def pick_event_choice(self, event, character, **kwargs):
        return 0

    def pick_card_to_remove(self, character, **kwargs):
        return None

    def shop(self, inventory, character):
        return None

    def pick_boss_relic(self, character, choices):
        return choices[0] if choices else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunResult:
    def test_fields_exist(self):
        r = RunResult(
            victory=True,
            floors_cleared=5,
            total_floors=5,
            final_hp=60,
            max_hp=80,
            damage_taken_total=20,
            max_hp_gained_total=0,
        )
        assert r.victory is True
        assert r.floors_cleared == 5
        assert r.total_floors == 5
        assert r.final_hp == 60
        assert r.max_hp == 80
        assert r.damage_taken_total == 20
        assert r.max_hp_gained_total == 0
        assert r.damage_per_floor == []
        assert r.encounter_types == []
        assert r.cards_added == []
        assert r.potions_gained == []


class TestRunAct1Map:
    """Integration tests for run_act1 with the map-based loop."""

    @pytest.mark.slow
    def test_returns_run_result(self):
        agent = _MockAgent()
        result = run_act1(42, agent, use_map=True)
        assert isinstance(result, RunResult)

    @pytest.mark.slow
    def test_floors_cleared_positive(self):
        agent = _MockAgent()
        result = run_act1(42, agent, use_map=True)
        assert result.floors_cleared >= 0

    @pytest.mark.slow
    def test_encounter_types_populated(self):
        agent = _MockAgent()
        result = run_act1(42, agent, use_map=True)
        assert len(result.encounter_types) > 0

    @pytest.mark.slow
    def test_deterministic(self):
        agent1 = _MockAgent()
        agent2 = _MockAgent()
        r1 = run_act1(123, agent1, use_map=True)
        r2 = run_act1(123, agent2, use_map=True)
        assert r1.floors_cleared == r2.floors_cleared
        assert r1.encounter_types == r2.encounter_types
        assert r1.damage_taken_total == r2.damage_taken_total

    @pytest.mark.slow
    def test_final_hp_zero_if_died(self):
        agent = _MockAgent()
        result = run_act1(42, agent, use_map=True)
        if not result.victory:
            assert result.final_hp == 0


class TestRunAct1Linear:
    """Integration tests for run_act1 with the legacy linear loop."""

    @pytest.mark.slow
    def test_returns_run_result(self):
        agent = _MockAgent()
        result = run_act1(42, agent, use_map=False)
        assert isinstance(result, RunResult)

    @pytest.mark.slow
    def test_total_floors_8(self):
        agent = _MockAgent()
        result = run_act1(42, agent, use_map=False)
        assert result.total_floors == 8


class TestFloorObserver:
    """FloorObserver hook is called for each floor."""

    @pytest.mark.slow
    def test_observer_floor_scope_called(self):
        from contextlib import contextmanager

        floors_seen = []

        class _Observer:
            @contextmanager
            def floor_scope(self, floor, room_type, character):
                floors_seen.append((floor, room_type))
                yield {}

        agent = _MockAgent()
        observer = _Observer()
        result = run_act1(42, agent, use_map=False, observer=observer)
        assert len(floors_seen) > 0

    @pytest.mark.slow
    def test_observer_receives_attrs(self):
        """Orchestrator fills attrs dict passed via yield."""
        from contextlib import contextmanager

        received_attrs = []

        class _Observer:
            @contextmanager
            def floor_scope(self, floor, room_type, character):
                attrs = {}
                yield attrs
                received_attrs.append(dict(attrs))

        agent = _MockAgent()
        observer = _Observer()
        run_act1(42, agent, use_map=False, observer=observer)
        assert len(received_attrs) > 0
        # Combat floors should have damage_taken in attrs
        combat_attrs = [a for a in received_attrs if "damage_taken" in a]
        assert len(combat_attrs) > 0


# ---------------------------------------------------------------------------
# _apply_combat_rewards relic logic
# ---------------------------------------------------------------------------

def _base_result() -> RunResult:
    return RunResult(
        victory=False, floors_cleared=0, total_floors=1,
        final_hp=80, max_hp=80, damage_taken_total=0, max_hp_gained_total=0,
    )


class TestApplyCombatRewardsRelics:
    """Relic drops should be handled inside _apply_combat_rewards, not separately."""

    def test_elite_grants_one_relic(self):
        character = Character.ironclad()
        initial = list(character.relics)
        _apply_combat_rewards(character, _base_result(), "elite", 42, RNG(42), _MockAgent())
        new_relics = [r for r in character.relics if r not in initial]
        assert len(new_relics) == 1
        assert new_relics[0] in ALL_RELICS

    def test_boss_calls_pick_boss_relic_and_adds_it(self):
        picked: list[str] = []

        class _SpyAgent(_MockAgent):
            def pick_boss_relic(self, character, choices):
                picked.extend(choices)
                return choices[0] if choices else None

        character = Character.ironclad()
        initial = list(character.relics)
        _apply_combat_rewards(character, _base_result(), "boss", 42, RNG(42), _SpyAgent())
        assert picked, "pick_boss_relic should have been called"
        assert all(r in BOSS_RELICS for r in picked)
        new_relics = [r for r in character.relics if r not in initial]
        assert len(new_relics) == 1
        assert new_relics[0] in BOSS_RELICS

    def test_monster_does_not_grant_relic(self):
        character = Character.ironclad()
        initial = list(character.relics)
        _apply_combat_rewards(character, _base_result(), "monster", 42, RNG(42), _MockAgent())
        assert character.relics == initial
