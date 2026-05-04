"""Tests for sts_env.run.relics — on_combat_end with both RunState and Character."""

import pytest

from sts_env.run.state import RunState
from sts_env.run.character import Character
from sts_env.run import relics


class TestOnCombatEndRunState:
    """Existing RunState behaviour is preserved."""

    def test_burning_blood_heals_runstate(self):
        rs = RunState(player_hp=70, player_max_hp=80, relics=["BurningBlood"])
        relics.on_combat_end(rs)
        assert rs.player_hp == 76

    def test_burning_blood_caps_at_max_hp(self):
        rs = RunState(player_hp=78, player_max_hp=80, relics=["BurningBlood"])
        relics.on_combat_end(rs)
        assert rs.player_hp == 80

    def test_no_relics_no_change(self):
        rs = RunState(player_hp=50, player_max_hp=80, relics=[])
        relics.on_combat_end(rs)
        assert rs.player_hp == 50


class TestOnCombatEndCharacter:
    """on_combat_end works with Character (duck-typed: same .relics / .heal())."""

    def test_burning_blood_heals_character(self):
        char = Character.ironclad()  # starts with BurningBlood, full HP
        char.player_hp = 70
        relics.on_combat_end(char)
        assert char.player_hp == 76

    def test_burning_blood_caps_at_max_hp_character(self):
        char = Character.ironclad()
        char.player_hp = 78
        relics.on_combat_end(char)
        assert char.player_hp == 80

    def test_no_relics_no_change_character(self):
        char = Character.ironclad()
        char.relics = []
        char.player_hp = 50
        relics.on_combat_end(char)
        assert char.player_hp == 50


class TestMeatOnTheBone:
    """MeatOnTheBone: heal 12 if HP ≤ 50% max at end of combat."""

    def test_exactly_50_percent_triggers(self):
        rs = RunState(player_hp=40, player_max_hp=80, relics=["MeatOnTheBone"])
        relics.on_combat_end(rs)
        assert rs.player_hp == 52

    def test_below_50_percent_triggers(self):
        rs = RunState(player_hp=1, player_max_hp=80, relics=["MeatOnTheBone"])
        relics.on_combat_end(rs)
        assert rs.player_hp == 13

    def test_above_50_percent_no_trigger(self):
        rs = RunState(player_hp=41, player_max_hp=80, relics=["MeatOnTheBone"])
        relics.on_combat_end(rs)
        assert rs.player_hp == 41

    def test_heal_capped_at_max_hp(self):
        rs = RunState(player_hp=39, player_max_hp=80, relics=["MeatOnTheBone"])
        relics.on_combat_end(rs)
        # 39 + 12 = 51 < 80, no cap needed
        assert rs.player_hp == 51

    def test_heal_capped_at_max_hp_near_full(self):
        rs = RunState(player_hp=36, player_max_hp=80, relics=["MeatOnTheBone"])
        relics.on_combat_end(rs)
        # Would be 48 if below threshold — but 36 <= 40, so triggers: 36+12=48
        assert rs.player_hp == 48

    def test_works_with_character(self):
        char = Character.ironclad()
        char.relics = ["MeatOnTheBone"]
        char.player_hp = 40  # exactly 50% of 80
        relics.on_combat_end(char)
        assert char.player_hp == 52
