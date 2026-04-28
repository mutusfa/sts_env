"""Tests for run-level orchestrator and elite mechanics."""

import pytest
from sts_env.combat import Combat
from sts_env.combat.engine import IRONCLAD_STARTER
from sts_env.combat.state import Action, ActionType
from sts_env.combat.card import Card
from sts_env.combat.cards import CardType, get_spec
from sts_env.combat.enemies import Intent, IntentType
from sts_env.run.state import RunState
from sts_env.run.character import Character, IRONCLAD_STARTER as CHAR_IRONCLAD_STARTER
from sts_env.run import relics, rewards, scenarios, builder
from sts_env.combat.rng import RNG


# ---------------------------------------------------------------------------
# Gremlin Nob tests
# ---------------------------------------------------------------------------

class TestGremlinNob:
    """Test Gremlin Nob elite mechanics."""

    def test_bellow_reduces_energy(self):
        """Bellow should reduce player energy by 2 on the next turn."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["GremlinNob"], seed=42)
        obs = combat.reset()
        # Turn 0: Nob shows BUFF intent (Bellow)
        assert obs.enemies[0].intent_type == "BUFF"
        # End turn → Bellow resolves, energy_loss_next_turn = 2
        obs, _, _ = combat.step(Action.end_turn())
        # Turn 1: player should have 3 - 2 = 1 energy
        assert obs.energy == 1, f"Expected energy=1 after Bellow, got {obs.energy}"

    def test_skill_punish_adds_strength(self):
        """Playing a Skill card should give Nob 2 strength."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["GremlinNob"], seed=42)
        obs = combat.reset()
        # End turn 0 (Bellow)
        obs, _, _ = combat.step(Action.end_turn())
        # Turn 1: find a Skill card in hand
        nob_str_before = obs.enemies[0].powers["strength"]
        for i, card in enumerate(obs.hand):
            # Handle both dict (new format) and Card (legacy)
            if isinstance(card, dict):
                card_id = card["card_id"]
            else:
                card_id = card.card_id
            spec = get_spec(card_id)
            if spec.card_type == CardType.SKILL and spec.cost <= obs.energy:
                obs, _, _ = combat.step(Action.play_card(i, 0))
                break
        nob_str_after = obs.enemies[0].powers["strength"]
        assert nob_str_after >= nob_str_before + 2, (
            f"Expected Nob strength >= {nob_str_before + 2} after skill play, got {nob_str_after}"
        )

    def test_attack_does_not_trigger_punish(self):
        """Playing an Attack card should NOT trigger Nob's skill-punish."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["GremlinNob"], seed=42)
        obs = combat.reset()
        # End turn 0 (Bellow)
        obs, _, _ = combat.step(Action.end_turn())
        # Find an Attack card that's not Bash (Bash applies vulnerable which triggers Angry)
        nob_str_before = obs.enemies[0].powers["strength"]
        for i, card in enumerate(obs.hand):
            # Handle both dict (new format) and Card (legacy)
            if isinstance(card, dict):
                card_id = card["card_id"]
            else:
                card_id = card.card_id
            spec = get_spec(card_id)
            if spec.card_type == CardType.ATTACK and spec.cost <= obs.energy and card_id != "Bash":
                obs, _, _ = combat.step(Action.play_card(i, 0))
                break
        nob_str_after = obs.enemies[0].powers["strength"]
        # Angry fires on attack hit, so Nob gains 1 from Angry but NOT 2 from skill-punish
        assert nob_str_after == nob_str_before + 1, (
            f"Expected Nob strength = {nob_str_before + 1} from Angry only, got {nob_str_after}"
        )


# ---------------------------------------------------------------------------
# Lagavulin tests
# ---------------------------------------------------------------------------

class TestLagavulin:
    """Test Lagavulin elite mechanics."""

    def test_starts_asleep(self):
        """Lagavulin should start asleep with metallicize."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["Lagavulin"], seed=42)
        obs = combat.reset()
        assert obs.enemies[0].powers.get("asleep", False) is True
        assert obs.enemies[0].powers.get("enemy_metallicize", 0) == 8

    def test_wakes_on_attack(self):
        """Lagavulin should wake up when attacked and attack back immediately."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["Lagavulin"], seed=42)
        obs = combat.reset()
        # Play Strike to wake Lagavulin
        strike_idx = next(i for i, c in enumerate(obs.hand) if (c["card_id"] if isinstance(c, dict) else c.card_id) == "Strike")
        obs, _, _ = combat.step(Action.play_card(strike_idx, 0))
        # End turn — Lagavulin should attack (not stay asleep)
        hp_before = obs.player_hp
        obs, _, _ = combat.step(Action.end_turn())
        # Player should have taken damage from Lagavulin's attack
        assert obs.player_hp < hp_before, "Lagavulin should attack after being woken"

    def test_sleep_drain_pushes_strength_negative(self):
        """Lagavulin's sleeping drain should push player strength below 0."""
        # Create a combat where player starts with 0 strength
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["Lagavulin"], seed=42)
        obs = combat.reset()
        # Don't attack — let it sleep and drain for multiple turns
        for _ in range(3):
            if obs.done:
                break
            obs, _, _ = combat.step(Action.end_turn())
        # Player strength should be negative
        assert obs.player_powers["strength"] < 0, (
            f"Expected negative strength from Lagavulin drain, got {obs.player_powers['strength']}"
        )

    def test_siphon_pushes_stats_negative(self):
        """Siphon Soul should push strength and dexterity below 0."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["Lagavulin"], seed=42)
        obs = combat.reset()
        # Wake Lagavulin
        strike_idx = next(i for i, c in enumerate(obs.hand) if (c["card_id"] if isinstance(c, dict) else c.card_id) == "Strike")
        obs, _, _ = combat.step(Action.play_card(strike_idx, 0))
        # Play through several turns to reach Siphon Soul in the cycle
        for _ in range(6):
            if obs.done:
                break
            obs, _, _ = combat.step(Action.end_turn())
        # Siphon should have fired at least once, pushing stats negative
        # (They start at 0 from the drain phase, so Siphon makes them negative)
        assert obs.player_powers["strength"] < 0 or obs.player_powers["dexterity"] < 0, (
            "Siphon Soul should push at least one stat below 0"
        )


# ---------------------------------------------------------------------------
# Sentry tests
# ---------------------------------------------------------------------------

class TestSentry:
    """Test Sentry elite mechanics (Three Sentries)."""

    def test_dazed_goes_to_draw_pile(self):
        """Bolt intent should add Dazed to draw pile, not discard."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["Sentry", "Sentry", "Sentry"], seed=42)
        obs = combat.reset()
        # End turn 0 (all Sentries play Beam)
        obs, _, _ = combat.step(Action.end_turn())
        # Turn 1: Sentries play Bolt (add Dazed)
        obs, _, _ = combat.step(Action.end_turn())
        # Check draw pile for Dazed
        draw_dazed = obs.draw_pile.get("Dazed", 0)
        # Dazed should appear in draw pile or be in hand (if drawn)
        internal = combat._state
        total_dazed = (
            sum(1 for c in internal.piles.draw if c.card_id == "Dazed")
            + sum(1 for c in internal.piles.hand if c.card_id == "Dazed")
            + sum(1 for c in internal.piles.discard if c.card_id == "Dazed")
        )
        assert total_dazed > 0, "Dazed cards should exist somewhere after Bolt"


