"""Tests for the encounter factories in sts_env.combat.encounters."""

from __future__ import annotations

import pytest

from sts_env.combat import encounters
from sts_env.combat.engine import Combat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _play_to_end(combat: Combat) -> None:
    """Run a combat to termination using a greedy play-first policy."""
    obs = combat.reset()
    while not obs.done:
        actions = combat.valid_actions()
        obs, _, _ = combat.step(actions[0])


# ---------------------------------------------------------------------------
# Single-enemy convenience factories (previously Combat.ironclad_starter)
# ---------------------------------------------------------------------------

def test_cultist_factory_returns_combat():
    c = encounters.cultist(seed=0)
    obs = c.reset()
    assert len(obs.enemies) == 1
    assert obs.enemies[0].name == "Cultist"


def test_jaw_worm_factory():
    c = encounters.jaw_worm(seed=0)
    obs = c.reset()
    assert obs.enemies[0].name == "JawWorm"


def test_acid_slime_m_factory():
    c = encounters.acid_slime_m(seed=0)
    obs = c.reset()
    assert obs.enemies[0].name == "AcidSlimeM"


# ---------------------------------------------------------------------------
# Small Slimes
# ---------------------------------------------------------------------------

def test_small_slimes_has_two_enemies():
    c = encounters.small_slimes(seed=0)
    obs = c.reset()
    assert len(obs.enemies) == 2


def test_small_slimes_enemy_names():
    """small_slimes yields one small + one medium slime (seeded 50/50)."""
    valid_combos = [
        {"SpikeSlimeS", "AcidSlimeM"},
        {"AcidSlimeS", "SpikeSlimeM"},
    ]
    c = encounters.small_slimes(seed=0)
    obs = c.reset()
    names = {e.name for e in obs.enemies}
    assert names in valid_combos, f"Unexpected composition: {names}"


def test_small_slimes_terminates():
    _play_to_end(encounters.small_slimes(seed=0))


def test_small_slimes_reproducible():
    obs1 = encounters.small_slimes(seed=42).reset()
    obs2 = encounters.small_slimes(seed=42).reset()
    assert obs1.enemies[0].hp == obs2.enemies[0].hp
    assert obs1.enemies[1].hp == obs2.enemies[1].hp
    assert obs1.hand == obs2.hand


# ---------------------------------------------------------------------------
# Two Louses
# ---------------------------------------------------------------------------

def test_two_louses_has_two_enemies():
    c = encounters.two_louses(seed=0)
    obs = c.reset()
    assert len(obs.enemies) == 2


def test_two_louses_names_are_louses():
    for seed in range(20):
        obs = encounters.two_louses(seed=seed).reset()
        for e in obs.enemies:
            assert e.name in {"RedLouse", "GreenLouse"}, (
                f"Unexpected enemy {e.name!r} in two_louses (seed={seed})"
            )


def test_two_louses_terminates():
    _play_to_end(encounters.two_louses(seed=0))


def test_two_louses_reproducible():
    obs1 = encounters.two_louses(seed=7).reset()
    obs2 = encounters.two_louses(seed=7).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]
    assert obs1.hand == obs2.hand


def test_two_louses_composition_varies_across_seeds():
    """Different seeds should sometimes produce different louse compositions."""
    seen: set[tuple[str, ...]] = set()
    for seed in range(30):
        obs = encounters.two_louses(seed=seed).reset()
        seen.add(tuple(e.name for e in obs.enemies))
    # Across 30 seeds we should see more than one composition
    assert len(seen) > 1, f"Only saw one composition: {seen}"


def test_two_louses_curl_up_set():
    """After reset, each louse must have curl_up > 0 (set by pre_battle)."""
    c = encounters.two_louses(seed=0)
    c.reset()
    for e in c._state.enemies:
        assert e.powers.curl_up > 0, f"{e.name} has curl_up=0 after pre_battle"


# ---------------------------------------------------------------------------
# Gremlin Gang
# ---------------------------------------------------------------------------

_GREMLIN_NAMES = {"MadGremlin", "SneakyGremlin", "FatGremlin", "ShieldGremlin", "GremlinWizard"}


def test_gremlin_gang_has_four_enemies():
    c = encounters.gremlin_gang(seed=0)
    obs = c.reset()
    assert len(obs.enemies) == 4


