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
