"""Tests for the card pool query helpers."""

from __future__ import annotations

from sts_env.combat.card_pools import (
    colorless_pool,
    curse_pool,
    pool,
    status_pool,
)
from sts_env.combat.cards import CardColor, Rarity


class TestPool:
    """Tests for the per-character, per-rarity pool query."""

    def test_ironclad_common_count(self) -> None:
        cards = pool(CardColor.RED, Rarity.COMMON)
        assert len(cards) == 16

    def test_ironclad_common_members(self) -> None:
        cards = pool(CardColor.RED, Rarity.COMMON)
        expected = {
            "Anger", "Armaments", "Cleave", "Clothesline", "Flex", "Havoc",
            "Headbutt", "IronWave", "PommelStrike", "ShrugItOff",
            "SwordBoomerang", "ThunderClap", "TrueStrike", "TwinStrike",
            "WarCry", "WildStrike",
        }
        assert set(cards) == expected

    def test_ironclad_uncommon_count(self) -> None:
        cards = pool(CardColor.RED, Rarity.UNCOMMON)
        assert len(cards) == 27

    def test_ironclad_rare_count(self) -> None:
        cards = pool(CardColor.RED, Rarity.RARE)
        assert len(cards) == 12

    def test_ironclad_basic(self) -> None:
        cards = pool(CardColor.RED, Rarity.BASIC)
        assert set(cards) == {"Strike", "Defend", "Bash"}

    def test_ironclad_basic_not_in_common(self) -> None:
        commons = pool(CardColor.RED, Rarity.COMMON)
        assert "Strike" not in commons
        assert "Defend" not in commons
        assert "Bash" not in commons

    def test_no_statuses_in_character_pool(self) -> None:
        for rarity in (Rarity.BASIC, Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE):
            cards = pool(CardColor.RED, rarity)
            assert "Slimed" not in cards
            assert "Wound" not in cards
            assert "Dazed" not in cards
            assert "Burn" not in cards

    def test_no_curses_in_character_pool(self) -> None:
        for rarity in (Rarity.BASIC, Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE):
            cards = pool(CardColor.RED, rarity)
            assert "AscendersBane" not in cards

    def test_empty_pool_for_nonexistent_color_rarity(self) -> None:
        assert pool(CardColor.GREEN, Rarity.COMMON) == []


class TestStatusPool:
    def test_status_members(self) -> None:
        cards = status_pool()
        assert set(cards) == {"Slimed", "Dazed", "Wound", "Burn"}

    def test_status_count(self) -> None:
        assert len(status_pool()) == 4


class TestCursePool:
    def test_curse_members(self) -> None:
        cards = curse_pool()
        assert "AscendersBane" in cards

    def test_curse_count(self) -> None:
        assert len(curse_pool()) == 1


class TestColorlessPool:
    # --- Uncommon (15 cards) ---

    COLORLESS_UNCOMMON = {
        "BandageUp",
        "Blind",
        "DarkShackles",
        "DeepBreath",
        "Discovery",
        "Enlightenment",
        "Finesse",
        "FlashOfSteel",
        "Forethought",
        "GoodInstincts",
        "Impatience",
        "JackOfAllTrades",
        "Madness",
        "Panacea",
        "PanicButton",
        "Purity",
        "SwiftStrike",
        "Trip",
    }

    # --- Rare (15 cards) ---

    COLORLESS_RARE = {
        "Apotheosis",
        "Chrysalis",
        "DramaticEntrance",
        "HandOfGreed",
        "Magnetism",
        "MasterOfStrategy",
        "Mayhem",
        "Metamorphosis",
        "MindBlast",
        "Panache",
        "SadisticNature",
        "SecretTechnique",
        "SecretWeapon",
        "TheBomb",
        "ThinkingAhead",
        "Transmutation",
        "Violence",
    }

    def test_colorless_uncommon_count(self) -> None:
        cards = colorless_pool(Rarity.UNCOMMON)
        assert len(cards) == len(self.COLORLESS_UNCOMMON)

    def test_colorless_uncommon_members(self) -> None:
        cards = colorless_pool(Rarity.UNCOMMON)
        assert set(cards) == self.COLORLESS_UNCOMMON

    def test_colorless_rare_count(self) -> None:
        cards = colorless_pool(Rarity.RARE)
        assert len(cards) == len(self.COLORLESS_RARE)

    def test_colorless_rare_members(self) -> None:
        cards = colorless_pool(Rarity.RARE)
        assert set(cards) == self.COLORLESS_RARE

    def test_colorless_no_common(self) -> None:
        assert colorless_pool(Rarity.COMMON) == []

    def test_colorless_excludes_statuses(self) -> None:
        all_cl = colorless_pool()
        assert "Slimed" not in all_cl
        assert "Wound" not in all_cl
        assert "Dazed" not in all_cl
        assert "Burn" not in all_cl

    def test_colorless_excludes_curses(self) -> None:
        all_cl = colorless_pool()
        assert "AscendersBane" not in all_cl