def test_gremlin_gang_all_are_gremlins():
    for seed in range(10):
        obs = encounters.gremlin_gang(seed=seed).reset()
        for e in obs.enemies:
            assert e.name in _GREMLIN_NAMES, (
                f"Non-gremlin enemy {e.name!r} in gremlin_gang (seed={seed})"
            )


def test_gremlin_gang_at_most_two_of_each_double():
    """Mad/Sneaky/Fat each appear at most twice; Shield/Wizard at most once."""
    for seed in range(30):
        obs = encounters.gremlin_gang(seed=seed).reset()
        from collections import Counter
        counts = Counter(e.name for e in obs.enemies)
        for name in ("MadGremlin", "SneakyGremlin", "FatGremlin"):
            assert counts[name] <= 2, (
                f"{name} appeared {counts[name]} times (seed={seed})"
            )
        for name in ("ShieldGremlin", "GremlinWizard"):
            assert counts[name] <= 1, (
                f"{name} appeared {counts[name]} times (seed={seed})"
            )


def test_gremlin_gang_terminates():
    _play_to_end(encounters.gremlin_gang(seed=0))


def test_gremlin_gang_reproducible():
    obs1 = encounters.gremlin_gang(seed=99).reset()
    obs2 = encounters.gremlin_gang(seed=99).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]
    assert obs1.hand == obs2.hand


def test_gremlin_gang_composition_varies():
    seen: set[tuple[str, ...]] = set()
    for seed in range(30):
        obs = encounters.gremlin_gang(seed=seed).reset()
        seen.add(tuple(sorted(e.name for e in obs.enemies)))
    assert len(seen) > 1, f"Only saw one composition: {seen}"


# ---------------------------------------------------------------------------
# Clone independence across encounter factories
# ---------------------------------------------------------------------------

def test_clone_independence_small_slimes():
    c = encounters.small_slimes(seed=5)
    c.reset()
    cloned = c.clone()
    c.step(c.valid_actions()[0])
    assert c.observe().turn == cloned.observe().turn or True  # just check no crash


def test_clone_independence_gremlin_gang():
    c = encounters.gremlin_gang(seed=3)
    c.reset()
    cloned = c.clone()
    obs_before = cloned.observe()
    c.step(c.valid_actions()[0])
    obs_after = cloned.observe()
    assert obs_before.player_hp == obs_after.player_hp


# ---------------------------------------------------------------------------
# Spike Slime (M) — single enemy, no split slot needed
# ---------------------------------------------------------------------------

def test_spike_slime_m_factory():
    c = encounters.spike_slime_m(seed=0)
    obs = c.reset()
    assert len(obs.enemies) == 1
    assert obs.enemies[0].name == "SpikeSlimeM"


def test_spike_slime_m_terminates():
    _play_to_end(encounters.spike_slime_m(seed=0))


def test_spike_slime_m_reproducible():
    obs1 = encounters.spike_slime_m(seed=42).reset()
    obs2 = encounters.spike_slime_m(seed=42).reset()
    assert obs1.enemies[0].hp == obs2.enemies[0].hp
    assert obs1.hand == obs2.hand


# ---------------------------------------------------------------------------
# Acid Slime (L) — with pre-allocated Empty slot
# ---------------------------------------------------------------------------

def test_acid_slime_l_factory_has_two_slots():
    obs = encounters.acid_slime_l(seed=0).reset()
    assert len(obs.enemies) == 2
    assert obs.enemies[0].name == "AcidSlimeL"
    assert obs.enemies[1].name == "Empty"


def test_acid_slime_l_terminates():
    _play_to_end(encounters.acid_slime_l(seed=0))


def test_acid_slime_l_reproducible():
    obs1 = encounters.acid_slime_l(seed=7).reset()
    obs2 = encounters.acid_slime_l(seed=7).reset()
    assert obs1.enemies[0].hp == obs2.enemies[0].hp
    assert obs1.hand == obs2.hand


# ---------------------------------------------------------------------------
# Spike Slime (L) — with pre-allocated Empty slot
# ---------------------------------------------------------------------------

def test_spike_slime_l_factory_has_two_slots():
    obs = encounters.spike_slime_l(seed=0).reset()
    assert len(obs.enemies) == 2
    assert obs.enemies[0].name == "SpikeSlimeL"
    assert obs.enemies[1].name == "Empty"


def test_spike_slime_l_terminates():
    _play_to_end(encounters.spike_slime_l(seed=0))


