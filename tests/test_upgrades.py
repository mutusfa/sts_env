"""Tests for card upgrade system."""

import pytest
from sts_env.combat import Combat
from sts_env.combat.card import Card
from sts_env.combat.cards import play_card, get_spec
from sts_env.combat.engine import IRONCLAD_STARTER


def _make_combat_with_card(card_id: str, upgraded: int = 0) -> Combat:
    """Create a combat with a specific card in hand."""
    combat = Combat(deck=list(IRONCLAD_STARTER), enemies=["JawWorm"], seed=42)
    combat.reset()
    test_card = Card(card_id, upgraded=upgraded)
    combat._state.piles.hand.insert(0, test_card)
    return combat


class TestCardSpecUpgrades:
    """Test that CardSpec.upgrade contains the expected deltas."""

    def test_starter_cards_have_upgrades(self):
        for card_id in ["Strike", "Defend", "Bash"]:
            assert get_spec(card_id).upgrade, f"{card_id} should have upgrade bonuses"

    def test_strike_upgrade_delta(self):
        assert get_spec("Strike").upgrade.get("attack", 0) == 3

    def test_defend_upgrade_delta(self):
        assert get_spec("Defend").upgrade.get("block", 0) == 3

    def test_bash_upgrade_deltas(self):
        spec = get_spec("Bash")
        assert spec.upgrade.get("attack", 0) == 2
        assert spec.upgrade.get("vulnerable", 0) == 1

    def test_feed_upgrade_delta(self):
        assert get_spec("Feed").upgrade.get("attack", 0) == 5

    def test_entrench_cost_reduction(self):
        assert get_spec("Entrench").upgrade.get("cost", 0) == -1

    def test_pummel_extra_hit(self):
        assert get_spec("Pummel").upgrade.get("hits", 0) == 1

    def test_corruption_cost_reduction(self):
        assert get_spec("Corruption").upgrade.get("cost", 0) == -1


class TestUpgradedDamage:
    """Test that upgraded attacks deal more damage."""

    def test_upgraded_strike_deals_9(self):
        combat = _make_combat_with_card("Strike", upgraded=1)
        enemy = combat._state.enemies[0]
        old_hp = enemy.hp
        combat._state.energy = 3
        play_card(combat._state, 0, 0)
        assert enemy.hp == old_hp - 9

    def test_base_strike_deals_6(self):
        combat = _make_combat_with_card("Strike", upgraded=0)
        enemy = combat._state.enemies[0]
        old_hp = enemy.hp
        combat._state.energy = 3
        play_card(combat._state, 0, 0)
        assert enemy.hp == old_hp - 6

    def test_upgraded_bash_deals_10_and_3_vuln(self):
        combat = _make_combat_with_card("Bash", upgraded=1)
        enemy = combat._state.enemies[0]
        old_hp = enemy.hp
        combat._state.energy = 3
        play_card(combat._state, 0, 0)
        assert enemy.hp == old_hp - 10  # 8 + 2
        assert enemy.powers.vulnerable == 3  # 2 + 1


class TestUpgradedBlock:
    """Test that upgraded skills grant more block."""

    def test_upgraded_defend_grants_8(self):
        combat = _make_combat_with_card("Defend", upgraded=1)
        combat._state.energy = 3
        play_card(combat._state, 0, 0)
        assert combat._state.player_block == 8  # 5 + 3

    def test_base_defend_grants_5(self):
        combat = _make_combat_with_card("Defend", upgraded=0)
        combat._state.energy = 3
        play_card(combat._state, 0, 0)
        assert combat._state.player_block == 5


class TestUpgradedCost:
    """Test that cost-reduction upgrades work."""

    def test_upgraded_entrench_costs_1(self):
        spec = get_spec("Entrench")
        assert spec.cost == 2
        assert spec.upgrade.get("cost", 0) == -1
        assert spec.cost + spec.upgrade.get("cost", 0) == 1

    def test_upgraded_corruption_costs_2(self):
        spec = get_spec("Corruption")
        assert spec.cost == 3
        assert spec.upgrade.get("cost", 0) == -1
        assert spec.cost + spec.upgrade.get("cost", 0) == 2


class TestUpgradedDraw:
    """Test that upgraded cards draw more."""

    def test_upgraded_warcry_draws_2(self):
        combat = _make_combat_with_card("WarCry", upgraded=1)
        combat._state.energy = 3
        hand_size_before = len(combat._state.piles.hand)
        play_card(combat._state, 0, 0)
        # WarCry exhausts, so it leaves hand, but draws 2
        # Net effect: hand gains 1 card (draw 2, lose WarCry to exhaust)
        assert len(combat._state.piles.hand) >= hand_size_before

    def test_upgraded_burning_pact_draws_3(self):
        combat = _make_combat_with_card("BurningPact", upgraded=1)
        combat._state.energy = 3
        hand_size_before = len(combat._state.piles.hand)
        play_card(combat._state, 0, 0)
        assert len(combat._state.piles.hand) >= hand_size_before + 1  # draws 3, loses 1