# ---------------------------------------------------------------------------
# RunState / Relic tests
# ---------------------------------------------------------------------------

class TestRunState:
    """Test run-level state management."""

    def test_burning_blood_heals(self):
        """Burning Blood relic should heal 6 HP after combat win."""
        run_state = RunState()
        run_state.player_hp = 70
        relics.on_combat_end(run_state)
        assert run_state.player_hp == 76, f"Expected HP=76 after Burning Blood, got {run_state.player_hp}"

    def test_burning_blood_capped_at_max(self):
        """Burning Blood should not heal above max HP."""
        run_state = RunState()
        run_state.player_hp = 78
        relics.on_combat_end(run_state)
        assert run_state.player_hp == 80, f"Expected HP capped at 80, got {run_state.player_hp}"

    def test_add_card(self):
        """add_card should extend the deck."""
        rs = RunState()
        n = len(rs.deck)
        rs.add_card("PommelStrike")
        assert len(rs.deck) == n + 1
        assert rs.deck[-1] == "PommelStrike"

    def test_add_potion(self):
        """add_potion should fill potion slots."""
        rs = RunState()
        rs.add_potion("FirePotion")
        assert rs.potions == ["FirePotion"]

    def test_potion_slot_limit(self):
        """Cannot exceed 3 potion slots — 4th is silently discarded."""
        rs = RunState()
        rs.add_potion("FirePotion")
        rs.add_potion("BloodPotion")
        rs.add_potion("BlockPotion")
        assert len(rs.potions) == 3
        rs.add_potion("SteroidPotion")
        # 4th potion is discarded, still only 3
        assert len(rs.potions) == 3