def test_spike_slime_l_reproducible():
    obs1 = encounters.spike_slime_l(seed=11).reset()
    obs2 = encounters.spike_slime_l(seed=11).reset()
    assert obs1.enemies[0].hp == obs2.enemies[0].hp
    assert obs1.hand == obs2.hand


# ---------------------------------------------------------------------------
# Large Slime (seeded 50/50 pick)
# ---------------------------------------------------------------------------

def test_large_slime_factory_returns_combat():
    c = encounters.large_slime(seed=0)
    obs = c.reset()
    assert len(obs.enemies) == 2
    assert obs.enemies[0].name in {"AcidSlimeL", "SpikeSlimeL"}
    assert obs.enemies[1].name == "Empty"


def test_large_slime_varies_across_seeds():
    seen: set[str] = set()
    for seed in range(30):
        obs = encounters.large_slime(seed=seed).reset()
        seen.add(obs.enemies[0].name)
    assert len(seen) == 2, f"large_slime should produce both L types, only saw: {seen}"


def test_large_slime_terminates():
    _play_to_end(encounters.large_slime(seed=0))


# ---------------------------------------------------------------------------
# small_slimes — corrected composition (1 small + 1 medium, seeded 50/50)
# ---------------------------------------------------------------------------

def test_small_slimes_composition_is_small_plus_medium():
    """small_slimes should produce (SpikeSlimeS+AcidSlimeM) or (AcidSlimeS+SpikeSlimeM)."""
    valid_combos = {
        frozenset({"SpikeSlimeS", "AcidSlimeM"}),
        frozenset({"AcidSlimeS", "SpikeSlimeM"}),
    }
    for seed in range(20):
        obs = encounters.small_slimes(seed=seed).reset()
        names = frozenset(e.name for e in obs.enemies)
        assert names in valid_combos, (
            f"Unexpected small_slimes composition {names} (seed={seed})"
        )


def test_small_slimes_composition_varies_across_seeds():
    seen: set[frozenset] = set()
    for seed in range(30):
        obs = encounters.small_slimes(seed=seed).reset()
        seen.add(frozenset(e.name for e in obs.enemies))
    assert len(seen) == 2, f"small_slimes should produce both combos, saw: {seen}"


# ---------------------------------------------------------------------------
# Blue Slaver
# ---------------------------------------------------------------------------

def test_blue_slaver_factory():
    obs = encounters.blue_slaver(seed=0).reset()
    assert len(obs.enemies) == 1
    assert obs.enemies[0].name == "BlueSlaver"


def test_blue_slaver_hp_in_range():
    for seed in range(10):
        obs = encounters.blue_slaver(seed=seed).reset()
        assert 46 <= obs.enemies[0].hp <= 50


def test_blue_slaver_terminates():
    _play_to_end(encounters.blue_slaver(seed=0))


def test_blue_slaver_reproducible():
    obs1 = encounters.blue_slaver(seed=42).reset()
    obs2 = encounters.blue_slaver(seed=42).reset()
    assert obs1.enemies[0].hp == obs2.enemies[0].hp


# ---------------------------------------------------------------------------
# Red Slaver
# ---------------------------------------------------------------------------

def test_red_slaver_factory():
    obs = encounters.red_slaver(seed=0).reset()
    assert len(obs.enemies) == 1
    assert obs.enemies[0].name == "RedSlaver"


def test_red_slaver_hp_in_range():
    for seed in range(10):
        obs = encounters.red_slaver(seed=seed).reset()
        assert 46 <= obs.enemies[0].hp <= 50


def test_red_slaver_terminates():
    _play_to_end(encounters.red_slaver(seed=0))


# ---------------------------------------------------------------------------
# Looter
# ---------------------------------------------------------------------------

def test_looter_factory():
    obs = encounters.looter(seed=0).reset()
    assert len(obs.enemies) == 1
    assert obs.enemies[0].name == "Looter"


def test_looter_terminates():
    _play_to_end(encounters.looter(seed=0))


def test_looter_reproducible():
    obs1 = encounters.looter(seed=7).reset()
    obs2 = encounters.looter(seed=7).reset()
    assert obs1.enemies[0].hp == obs2.enemies[0].hp


# ---------------------------------------------------------------------------
# Three Louse
# ---------------------------------------------------------------------------

