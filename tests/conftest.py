"""Shared pytest fixtures."""

import pytest

from sts_env.combat.deck import Piles
from sts_env.combat.player_state import PlayerState
from sts_env.combat.rng import RNG


@pytest.fixture()
def rng() -> RNG:
    return RNG(seed=0)


@pytest.fixture()
def starter_ironclad() -> PlayerState:
    """A fresh Ironclad PlayerState (starter deck, 80 HP, BurningBlood)."""
    return PlayerState.ironclad_starter()


@pytest.fixture()
def piles() -> Piles:
    return Piles(
        draw=["Strike", "Defend", "Bash"],
        hand=[],
        discard=["Strike_2", "Defend_2"],
        exhaust=[],
    )