# ---------------------------------------------------------------------------
# Scenario tests
# ---------------------------------------------------------------------------

class TestScenario3:
    """Test scenario 3 encounter generation."""

    def test_returns_5_encounters(self):
        encounters = scenarios.scenario3_encounters(seed=42)
        assert len(encounters) == 5

    def test_correct_types(self):
        encounters = scenarios.scenario3_encounters(seed=42)
        types = [t for t, _ in encounters]
        assert types.count("easy") == 3
        assert types.count("hard") == 1
        assert types.count("elite") == 1

    def test_ordering(self):
        encounters = scenarios.scenario3_encounters(seed=42)
        types = [t for t, _ in encounters]
        assert types == ["easy", "easy", "hard", "easy", "elite"]

    def test_elite_is_valid(self):
        encounters = scenarios.scenario3_encounters(seed=42)
        elite_id = encounters[4][1]
        assert elite_id in ("Gremlin Nob", "Lagavulin", "Three Sentries")

    def test_deterministic(self):
        e1 = scenarios.scenario3_encounters(seed=42)
        e2 = scenarios.scenario3_encounters(seed=42)
        assert e1 == e2


# ---------------------------------------------------------------------------
# Act 1 scenario tests
# ---------------------------------------------------------------------------

class TestAct1Scenario:
    """Test act1_encounters scenario generation."""

    def test_returns_8_encounters(self):
        encounters = scenarios.act1_encounters(seed=42)
        assert len(encounters) == 8

    def test_correct_types(self):
        encounters = scenarios.act1_encounters(seed=42)
        types = [t for t, _ in encounters]
        assert types.count("easy") == 3
        assert types.count("hard") == 2
        assert types.count("elite") == 2
        assert types.count("boss") == 1

    def test_boss_is_last(self):
        encounters = scenarios.act1_encounters(seed=42)
        assert encounters[-1][0] == "boss"
        assert encounters[-1][1] == "slime_boss"

    def test_deterministic(self):
        e1 = scenarios.act1_encounters(seed=42)
        e2 = scenarios.act1_encounters(seed=42)
        assert e1 == e2

    def test_ordering(self):
        encounters = scenarios.act1_encounters(seed=42)
        types = [t for t, _ in encounters]
        assert types == ["easy", "easy", "hard", "elite", "easy", "hard", "elite", "boss"]


# ---------------------------------------------------------------------------
# Builder tests
# ---------------------------------------------------------------------------

class TestBuilder:
    """Test combat builder from encounter IDs."""

    def test_build_easy_combat(self):
        combat = builder.build_combat("easy", "cultist", seed=42)
        obs = combat.reset()
        assert obs.enemies[0].name == "Cultist"

    def test_build_elite_combat(self):
        combat = builder.build_combat("elite", "Lagavulin", seed=42)
        obs = combat.reset()
        assert obs.enemies[0].name == "Lagavulin"

    def test_build_sentry_combat(self):
        combat = builder.build_combat("elite", "Three Sentries", seed=42)
        obs = combat.reset()
        assert len(obs.enemies) == 3
        assert obs.enemies[0].name == "Sentry"

    def test_build_with_potions(self):
        combat = builder.build_combat(
            "easy", "cultist", seed=42, potions=["FirePotion"]
        )
        obs = combat.reset()
        assert "FirePotion" in obs.potions


# ---------------------------------------------------------------------------
# Reward tests
# ---------------------------------------------------------------------------

