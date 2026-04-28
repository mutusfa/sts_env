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


def curse_pool() -> list[str]:
    """Return all curse card IDs."""
    return [
        spec.card_id
        for spec in all_specs().values()
        if spec.card_type == CardType.CURSE
    ]
