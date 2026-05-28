"""Failing tests for the Enemy Pool Single Source refactor.

Covers:
- Pool consistency: WEAK/STRONG/ELITE_POOL derived from encounters.py factory names
- Elite factories exist in encounters.py and builder._ENCOUNTER_FACTORY_MAP
- PlayerState dataclass with ironclad_starter() classmethod
- Combat.__init__ accepts PlayerState
- Character inherits from PlayerState
- builder.build_combat passes full PlayerState (no post-construction patching)
"""

from __future__ import annotations

import pytest

from sts_env.combat import encounters
from sts_env.combat.player_state import PlayerState
from sts_env.combat.engine import Combat, IRONCLAD_STARTER
from sts_env.run import builder
from sts_env.run.encounter_queue import (
    WEAK_POOL,
    STRONG_POOL,
    ELITE_POOL,
    weighted_pick,
)
from sts_env.run.character import Character
from sts_env.combat.rng import RNG


# ---------------------------------------------------------------------------
# PlayerState
# ---------------------------------------------------------------------------

class TestPlayerState:
    def test_ironclad_starter_fields(self, starter_ironclad: PlayerState):
        assert starter_ironclad.deck == IRONCLAD_STARTER
        assert starter_ironclad.player_hp == 80
        assert starter_ironclad.player_max_hp == 80
        assert starter_ironclad.potions == []
        assert starter_ironclad.max_potion_slots == 3
        assert starter_ironclad.gold == 99
        assert "BurningBlood" in starter_ironclad.relics

    def test_classmethod_factory(self):
        ps = PlayerState.ironclad_starter()
        assert ps.deck == IRONCLAD_STARTER
        assert ps.player_hp == 80

    def test_mutable(self, starter_ironclad: PlayerState):
        starter_ironclad.player_hp = 50
        assert starter_ironclad.player_hp == 50

    def test_custom_fields(self):
        ps = PlayerState(deck=["Strike"], player_hp=40, player_max_hp=50)
        assert ps.deck == ["Strike"]
        assert ps.player_hp == 40
        assert ps.player_max_hp == 50


# ---------------------------------------------------------------------------
# Character inherits PlayerState
# ---------------------------------------------------------------------------

class TestCharacterInheritsPlayerState:
    def test_is_player_state_instance(self):
        c = Character.ironclad()
        assert isinstance(c, PlayerState)

    def test_no_combat_kwargs(self):
        """combat_kwargs() should be removed."""
        c = Character.ironclad()
        assert not hasattr(c, "combat_kwargs"), "combat_kwargs() should have been removed"


# ---------------------------------------------------------------------------
# Combat.__init__ accepts PlayerState
# ---------------------------------------------------------------------------

class TestCombatAcceptsPlayerState:
    def test_basic_construction(self, starter_ironclad: PlayerState):
        combat = Combat(starter_ironclad, ["Cultist"], seed=42)
        obs = combat.observe()
        assert obs.player_hp == 80
        assert obs.enemies[0].name == "Cultist"

    def test_custom_hp(self):
        ps = PlayerState(deck=IRONCLAD_STARTER, player_hp=50, player_max_hp=80)
        combat = Combat(ps, ["Cultist"], seed=42)
        obs = combat.observe()
        assert obs.player_hp == 50

    def test_relics_forwarded(self, starter_ironclad: PlayerState):
        combat = Combat(starter_ironclad, ["Cultist"], seed=42)
        assert "BurningBlood" in combat._state.relics

    def test_potions_forwarded(self):
        ps = PlayerState(deck=IRONCLAD_STARTER, potions=["FirePotion"])
        combat = Combat(ps, ["Cultist"], seed=42)
        obs = combat.observe()
        assert "FirePotion" in obs.potions

    def test_is_elite_flag(self, starter_ironclad: PlayerState):
        combat = Combat(starter_ironclad, ["GremlinNob"], seed=42, is_elite=True)
        assert combat._state.is_elite is True


# ---------------------------------------------------------------------------
# Elite factories in encounters.py
# ---------------------------------------------------------------------------