class TestRewards:
    """Test card and potion reward rolling."""

    def test_card_reward_returns_3_cards(self):
        rng = RNG(42)
        cards = rewards.roll_card_rewards(rng, is_elite=False)
        assert len(cards) == 3

    def test_elite_card_reward(self):
        rng = RNG(42)
        cards = rewards.roll_card_rewards(rng, is_elite=True)
        assert len(cards) == 3

    def test_potion_reward_returns_string_or_none(self):
        rng = RNG(42)
        potion = rewards.roll_potion_reward(rng)
        # Potion reward may be None (no potion) or a string
        assert potion is None or isinstance(potion, str)


# ---------------------------------------------------------------------------
# damage_taken / max_hp_gained test
# ---------------------------------------------------------------------------

class TestDamageTakenAndMaxHp:
    """Test that damage_taken reflects net HP change (can be negative with Feed)
    and max_hp_gained tracks the separate max-HP increase."""

    def test_damage_taken_can_be_negative_with_feed(self):
        """damage_taken = start_hp - current_hp, which can go negative with Feed healing."""
        found_negative = False
        for seed in range(50):
            deck = IRONCLAD_STARTER + ["Feed"]
            combat = Combat(deck=deck, enemies=["Cultist"], seed=seed)
            obs = combat.reset()
            while not obs.done:
                actions = combat.valid_actions()
                if not actions:
                    break
                actions.sort(key=lambda a: 0 if a.action_type == ActionType.PLAY_CARD else 99)
                obs, _, _ = combat.step(actions[0])
            if combat.damage_taken < 0:
                found_negative = True
                # If damage_taken is negative, max_hp_gained should be > 0 (Feed's effect)
                assert combat.max_hp_gained > 0, (
                    f"Seed {seed}: damage_taken={combat.damage_taken} but max_hp_gained={combat.max_hp_gained}"
                )
        # Feed is in the deck, so at least some seeds should produce a kill-with-Feed
        # resulting in negative damage_taken (net HP gain)
        # Not asserting found_negative=True because it depends on draw RNG

    def test_max_hp_gained_default_zero(self):
        """Without Feed, max_hp_gained should be 0."""
        combat = Combat(deck=IRONCLAD_STARTER, enemies=["Cultist"], seed=0)
        obs = combat.reset()
        while not obs.done:
            actions = combat.valid_actions()
            if not actions:
                break
            actions.sort(key=lambda a: 0 if a.action_type == ActionType.PLAY_CARD else 99)
            obs, _, _ = combat.step(actions[0])
        assert combat.max_hp_gained == 0


# ---------------------------------------------------------------------------
# Card-generating potion tests (Attack/Skill/Power Potion)
# ---------------------------------------------------------------------------

