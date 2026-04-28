"""Tests for Act 1 map-based run system."""

import pytest

from sts_env.run.map import generate_act1_map, RoomType, get_encounter_for_room, MAP_WIDTH, MAP_HEIGHT
from sts_env.run.rooms import rest_heal, rest_upgrade, pick_rest_choice, RestChoice, _best_upgrade_target
from sts_env.run.character import Character
from sts_env.combat.rng import RNG


# =========================================================================
# Map generation tests
# =========================================================================

class TestMapGeneration:
    def test_generates_15_floors(self):
        m = generate_act1_map(42)
        assert len(m.nodes) == MAP_HEIGHT

    def test_7_columns_per_floor(self):
        m = generate_act1_map(42)
        for f in range(MAP_HEIGHT):
            assert len(m.nodes[f]) == MAP_WIDTH

    def test_floor0_reachable_are_monster(self):
        m = generate_act1_map(42)
        for node in m.nodes[0]:
            if node.edges:
                assert node.room_type == RoomType.MONSTER

    def test_floor8_reachable_are_treasure(self):
        m = generate_act1_map(42)
        for node in m.nodes[8]:
            if node.edges:
                assert node.room_type == RoomType.TREASURE

    def test_floor14_reachable_are_rest(self):
        m = generate_act1_map(42)
        for node in m.nodes[14]:
            if node.edges:
                assert node.room_type == RoomType.REST

    def test_floor14_has_no_edges(self):
        """Floor 14 is the last floor — no outgoing edges."""
        m = generate_act1_map(42)
        for node in m.nodes[14]:
            assert len(node.edges) == 0

    def test_reachable_non_boss_have_edges(self):
        """Nodes that are reachable (on a path) on floors 0-13 have edges."""
        m = generate_act1_map(42)
        # Find all nodes on actual paths
        paths = m.all_paths()
        assert len(paths) > 0
        nodes_on_paths = set()
        for path in paths:
            for floor, x in path:
                nodes_on_paths.add((floor, x))
        for floor, x in nodes_on_paths:
            if floor < 14:
                node = m.get_node(floor, x)
                assert node is not None
                assert len(node.edges) >= 1, (
                    f"Reachable node ({floor},{x}) has no edges"
                )

    def test_all_paths_reach_floor14(self):
        m = generate_act1_map(42)
        paths = m.all_paths()
        assert len(paths) > 0
        for path in paths:
            assert path[-1][0] == 14

    def test_deterministic(self):
        m1 = generate_act1_map(42)
        m2 = generate_act1_map(42)
        for floor in range(MAP_HEIGHT):
            for i in range(MAP_WIDTH):
                n1 = m1.get_node(floor, i)
                n2 = m2.get_node(floor, i)
                if n1 and n2:
                    assert n1.room_type == n2.room_type
                    assert n1.edges == n2.edges

    def test_string_repr(self):
        m = generate_act1_map(42)
        s = str(m)
        assert "R" in s  # Rest
        assert "M" in s  # Monster
        assert "T" in s  # Treasure


class TestEncounterSelection:
    def test_monster_returns_encounter(self):
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(42))
        enc = get_encounter_for_room(RoomType.MONSTER, queue)
        assert enc is not None
        assert isinstance(enc, str)

    def test_elite_returns_encounter(self):
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(42))
        enc = get_encounter_for_room(RoomType.ELITE, queue)
        assert enc is not None

    def test_boss_returns_act1_boss(self):
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(42))
        enc = get_encounter_for_room(RoomType.BOSS, queue)
        assert enc in ["slime_boss", "guardian", "hexaghost"]

    def test_rest_returns_none(self):
        from sts_env.run.encounter_queue import EncounterQueue
        queue = EncounterQueue(RNG(42))
        enc = get_encounter_for_room(RoomType.REST, queue)
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
