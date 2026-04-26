"""Tests for card upgrade system."""

import pytest
from sts_env.combat import Combat
from sts_env.combat.card import Card
from sts_env.combat.cards import UPGRADE_BONUSES, _ub, play_card, get_spec
from sts_env.combat.engine import IRONCLAD_STARTER


def _make_combat_with_card(card_id: str, upgraded: int = 0) -> Combat:
    """Create a combat with a specific card in hand."""
    combat = Combat(deck=list(IRONCLAD_STARTER), enemies=["JawWorm"], seed=42)
    combat.reset()
    # Place our test card at hand index 0
    test_card = Card(card_id, upgraded=upgraded)
    combat._state.piles.hand.insert(0, test_card)
    return combat


class TestUpgradeBonuses:
    """Test the UPGRADE_BONUSES data and _ub helper."""

    def test_ub_returns_zero_for_base(self):
        assert _ub("Strike", 0, "damage") == 0

    def test_ub_returns_bonus_for_upgraded(self):
        assert _ub("Strike", 1, "damage") == 3

    def test_ub_returns_zero_for_unknown_key(self):
        assert _ub("Strike", 1, "unknown") == 0

    def test_ub_returns_zero_for_unknown_card(self):
        assert _ub("NonExistent", 1, "damage") == 0

    def test_all_starter_cards_have_upgrade(self):
        for card_id in ["Strike", "Defend", "Bash"]:
            assert card_id in UPGRADE_BONUSES

    def test_feed_upgrade(self):
        assert UPGRADE_BONUSES["Feed"]["damage"] == 5
        assert UPGRADE_BONUSES["Feed"]["max_hp"] == 1

    def test_entrench_cost_reduction(self):
        assert UPGRADE_BONUSES["Entrench"]["cost"] == -1

    def test_pummel_extra_hit(self):
        assert UPGRADE_BONUSES["Pummel"]["hits"] == 1


class TestUpgradedDamage:
    """Test that upgraded attacks deal more damage."""

    def test_upgraded_strike_deals_9(self):
        combat = _make_combat_with_card("Strike", upgraded=1)
        enemy = combat._state.enemies[0]
        old_hp = enemy.hp
        combat._state.energy = 3
        play_card(combat._state, 0, 0)
        # Base Strike = 6, upgrade +3 = 9
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
        bonus_cost = UPGRADE_BONUSES["Entrench"].get("cost", 0)
        assert bonus_cost == -1
        assert spec.cost + bonus_cost == 1

    def test_upgraded_corruption_costs_2(self):
        spec = get_spec("Corruption")
        assert spec.cost == 3
        bonus_cost = UPGRADE_BONUSES["Corruption"].get("cost", 0)
        assert bonus_cost == -1
        assert spec.cost + bonus_cost == 2


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