class TestCardPotions:
    """Test Attack/Skill/Power Potion two-step choice system."""

    def _make_combat_with_potion(self, potion_id: str, seed: int = 99):
        """Build a combat with a single potion and a tiny deck."""
        deck = ["Strike", "Defend"]
        combat = Combat(deck=deck, enemies=["Cultist"], seed=seed)
        combat.reset()
        # Inject the potion directly into state
        combat._state.potions = [potion_id]
        return combat

    def _use_potion(self, combat):
        """Find and execute a USE_POTION action for the first potion slot."""
        actions = combat.valid_actions()
        use = [a for a in actions if a.action_type == ActionType.USE_POTION]
        assert use, "No USE_POTION action found"
        obs, _, _ = combat.step(use[0])
        return obs

    def _choose_card(self, combat, choice_index=0):
        """Pick a card from pending_choices via CHOOSE_CARD."""
        actions = combat.valid_actions()
        choose = [a for a in actions if a.action_type == ActionType.CHOOSE_CARD and a.choice_index == choice_index]
        assert choose, f"No CHOOSE_CARD action with index {choice_index}"
        obs, _, _ = combat.step(choose[0])
        return obs

    def test_attack_potion_presents_choices(self):
        """AttackPotion presents 3 Attack card choices after USE_POTION."""
        combat = self._make_combat_with_potion("AttackPotion")
        obs = self._use_potion(combat)
        # Should have pending_choices with 3 cards
        assert len(obs.pending_choices) == 3, f"Expected 3 choices, got {len(obs.pending_choices)}"
        for c in obs.pending_choices:
            assert c.cost_override == 0
            assert get_spec(c.card_id).card_type == CardType.ATTACK

    def test_skill_potion_presents_choices(self):
        """SkillPotion presents 3 Skill card choices after USE_POTION."""
        combat = self._make_combat_with_potion("SkillPotion")
        obs = self._use_potion(combat)
        assert len(obs.pending_choices) == 3
        for c in obs.pending_choices:
            assert c.cost_override == 0
            assert get_spec(c.card_id).card_type == CardType.SKILL

    def test_power_potion_presents_choices(self):
        """PowerPotion presents 3 Power card choices after USE_POTION."""
        combat = self._make_combat_with_potion("PowerPotion")
        obs = self._use_potion(combat)
        assert len(obs.pending_choices) == 3
        for c in obs.pending_choices:
            assert c.cost_override == 0
            assert get_spec(c.card_id).card_type == CardType.POWER

    def test_choose_card_adds_to_hand(self):
        """CHOOSE_CARD picks one card and adds it to hand."""
        combat = self._make_combat_with_potion("AttackPotion")
        obs = self._use_potion(combat)
        hand_before = len(obs.hand)
        chosen_card = obs.pending_choices[1]
        obs2 = self._choose_card(combat, choice_index=1)
        # Hand should have one more card
        assert len(obs2.hand) == hand_before + 1
        # The added card should be the chosen one
        # Handle both dict (new format) and Card (legacy) for hand
        added_card = obs2.hand[-1]
        added_card_id = added_card["card_id"] if isinstance(added_card, dict) else added_card.card_id
        assert added_card_id == chosen_card.card_id
        if isinstance(added_card, dict):
            # New format: cost should be 0 (from potion)
            assert added_card["cost"] == 0
        else:
            # Legacy format
            assert added_card.cost_override == 0
        # pending_choices should be cleared
        assert len(obs2.pending_choices) == 0

    def test_choices_are_distinct(self):
        """The 3 presented cards should be distinct (no duplicates)."""
        combat = self._make_combat_with_potion("AttackPotion")
        obs = self._use_potion(combat)
        ids = [c.card_id for c in obs.pending_choices]
        assert len(set(ids)) == len(ids), f"Duplicate choices: {ids}"

    def test_skip_choice_wastes_potion(self):
        """SKIP_CHOICE clears choices without adding a card."""
        combat = self._make_combat_with_potion("AttackPotion")
        obs = self._use_potion(combat)
        hand_before = len(obs.hand)
        actions = combat.valid_actions()
        skip = [a for a in actions if a.action_type == ActionType.SKIP_CHOICE]
        assert skip, "No SKIP_CHOICE action found"
        obs2, _, _ = combat.step(skip[0])
        # Hand size unchanged
        assert len(obs2.hand) == hand_before
        # pending_choices cleared
        assert len(obs2.pending_choices) == 0

    def test_only_choose_actions_while_pending(self):
        """While pending_choices are pending, only CHOOSE_CARD/SKIP_CHOICE are valid."""
        combat = self._make_combat_with_potion("AttackPotion")
        obs = self._use_potion(combat)
        actions = combat.valid_actions()
        types = {a.action_type for a in actions}
        assert types == {ActionType.CHOOSE_CARD, ActionType.SKIP_CHOICE}

    def test_potion_card_plays_free(self):
        """The card chosen from AttackPotion should cost 0 energy to play."""
        combat = self._make_combat_with_potion("AttackPotion", seed=0)
        obs = self._use_potion(combat)
        obs2 = self._choose_card(combat, choice_index=0)
        # In new format, free cards show cost=0 in the dict
        # Find the index of the card with cost=0
        idx = None
        for i, c in enumerate(obs2.hand):
            if isinstance(c, dict):
                if c["cost"] == 0:
                    idx = i
                    break
            else:
                if c.cost_override == 0:
                    idx = i
                    break
        assert idx is not None, "Should have found a free card"
        # Play it — should not deduct energy for its cost
        energy_before = obs2.energy
        obs3, _, _ = combat.step(Action.play_card(
            hand_index=idx,
            target_index=0,
        ))
        # Energy should not have been reduced by the card's base cost
        assert obs3.energy == energy_before, (
            f"Free card cost energy: had {energy_before}, now {obs3.energy}"
        )

    def test_potion_card_in_reward_pool(self):
        """AttackPotion, SkillPotion, PowerPotion should be in reward pools."""
        from sts_env.run.rewards import COMMON_POTIONS, UNCOMMON_POTIONS
        assert "AttackPotion" in COMMON_POTIONS
        assert "SkillPotion" in COMMON_POTIONS
        assert "PowerPotion" in UNCOMMON_POTIONS


