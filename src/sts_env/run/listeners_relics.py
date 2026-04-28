"""Run-layer relic listeners.

Relics subscribe at Character creation via ``bus.wire_relics()``.
"""

from __future__ import annotations

from .bus import RunEvent, listener, RELI_RUN_SUBSCRIPTIONS


# ---------------------------------------------------------------------------
# CeramicFish: gain 9 gold whenever a card is added to the deck
# ---------------------------------------------------------------------------

@listener(RunEvent.CARD_ADDED, "ceramic_fish", subscriptions=[(RELI_RUN_SUBSCRIPTIONS, "CeramicFish")])
def _ceramic_fish(payload: dict) -> None:
    character = payload.get("character")
    if character is None:
        return
    character.gold += 9


# ---------------------------------------------------------------------------
# BustedCrown: card rewards offer 1 card instead of 3
# ---------------------------------------------------------------------------

@listener(RunEvent.CARD_REWARD_COUNT, "busted_crown", subscriptions=[(RELI_RUN_SUBSCRIPTIONS, "BustedCrown")])
def _busted_crown(payload: dict) -> None:
    payload["count"] = max(1, payload["count"] - 2)
