"""Card pool query helpers.

All pools are derived from the card spec registry — single source of truth.
Adding a card via ``register()`` with the right ``color`` / ``rarity`` /
``card_type`` fields automatically lands it in the correct pool.

Status and curse pools are filtered by ``card_type``, not by color/rarity,
so they are never accidentally included in reward or shop pools.
"""

from __future__ import annotations

from .cards import CardColor, CardType, Rarity, all_specs


def pool(color: CardColor, rarity: Rarity) -> list[str]:
    """Return card IDs for a given character color and rarity.

    Excludes statuses and curses regardless of their color/rarity values.
    """
    return [
        spec.card_id
        for spec in all_specs().values()
        if spec.color == color
        and spec.rarity == rarity
        and spec.card_type not in (CardType.STATUS, CardType.CURSE)
    ]


def typed_pool(color: CardColor, card_type: CardType, rarity: Rarity) -> list[str]:
    """Return card IDs for a given character color, card type, and rarity.

    Used by the shop to build per-type buckets (ATTACK/SKILL/POWER) matching
    C++ Shop::getRandomClassCardOfTypeAndRarity.
    """
    return [
        spec.card_id
        for spec in all_specs().values()
        if spec.color == color
        and spec.card_type == card_type
        and spec.rarity == rarity
    ]


def colorless_pool(rarity: Rarity | None = None) -> list[str]:
    """Return colorless card IDs, optionally filtered by rarity.

    Excludes status cards (which are also tagged COLORLESS).
    """
    specs = all_specs().values()
    if rarity is not None:
        specs = [s for s in specs if s.rarity == rarity]
    return [
        spec.card_id
        for spec in specs
        if spec.color == CardColor.COLORLESS
        and spec.card_type not in (CardType.STATUS, CardType.CURSE)
    ]


def status_pool() -> list[str]:
    """Return all status card IDs."""
    return [
        spec.card_id
        for spec in all_specs().values()
        if spec.card_type == CardType.STATUS
    ]


STANDARD_CURSE_IDS: frozenset[str] = frozenset({
    "Injury",
    "Doubt",
    "Regret",
    "Pain",
    "Shame",
    "Writhe",
    "Decay",
    "Normality",
})


def curse_pool() -> list[str]:
    """Return standard curse IDs used by events/rewards (excludes special curses)."""
    return sorted(STANDARD_CURSE_IDS)