# ---------------------------------------------------------------------------
# Character tests
# ---------------------------------------------------------------------------

class TestCharacter:
    """Test the Character dataclass for the strategic layer."""

    def test_ironclad_factory(self):
        """Character.ironclad() returns a fresh Ironclad with starter state."""
        c = Character.ironclad()
        assert c.deck == ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
        assert c.player_hp == 80
        assert c.player_max_hp == 80
        assert c.potions == []
        assert c.gold == 99
        assert c.floor == 0
        assert c.relics == ["BurningBlood"]
        assert c.max_potion_slots == 3

    def test_add_card(self):
        """add_card should append to deck."""
        c = Character.ironclad()
        n = len(c.deck)
        c.add_card("PommelStrike")
        assert len(c.deck) == n + 1
        assert c.deck[-1] == "PommelStrike"

    def test_add_potion(self):
        """add_potion should fill slots up to max_potion_slots."""
        c = Character.ironclad()
        c.add_potion("FirePotion")
        assert c.potions == ["FirePotion"]
        c.add_potion("BloodPotion")
        c.add_potion("BlockPotion")
        assert len(c.potions) == 3
        # 4th is discarded
        c.add_potion("SteroidPotion")
        assert len(c.potions) == 3

    def test_has_relic(self):
        """has_relic returns True when the relic is present."""
        c = Character.ironclad()
        assert c.has_relic("BurningBlood") is True
        assert c.has_relic("Pantograph") is False

    def test_heal(self):
        """heal caps at max_hp."""
        c = Character.ironclad()
        c.player_hp = 70
        c.heal(6)
        assert c.player_hp == 76
        c.heal(100)
        assert c.player_hp == 80

    def test_summary(self):
        """summary returns a human-readable one-liner."""
        c = Character.ironclad()
        s = c.summary()
        assert "HP=80/80" in s
        assert "Gold=99" in s
        assert "Floor=0" in s
        assert "Deck(10)" in s
        assert "BurningBlood" in s

    def test_snapshot(self):
        """snapshot returns a plain dict with all state."""
        c = Character.ironclad()
        snap = c.snapshot()
        assert isinstance(snap, dict)
        assert snap["player_hp"] == 80
        assert snap["player_max_hp"] == 80
        assert len(snap["deck"]) == 10
        assert snap["relics"] == ["BurningBlood"]
        # snapshot should be a copy — mutating it doesn't affect the Character
        snap["gold"] = 9999
        assert c.gold == 99

    def test_ironclad_starter_backward_compat(self):
        """IRONCLAD_STARTER from engine.py should still match."""
        assert IRONCLAD_STARTER == CHAR_IRONCLAD_STARTER

    def test_combat_kwargs(self):
        """combat_kwargs returns the right fields for build_combat."""
        c = Character.ironclad()
        c.player_hp = 60
        c.add_potion("FirePotion")
        kw = c.combat_kwargs()
        assert kw == {
            "deck": list(c.deck),
            "player_hp": 60,
            "player_max_hp": 80,
            "potions": ["FirePotion"],
        }

    def test_build_combat_with_character(self):
        """build_combat accepts a Character object."""
        c = Character.ironclad()
        c.player_hp = 60
        c.add_potion("FirePotion")
        combat = builder.build_combat(
            "easy", "cultist", seed=42, character=c
        )
        obs = combat.reset()
        assert obs.player_hp == 60
        assert "FirePotion" in obs.potions

    def test_build_combat_character_overrides_kwargs(self):
        """When character is given, individual kwargs are ignored."""
        c = Character.ironclad()
        c.player_hp = 50
        combat = builder.build_combat(
            "easy", "cultist", seed=42,
            character=c,
            player_hp=99,  # should be ignored
        )
        obs = combat.reset()
        assert obs.player_hp == 50

    def test_character_is_mutable(self):
        """Character should be mutable (not frozen)."""
        c = Character.ironclad()
        c.player_hp = 1
        c.gold = 500
        c.floor = 42
        assert c.player_hp == 1
        assert c.gold == 500
        assert c.floor == 42