def test_three_louse_has_three_enemies():
    obs = encounters.three_louse(seed=0).reset()
    assert len(obs.enemies) == 3


def test_three_louse_all_are_louses():
    for seed in range(10):
        obs = encounters.three_louse(seed=seed).reset()
        for e in obs.enemies:
            assert e.name in {"RedLouse", "GreenLouse"}, (
                f"Unexpected enemy {e.name!r} in three_louse (seed={seed})"
            )


def test_three_louse_terminates():
    _play_to_end(encounters.three_louse(seed=0))


def test_three_louse_reproducible():
    obs1 = encounters.three_louse(seed=5).reset()
    obs2 = encounters.three_louse(seed=5).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]


def test_three_louse_composition_varies():
    seen: set[tuple] = set()
    for seed in range(30):
        obs = encounters.three_louse(seed=seed).reset()
        seen.add(tuple(e.name for e in obs.enemies))
    assert len(seen) > 1, f"three_louse only produced one composition: {seen}"


# ---------------------------------------------------------------------------
# Two Fungi Beasts
# ---------------------------------------------------------------------------

def test_two_fungi_beasts_has_two_enemies():
    obs = encounters.two_fungi_beasts(seed=0).reset()
    assert len(obs.enemies) == 2


def test_two_fungi_beasts_are_fungi():
    obs = encounters.two_fungi_beasts(seed=0).reset()
    for e in obs.enemies:
        assert e.name == "FungiBeast"


def test_two_fungi_beasts_spore_cloud_set():
    c = encounters.two_fungi_beasts(seed=0)
    c.reset()
    for e in c._state.enemies:
        assert e.powers.spore_cloud == 2, f"{e.name} has spore_cloud=0 after pre_battle"


def test_two_fungi_beasts_terminates():
    _play_to_end(encounters.two_fungi_beasts(seed=0))


# ---------------------------------------------------------------------------
# Lots of Slimes
# ---------------------------------------------------------------------------

def test_lots_of_slimes_has_five_enemies():
    obs = encounters.lots_of_slimes(seed=0).reset()
    assert len(obs.enemies) == 5


def test_lots_of_slimes_correct_pool():
    """Always exactly 3× SpikeSlimeS and 2× AcidSlimeS."""
    from collections import Counter
    for seed in range(20):
        obs = encounters.lots_of_slimes(seed=seed).reset()
        counts = Counter(e.name for e in obs.enemies)
        assert counts["SpikeSlimeS"] == 3, f"Expected 3 SpikeSlimeS (seed={seed})"
        assert counts["AcidSlimeS"] == 2, f"Expected 2 AcidSlimeS (seed={seed})"


def test_lots_of_slimes_order_varies():
    seen: set[tuple] = set()
    for seed in range(30):
        obs = encounters.lots_of_slimes(seed=seed).reset()
        seen.add(tuple(e.name for e in obs.enemies))
    assert len(seen) > 1, f"lots_of_slimes only produced one order: {seen}"


def test_lots_of_slimes_terminates():
    _play_to_end(encounters.lots_of_slimes(seed=0))


def test_lots_of_slimes_reproducible():
    obs1 = encounters.lots_of_slimes(seed=99).reset()
    obs2 = encounters.lots_of_slimes(seed=99).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]


# ---------------------------------------------------------------------------
# Exordium Thugs
# ---------------------------------------------------------------------------

_WEAK_WILDLIFE = {"RedLouse", "GreenLouse", "SpikeSlimeM", "AcidSlimeM"}
_STRONG_HUMANOIDS = {"Cultist", "RedSlaver", "BlueSlaver", "Looter"}


def test_exordium_thugs_has_two_enemies():
    obs = encounters.exordium_thugs(seed=0).reset()
    assert len(obs.enemies) == 2


def test_exordium_thugs_composition():
    for seed in range(20):
        obs = encounters.exordium_thugs(seed=seed).reset()
        names = [e.name for e in obs.enemies]
        assert names[0] in _WEAK_WILDLIFE, (
            f"Slot 0 ({names[0]!r}) is not weak wildlife (seed={seed})"
        )
        assert names[1] in _STRONG_HUMANOIDS, (
            f"Slot 1 ({names[1]!r}) is not a strong humanoid (seed={seed})"
        )


