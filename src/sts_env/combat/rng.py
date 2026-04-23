"""Seeded RNG wrapper.

All random decisions in combat (shuffle order, enemy intent rolls, HP rolls)
must go through this wrapper so the same seed always produces the same game.
"""

import random
from typing import MutableSequence, TypeVar

T = TypeVar("T")


class RNG:
    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def shuffle(self, seq: MutableSequence[T]) -> None:
        self._rng.shuffle(seq)

    def randint(self, a: int, b: int) -> int:
        """Return a random integer N such that a <= N <= b."""
        return self._rng.randint(a, b)

    def choice(self, seq: list[T]) -> T:
        return self._rng.choice(seq)

    def random(self) -> float:
        return self._rng.random()
