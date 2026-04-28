"""Tests for Slime Boss (Act 1 boss) and Slimed status card mechanics."""

import pytest
from sts_env.combat import Combat
from sts_env.combat.engine import IRONCLAD_STARTER
from sts_env.combat.state import Action, ActionType
from sts_env.combat.card import Card
from sts_env.combat.cards import CardType, get_spec
from sts_env.combat.enemies import Intent, IntentType
from sts_env.combat.encounters import slime_boss
from sts_env.run import builder


class TestSlimeBossSpec:
    """Basic Slime Boss setup tests."""

    def test_hp_is_140(self):
        """Slime Boss should always have 140 HP."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["SlimeBoss", "Empty"], seed=42)
        obs = combat.reset()
        assert obs.enemies[0].name == "SlimeBoss"
        assert obs.enemies[0].hp == 140
        assert obs.enemies[0].max_hp == 140

    def test_second_slot_is_empty(self):
        """Second slot should be Empty (pre-allocated for split)."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["SlimeBoss", "Empty"], seed=42)
        obs = combat.reset()
        assert obs.enemies[1].name == "Empty"
        assert obs.enemies[1].hp == 0

    def test_first_intent_is_goop_spray(self):
        """Turn 0 intent should be Goop Spray (DEBUFF)."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["SlimeBoss", "Empty"], seed=42)
        obs = combat.reset()
        assert obs.enemies[0].intent_type == "DEBUFF"


class TestSlimeBossIntentCycle:
    """Test the Goop Spray → Preparing → Slam intent cycle."""

    def _make_combat(self, seed=42):
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["SlimeBoss", "Empty"], seed=seed)
        combat.reset()
        return combat

    def test_goop_spray_adds_slimed_to_discard(self):
        """Goop Spray should add 3 Slimed cards to the discard pile."""
        combat = self._make_combat()
        obs = combat.observe()
        assert obs.enemies[0].intent_type == "DEBUFF"
        # End turn → Goop Spray resolves
        obs, _, _ = combat.step(Action.end_turn())
        slimed_count = obs.discard_pile.get("Slimed", 0)
        assert slimed_count == 3, f"Expected 3 Slimed in discard, got {slimed_count}"

    def test_preparing_does_nothing(self):
        """Preparing intent should not deal damage or add cards."""
        combat = self._make_combat()
        # End turn 0 (Goop Spray resolves)
        obs, _, _ = combat.step(Action.end_turn())
        # Turn 1: Boss shows Preparing intent (BUFF, no damage)
        assert obs.enemies[0].intent_type == "BUFF"
        assert obs.enemies[0].intent_damage == 0
        hp_before = obs.player_hp
        # End turn 1 (Preparing resolves)
        obs, _, _ = combat.step(Action.end_turn())
        assert obs.player_hp == hp_before

    def test_slam_deals_35_damage(self):
        """Slam should deal 35 damage to the player."""
        combat = self._make_combat()
        # End turn 0 (Goop Spray)
        obs, _, _ = combat.step(Action.end_turn())
        # End turn 1 (Preparing)
        obs, _, _ = combat.step(Action.end_turn())
        # Turn 2: Boss shows Slam intent (ATTACK, 35 damage)
        assert obs.enemies[0].intent_type == "ATTACK"
        assert obs.enemies[0].intent_damage == 35
        hp_before = obs.player_hp
        # End turn 2 (Slam resolves)
        obs, _, _ = combat.step(Action.end_turn())
        assert obs.player_hp == hp_before - 35

    def test_cycle_repeats(self):
        """After 3 turns, the cycle should repeat: Goop Spray again."""
        combat = self._make_combat()
        # End turns 0-2 (Goop Spray → Preparing → Slam)
        for _ in range(3):
            obs, _, _ = combat.step(Action.end_turn())
        # After resolving Slam, turn 3 intent should be Goop Spray (DEBUFF)
        assert obs.enemies[0].intent_type == "DEBUFF"
        # End turn 3 to resolve the second Goop Spray
        obs, _, _ = combat.step(Action.end_turn())
        # Check total Slimed across all piles (cards may have cycled through draw)
        total_slimed = (
            obs.discard_pile.get("Slimed", 0)
            + obs.draw_pile.get("Slimed", 0)
            + sum(1 for c in obs.hand if (c["card_id"] if isinstance(c, dict) else c.card_id) == "Slimed")
            + obs.exhaust_pile.get("Slimed", 0)
        )
        assert total_slimed == 6, f"Expected 6 Slimed total, got {total_slimed}"


class TestSlimeBossSplit:
    """Test split mechanics when HP crosses ≤50% threshold."""

    def test_split_triggers_at_50_percent(self):
        """Slime Boss should split into AcidSlimeM + SpikeSlimeM at ≤70 HP."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["SlimeBoss", "Empty"], seed=42)
        obs = combat.reset()

        # Play attacks each turn until split happens
        for _turn in range(30):
            obs = combat.observe()
            if obs.done:
                break
            # Check if split already happened (from previous enemy turn)
            if obs.enemies[0].name != "SlimeBoss":
                break

            # Play all affordable attack cards
            actions = combat.valid_actions()
            for action in list(actions):
                if action.action_type != ActionType.PLAY_CARD:
                    continue
                obs = combat.observe()
                if action.hand_index >= len(obs.hand):
                    continue
                card = obs.hand[action.hand_index]
                # Handle both dict (new format) and Card (legacy)
                card_id = card["card_id"] if isinstance(card, dict) else card.card_id
                spec = get_spec(card_id)
                if spec.card_type == CardType.ATTACK and spec.cost <= obs.energy:
                    obs, _, _ = combat.step(action)
                    if obs.enemies[0].name != "SlimeBoss":
                        break
                else:
                    continue

            if obs.enemies[0].name != "SlimeBoss" or obs.done:
                break

            # End turn
            obs, _, _ = combat.step(Action.end_turn())
            if obs.enemies[0].name != "SlimeBoss" or obs.done:
                break

        # After split: two different medium slimes
        assert obs.enemies[0].name in ("AcidSlimeM", "SpikeSlimeM"), \
            f"Expected medium slime at slot 0, got {obs.enemies[0].name}"
        assert obs.enemies[1].name in ("AcidSlimeM", "SpikeSlimeM"), \
            f"Expected medium slime at slot 1, got {obs.enemies[1].name}"
        assert obs.enemies[0].name != obs.enemies[1].name, \
            "Slime Boss should split into two different slimes"

    def test_split_hp_carries_over(self):
        """Split slimes should have HP equal to the boss's remaining HP."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["SlimeBoss", "Empty"], seed=42)
        obs = combat.reset()

        for _turn in range(30):
            obs = combat.observe()
            if obs.done or obs.enemies[0].name != "SlimeBoss":
                break

            actions = combat.valid_actions()
            for action in list(actions):
                if action.action_type != ActionType.PLAY_CARD:
                    continue
                obs = combat.observe()
                if action.hand_index >= len(obs.hand):
                    continue
                card = obs.hand[action.hand_index]
                # Handle both dict (new format) and Card (legacy)
                card_id = card["card_id"] if isinstance(card, dict) else card.card_id
                spec = get_spec(card_id)
                if spec.card_type == CardType.ATTACK and spec.cost <= obs.energy:
                    obs, _, _ = combat.step(action)
                    if obs.enemies[0].name != "SlimeBoss":
                        break
                else:
                    continue

            if obs.enemies[0].name != "SlimeBoss" or obs.done:
                break
            obs, _, _ = combat.step(Action.end_turn())
            if obs.enemies[0].name != "SlimeBoss" or obs.done:
                break

        # Both split slimes should have the same HP (= boss HP at time of split)
        assert obs.enemies[0].hp == obs.enemies[1].hp, \
            "Split slimes should have equal HP"
        assert obs.enemies[0].hp > 0
        assert obs.enemies[0].hp <= 70, \
            f"Split HP should be ≤ 70, got {obs.enemies[0].hp}"


class TestSlimedCard:
    """Test the Slimed status card."""

    def test_slimed_is_status_card(self):
        spec = get_spec("Slimed")
        assert spec.card_type == CardType.STATUS

    def test_slimed_costs_1(self):
        spec = get_spec("Slimed")
        assert spec.cost == 1

    def test_slimed_exhausts(self):
        spec = get_spec("Slimed")
        assert spec.exhausts is True

    def test_slimed_can_be_played(self):
        spec = get_spec("Slimed")
        assert spec.playable is True


class TestSlimeBossEncounter:
    """Test the encounter factory and builder integration."""

    def test_slime_boss_factory(self):
        combat = slime_boss(seed=42)
        obs = combat.reset()
        assert obs.enemies[0].name == "SlimeBoss"
        assert obs.enemies[1].name == "Empty"
        assert obs.enemies[0].hp == 140

    def test_slime_boss_factory_with_custom_deck(self):
        custom_deck = ["Strike"] * 10
        combat = slime_boss(seed=42, deck=custom_deck, player_hp=100)
        obs = combat.reset()
        assert obs.player_hp == 100
        assert obs.enemies[0].name == "SlimeBoss"

    def test_builder_boss_type(self):
        combat = builder.build_combat(
            "boss", "slime_boss", seed=42,
            deck=list(IRONCLAD_STARTER),
            player_hp=80,
            player_max_hp=80,
        )
        obs = combat.reset()
        assert obs.enemies[0].name == "SlimeBoss"

    def test_builder_boss_with_potions(self):
        combat = builder.build_combat(
            "boss", "slime_boss", seed=42,
            deck=list(IRONCLAD_STARTER),
            player_hp=80,
            player_max_hp=80,
            potions=["AttackPotion"],
        )
        obs = combat.reset()
        assert "AttackPotion" in obs.potions

    def test_builder_unknown_boss_raises(self):
        with pytest.raises(ValueError, match="Unknown boss"):
            builder.build_combat(
                "boss", "nonexistent_boss", seed=42,
                deck=list(IRONCLAD_STARTER),
            )
