"""Shared pytest fixtures."""

import pytest

from sts_env.combat.deck import Piles
from sts_env.combat.rng import RNG


@pytest.fixture()
def rng() -> RNG:
    return RNG(seed=0)


@pytest.fixture()
def piles() -> Piles:
    return Piles(
        draw=["Strike", "Defend", "Bash"],
        hand=[],
        discard=["Strike_2", "Defend_2"],
        exhaust=[],
    )
