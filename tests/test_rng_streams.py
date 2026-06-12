"""Tests for domain-separated, location-keyed run RNG."""

from __future__ import annotations

from sts_env.combat.rng import RNG
from sts_env.run.rewards import Room, roll_combat_reward_offer
from sts_env.run.rng_streams import RunRNG, mix_keys
from sts_env.run.shop import generate_shop
from sts_env.run.character import Character


class TestMixKeys:
    def test_stable_for_same_inputs(self):
        a = mix_keys(42, "event_pick", 5)
        b = mix_keys(42, "event_pick", 5)
        assert a == b

    def test_differs_by_domain(self):
        assert mix_keys(42, "event_pick", 5) != mix_keys(42, "shop_card", 5)

    def test_differs_by_floor(self):
        assert mix_keys(42, "event_pick", 3) != mix_keys(42, "event_pick", 8)


class TestRunRNGDerive:
    def test_same_domain_keys_produce_identical_streams(self):
        run_rng = RunRNG(99)
        r1 = run_rng.derive("card_reward", 7)
        r2 = run_rng.derive("card_reward", 7)
        assert [r1.randint(0, 100) for _ in range(5)] == [
            r2.randint(0, 100) for _ in range(5)
        ]

    def test_domain_isolation(self):
        """Extra draws in one domain must not affect another domain at same floor."""
        run_rng = RunRNG(123)
        event_rng = run_rng.derive("event_resolve", 3, "Big Fish", 0, 0)
        for _ in range(50):
            event_rng.random()

        shop_a = generate_shop(run_rng, floor=5, character=Character.ironclad())
        reward_a, _ = roll_combat_reward_offer(
            run_rng, floor=7, room=Room.MONSTER
        )
        pick_a = run_rng.derive("event_pick", 8).choice(["A", "B", "C"])

        shop_b = generate_shop(run_rng, floor=5, character=Character.ironclad())
        reward_b, _ = roll_combat_reward_offer(
            run_rng, floor=7, room=Room.MONSTER
        )
        pick_b = run_rng.derive("event_pick", 8).choice(["A", "B", "C"])

        assert shop_a == shop_b
        assert reward_a == reward_b
        assert pick_a == pick_b

    def test_route_isolation_counterfactual(self):
        """Floor-8 outcomes unchanged after extra floor-3 event draws."""
        run_rng = RunRNG(456)
        baseline_shop = generate_shop(run_rng, floor=8, character=Character.ironclad())
        baseline_reward, _ = roll_combat_reward_offer(
            run_rng, floor=8, room=Room.ELITE
        )
        baseline_event = run_rng.derive("event_pick", 8).choice(list("ABCDEF"))

        noisy = RunRNG(456)
        noise_rng = noisy.derive("event_resolve", 3, "Dead Adventurer", 0, 0)
        for _ in range(30):
            noise_rng.randint(0, 99)

        assert generate_shop(noisy, floor=8, character=Character.ironclad()) == baseline_shop
        offer, _ = roll_combat_reward_offer(noisy, floor=8, room=Room.ELITE)
        assert offer == baseline_reward
        assert noisy.derive("event_pick", 8).choice(list("ABCDEF")) == baseline_event

    def test_combat_seed_unchanged(self):
        assert RunRNG(42).combat_seed(5) == 42 * 1000 + 5
        assert RunRNG(7).combat_seed(3) == 7003
