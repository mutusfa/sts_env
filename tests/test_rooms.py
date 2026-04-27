"""Tests for Act 1 map-based run system."""

import pytest

from sts_env.run.map import generate_act1_map, RoomType, get_encounter_for_room
from sts_env.run.rooms import rest_heal, rest_upgrade, pick_rest_choice, RestChoice, _best_upgrade_target
from sts_env.run.character import Character
from sts_env.combat.rng import RNG


# =========================================================================
# Map generation tests
# =========================================================================

class TestMapGeneration:
    def test_generates_15_floors(self):
        m = generate_act1_map(42)
        assert len(m.nodes) == 15

    def test_floor0_all_monster(self):
        m = generate_act1_map(42)
        for node in m.nodes[0]:
            assert node.room_type == RoomType.MONSTER

    def test_floor7_all_rest(self):
        m = generate_act1_map(42)
        for node in m.nodes[7]:
            assert node.room_type == RoomType.REST

    def test_floor14_all_boss(self):
        m = generate_act1_map(42)
        for node in m.nodes[14]:
            assert node.room_type == RoomType.BOSS

    def test_each_node_has_edges_except_boss(self):
        m = generate_act1_map(42)
        for floor in range(14):
            for node in m.nodes[floor]:
                assert len(node.edges) >= 1, f"Node at floor {floor} x={node.x} has no edges"

    def test_boss_nodes_have_no_edges(self):
        m = generate_act1_map(42)
        for node in m.nodes[14]:
            assert len(node.edges) == 0

    def test_all_paths_reach_boss(self):
        m = generate_act1_map(42)
        paths = m.all_paths()
        assert len(paths) > 0
        for path in paths:
            assert path[-1][0] == 14  # Last floor is boss

    def test_deterministic(self):
        m1 = generate_act1_map(42)
        m2 = generate_act1_map(42)
        for floor in range(15):
            for i in range(3):
                n1 = m1.get_node(floor, i)
                n2 = m2.get_node(floor, i)
                if n1 and n2:
                    assert n1.room_type == n2.room_type

    def test_string_repr(self):
        m = generate_act1_map(42)
        s = str(m)
        assert "B" in s  # Boss
        assert "R" in s  # Rest
        assert "M" in s  # Monster


class TestEncounterSelection:
    def test_monster_returns_encounter(self):
        rng = RNG(42)
        enc = get_encounter_for_room(RoomType.MONSTER, rng)
        assert enc is not None
        assert isinstance(enc, str)

    def test_elite_returns_encounter(self):
        rng = RNG(42)
        enc = get_encounter_for_room(RoomType.ELITE, rng)
        assert enc is not None

    def test_boss_returns_act1_boss(self):
        rng = RNG(42)
        enc = get_encounter_for_room(RoomType.BOSS, rng)
        assert enc in ["slime_boss", "guardian", "hexaghost"]

    def test_rest_returns_none(self):
        rng = RNG(42)
        enc = get_encounter_for_room(RoomType.REST, rng)
        assert enc is None


# =========================================================================
# Rest site tests
# =========================================================================

class TestRestHeal:
    def test_heals_30_percent(self):
        c = Character.ironclad()
        c.player_hp = 40
        healed = rest_heal(c)
        assert healed == 24  # 80 * 30 // 100
        assert c.player_hp == 64

    def test_capped_at_max_hp(self):
        c = Character.ironclad()
        c.player_hp = 78
        healed = rest_heal(c)
        assert healed == 2
        assert c.player_hp == 80

    def test_full_hp_heals_zero(self):
        c = Character.ironclad()
        c.player_hp = 80
        healed = rest_heal(c)
        assert healed == 0


class TestRestUpgrade:
    def test_upgrades_card_in_deck(self):
        c = Character.ironclad()
        strike_count = c.deck.count("Strike")
        assert strike_count >= 1
        rest_upgrade(c, "Strike")
        assert "Strike+" in c.deck
        assert c.deck.count("Strike") == strike_count - 1

    def test_upgrades_only_first_copy(self):
        c = Character.ironclad()
        strike_count = c.deck.count("Strike")
        rest_upgrade(c, "Strike")
        assert c.deck.count("Strike+") == 1
        assert c.deck.count("Strike") == strike_count - 1

    def test_no_effect_if_card_not_in_deck(self):
        c = Character.ironclad()
        deck_before = list(c.deck)
        rest_upgrade(c, "NonExistentCard")
        assert c.deck == deck_before


class TestPickRestChoice:
    def test_heals_when_hurt(self):
        c = Character.ironclad()
        c.player_hp = 30  # 37.5% of 80
        result = pick_rest_choice(c, strategy="heal_if_hurt")
        assert result.choice == RestChoice.REST
        assert result.hp_healed > 0

    def test_upgrades_when_healthy(self):
        c = Character.ironclad()
        c.player_hp = 70  # 87.5% of 80
        result = pick_rest_choice(c, strategy="heal_if_hurt")
        # Should prefer upgrade since HP > 70%
        assert result.choice == RestChoice.UPGRADE
        assert result.card_upgraded is not None

    def test_always_heal_strategy(self):
        c = Character.ironclad()
        c.player_hp = 70
        result = pick_rest_choice(c, strategy="always_heal")
        assert result.choice == RestChoice.REST

    def test_always_upgrade_strategy(self):
        c = Character.ironclad()
        c.player_hp = 40
        result = pick_rest_choice(c, strategy="always_upgrade")
        assert result.choice == RestChoice.UPGRADE

    def test_always_upgrade_falls_back_to_heal(self):
        c = Character.ironclad()
        # Upgrade all cards first
        c.deck = [card + "+" for card in c.deck]
        result = pick_rest_choice(c, strategy="always_upgrade")
        assert result.choice == RestChoice.REST


class TestBestUpgradeTarget:
    def test_prefers_bash(self):
        c = Character.ironclad()
        target = _best_upgrade_target(c)
        assert target == "Bash"

    def test_returns_none_when_all_upgraded(self):
        c = Character.ironclad()
        c.deck = [card + "+" for card in c.deck]
        target = _best_upgrade_target(c)
        assert target is None


# =========================================================================
# Card upgrade integration (deck "+" suffix → Card.card_id carries "+")
# =========================================================================

class TestUpgradeSuffixParsing:
    def test_strike_plus_is_full_card_id(self):
        from sts_env.combat.card import Card
        c = Card("Strike+")
        assert c.card_id == "Strike+"
        assert c.base_id == "Strike"
        assert c.upgraded

    def test_deck_with_upgraded_cards_combat(self):
        from sts_env.combat import Combat
        c = Character.ironclad()
        # Upgrade one Strike
        idx = c.deck.index("Strike")
        c.deck[idx] = "Strike+"

        combat = Combat(
            deck=list(c.deck),
            enemies=["JawWorm"],
            seed=42,
            player_hp=c.player_hp,
        )
        combat.reset()
        all_cards = (
            combat._state.piles.draw
            + combat._state.piles.hand
            + combat._state.piles.discard
        )
        upgraded_strikes = [c for c in all_cards if c.card_id == "Strike+"]
        assert len(upgraded_strikes) == 1