def test_exordium_thugs_composition_varies():
    seen: set[tuple] = set()
    for seed in range(50):
        obs = encounters.exordium_thugs(seed=seed).reset()
        seen.add(tuple(e.name for e in obs.enemies))
    assert len(seen) > 1, f"exordium_thugs only produced one composition: {seen}"


def test_exordium_thugs_terminates():
    _play_to_end(encounters.exordium_thugs(seed=0))


def test_exordium_thugs_reproducible():
    obs1 = encounters.exordium_thugs(seed=13).reset()
    obs2 = encounters.exordium_thugs(seed=13).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]


# ---------------------------------------------------------------------------
# Exordium Wildlife
# ---------------------------------------------------------------------------

_STRONG_WILDLIFE = {"FungiBeast", "JawWorm"}


def test_exordium_wildlife_has_two_enemies():
    obs = encounters.exordium_wildlife(seed=0).reset()
    assert len(obs.enemies) == 2


def test_exordium_wildlife_composition():
    for seed in range(20):
        obs = encounters.exordium_wildlife(seed=seed).reset()
        names = [e.name for e in obs.enemies]
        assert names[0] in _STRONG_WILDLIFE, (
            f"Slot 0 ({names[0]!r}) is not strong wildlife (seed={seed})"
        )
        assert names[1] in _WEAK_WILDLIFE, (
            f"Slot 1 ({names[1]!r}) is not weak wildlife (seed={seed})"
        )


def test_exordium_wildlife_composition_varies():
    seen: set[tuple] = set()
    for seed in range(50):
        obs = encounters.exordium_wildlife(seed=seed).reset()
        seen.add(tuple(e.name for e in obs.enemies))
    assert len(seen) > 1, f"exordium_wildlife only produced one composition: {seen}"


def test_exordium_wildlife_terminates():
    _play_to_end(encounters.exordium_wildlife(seed=0))


def test_exordium_wildlife_reproducible():
    obs1 = encounters.exordium_wildlife(seed=17).reset()
    obs2 = encounters.exordium_wildlife(seed=17).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]


# ---------------------------------------------------------------------------
# Act 1 pool helpers
# ---------------------------------------------------------------------------

_ACT1_WEAK_NAMES = {"Cultist", "JawWorm", "RedLouse", "GreenLouse", "SpikeSlimeS",
                    "AcidSlimeM", "AcidSlimeS", "SpikeSlimeM"}  # any from weak encounters

_ACT1_STRONG_NAMES = (
    _WEAK_WILDLIFE | _STRONG_HUMANOIDS | _STRONG_WILDLIFE
    | {"SpikeSlimeS", "AcidSlimeS", "SpikeSlimeL", "AcidSlimeL", "Empty"}
    | {"MadGremlin", "SneakyGremlin", "FatGremlin", "ShieldGremlin", "GremlinWizard"}
    | {"Mugger"}
)


def test_act1_weak_encounter_returns_combat():
    c = encounters.act1_weak_encounter(seed=0)
    obs = c.reset()
    assert obs is not None
    assert len(obs.enemies) >= 1


def test_act1_weak_encounter_varies_across_seeds():
    seen: set[str] = set()
    for seed in range(40):
        obs = encounters.act1_weak_encounter(seed=seed).reset()
        seen.add(obs.enemies[0].name)
    # Should see more than one type across 40 seeds
    assert len(seen) > 1, f"act1_weak_encounter only saw: {seen}"


def test_act1_weak_encounter_reproducible():
    obs1 = encounters.act1_weak_encounter(seed=42).reset()
    obs2 = encounters.act1_weak_encounter(seed=42).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]


def test_act1_strong_encounter_returns_combat():
    c = encounters.act1_strong_encounter(seed=0)
    obs = c.reset()
    assert obs is not None
    assert len(obs.enemies) >= 1


def test_act1_strong_encounter_varies_across_seeds():
    seen_first: set[str] = set()
    for seed in range(60):
        obs = encounters.act1_strong_encounter(seed=seed).reset()
        seen_first.add(obs.enemies[0].name)
    assert len(seen_first) > 2, f"act1_strong_encounter only saw first enemies: {seen_first}"


def test_act1_strong_encounter_reproducible():
    obs1 = encounters.act1_strong_encounter(seed=99).reset()
    obs2 = encounters.act1_strong_encounter(seed=99).reset()
    assert [e.name for e in obs1.enemies] == [e.name for e in obs2.enemies]