class TestEliteFactories:
    def test_gremlin_nob_factory(self, starter_ironclad: PlayerState):
        combat = encounters.gremlin_nob(seed=42, character=starter_ironclad)
        obs = combat.observe()
        assert obs.enemies[0].name == "GremlinNob"

    def test_lagavulin_factory(self, starter_ironclad: PlayerState):
        combat = encounters.lagavulin(seed=42, character=starter_ironclad)
        obs = combat.observe()
        assert obs.enemies[0].name == "Lagavulin"

    def test_three_sentries_factory(self, starter_ironclad: PlayerState):
        combat = encounters.three_sentries(seed=42, character=starter_ironclad)
        obs = combat.observe()
        assert len(obs.enemies) == 3
        for e in obs.enemies:
            assert e.name == "Sentry"

    def test_act1_elite_pool_exists(self):
        assert hasattr(encounters, "_ACT1_ELITE_POOL")
        labels = [label for _, label in encounters._ACT1_ELITE_POOL]
        assert "Gremlin Nob" in labels
        assert "Lagavulin" in labels
        assert "Three Sentries" in labels

    def test_act1_elite_pool_factories_match_labels(self):
        for factory, label in encounters._ACT1_ELITE_POOL:
            assert callable(factory)
            ps = PlayerState.ironclad_starter()
            combat = factory(seed=0, character=ps)
            obs = combat.observe()
            assert len(obs.enemies) >= 1


# ---------------------------------------------------------------------------
# Pool consistency: encounter_queue pools derived from encounters.py
# ---------------------------------------------------------------------------

class TestPoolConsistency:
    def test_weak_pool_matches_factory_names(self):
        factory_names = [f.__name__ for f in encounters._ACT1_WEAK_FACTORIES]
        assert WEAK_POOL == factory_names

    def test_strong_pool_matches_factory_names(self):
        factory_names = [f.__name__ for f, _ in encounters._ACT1_STRONG_POOL]
        assert STRONG_POOL == factory_names

    def test_elite_pool_matches_labels(self):
        labels = [label for _, label in encounters._ACT1_ELITE_POOL]
        assert ELITE_POOL == labels

    def test_weighted_pick_is_public(self):
        """weighted_pick should be importable (not private _weighted_pick)."""
        rng = RNG(42)
        result = weighted_pick(rng, STRONG_POOL, [1.0] * len(STRONG_POOL))
        assert result in STRONG_POOL


# ---------------------------------------------------------------------------
# Builder: elite encounters via factory map, no patching
# ---------------------------------------------------------------------------

class TestBuilderEliteViaFactoryMap:
    def test_elite_factory_map_has_gremlin_nob(self):
        assert "Gremlin Nob" in builder._ENCOUNTER_FACTORY_MAP

    def test_elite_factory_map_has_lagavulin(self):
        assert "Lagavulin" in builder._ENCOUNTER_FACTORY_MAP

    def test_elite_factory_map_has_three_sentries(self):
        assert "Three Sentries" in builder._ENCOUNTER_FACTORY_MAP

    def test_build_elite_gremlin_nob(self):
        c = Character.ironclad()
        combat = builder.build_combat("elite", "Gremlin Nob", seed=42, character=c)
        obs = combat.observe()
        assert obs.enemies[0].name == "GremlinNob"
        assert combat._state.is_elite is True

    def test_build_elite_lagavulin(self):
        c = Character.ironclad()
        combat = builder.build_combat("elite", "Lagavulin", seed=42, character=c)
        obs = combat.observe()
        assert obs.enemies[0].name == "Lagavulin"

    def test_build_elite_three_sentries(self):
        c = Character.ironclad()
        combat = builder.build_combat("elite", "Three Sentries", seed=42, character=c)
        obs = combat.observe()
        assert len(obs.enemies) == 3

    def test_build_passes_hp_directly(self):
        """Builder must not patch _player_max_hp after construction."""
        c = Character.ironclad()
        c.player_hp = 55
        combat = builder.build_combat("easy", "cultist", seed=42, character=c)
        assert combat._player_start_hp == 55
        assert combat._player_max_hp == 80

    def test_build_passes_potions_directly(self):
        c = Character.ironclad()
        c.add_potion("FirePotion")
        combat = builder.build_combat("easy", "cultist", seed=42, character=c)
        assert "FirePotion" in combat._state.potions

    def test_no_post_construction_patching(self):
        """Factories must not require post-construction attribute patches.

        We verify this by checking the built combat is fully valid before
        any external mutation: observe() reflects the correct player_hp immediately.
        """
        c = Character.ironclad()
        c.player_hp = 60
        combat = builder.build_combat("elite", "Lagavulin", seed=0, character=c)
        obs = combat.observe()
        assert obs.player_hp == 60
