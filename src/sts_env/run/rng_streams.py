"""Run-level RNG streams keyed by domain and location.

Each observable random outcome (event identity at a floor, shop stock, card
rewards, etc.) is derived from ``(master_seed, domain, *keys)`` rather than a
single advancing stream.  That keeps floor-N outcomes stable when earlier floors
consume different amounts of randomness — required for counterfactual paired
rollouts in strategic agent research.

Combat randomness remains per-fight via :meth:`RunRNG.combat_seed` and is
unchanged by this module.

Skipping a room does **not** consume that floor's RNG (by design): outcomes at
floor N depend only on N's domain keys, not on how many rooms were visited.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from ..combat.rng import RNG

DOMAIN_SALTS: dict[str, int] = {
    "map": 0x4D415000,
    "neow": 0xCA7,
    "monster_queue": 0xCAFE0001,
    "elite_queue": 0xCAFE0002,
    "boss": 0xCAFE0003,
    "event_pick": 0xE7E00001,
    "event_resolve": 0xE7E00002,
    "shop_card": 0x5C0C0001,
    "shop_merchant": 0x5C0C0002,
    "shop_potion": 0x5C0C0003,
    "treasure": 0x7E350001,
    "card_reward": 0xBEEF,
    "relic": 0xBEEF0002,
    "transform": 0x7E4E0001,
    "gold": 0x60D00001,
}


def _domain_salt(domain: str) -> int:
    if domain in DOMAIN_SALTS:
        return DOMAIN_SALTS[domain]
    return zlib.crc32(domain.encode()) & 0xFFFFFFFF


def mix_keys(seed: int, domain: str, *keys: int | str) -> int:
    """Deterministically mix master seed, domain salt, and optional keys."""
    salt = _domain_salt(domain)
    if keys:
        key_blob = "|".join(str(k) for k in keys).encode()
        key_mix = zlib.crc32(key_blob) & 0xFFFFFFFF
    else:
        key_mix = 0
    return (seed ^ salt ^ key_mix) & 0xFFFFFFFF


@dataclass(frozen=True)
class RunRNG:
    """Master run seed with stable per-domain / per-floor RNG derivation."""

    seed: int

    def derive(self, domain: str, *keys: int | str) -> RNG:
        """Return a fresh RNG for ``(seed, domain, *keys)``."""
        return RNG(mix_keys(self.seed, domain, *keys))

    def combat_seed(self, floor: int) -> int:
        """Per-combat seed (unchanged from orchestrator convention)."""
        return self.seed * 1000 + floor
