"""Room-scoped character change logging via snapshot diff."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .character import Character


@dataclass(frozen=True)
class CharacterChange:
    """One net change to tracked character fields within a room."""

    field: str
    delta: int | None = None
    value: str | None = None


@dataclass(frozen=True)
class CharacterSnapshot:
    """Point-in-time snapshot of character fields included in room diffs."""

    player_hp: int
    player_max_hp: int
    gold: int
    deck: tuple[str, ...]
    potions: tuple[str, ...]
    relics: tuple[str, ...]


@dataclass(frozen=True)
class RoomRecord:
    """All net character changes during one room visit."""

    floor: int
    room_type: str
    changes: tuple[CharacterChange, ...]


def snapshot_from_character(character: Character) -> CharacterSnapshot:
    """Capture log-relevant character state."""
    return CharacterSnapshot(
        player_hp=character.player_hp,
        player_max_hp=character.player_max_hp,
        gold=character.gold,
        deck=tuple(character.deck),
        potions=tuple(character.potions),
        relics=tuple(character.relics),
    )


def finish_room(
    before: CharacterSnapshot,
    character: Character,
    *,
    floor: int,
    room_type: str,
) -> RoomRecord:
    """Diff character against a room-entry snapshot and build a room record."""
    after = snapshot_from_character(character)
    return RoomRecord(
        floor=floor,
        room_type=room_type,
        changes=diff_snapshots(before, after),
    )


def diff_snapshots(
    before: CharacterSnapshot,
    after: CharacterSnapshot,
) -> tuple[CharacterChange, ...]:
    """Compute net character changes between two snapshots."""
    changes: list[CharacterChange] = []

    if after.player_max_hp != before.player_max_hp:
        changes.append(
            CharacterChange("max_hp", delta=after.player_max_hp - before.player_max_hp)
        )
    if after.player_hp != before.player_hp:
        changes.append(CharacterChange("hp", delta=after.player_hp - before.player_hp))
    if after.gold != before.gold:
        changes.append(CharacterChange("gold", delta=after.gold - before.gold))

    changes.extend(_diff_multiset("card", before.deck, after.deck))
    changes.extend(_diff_multiset("potion", before.potions, after.potions))
    changes.extend(_diff_relics(before.relics, after.relics))

    return tuple(changes)


def _diff_multiset(
    prefix: str,
    before: tuple[str, ...],
    after: tuple[str, ...],
) -> list[CharacterChange]:
    """Diff deck or potion multisets, collapsing single-card upgrades."""
    before_counts = Counter(before)
    after_counts = Counter(after)

    removed: list[str] = []
    added: list[str] = []
    upgraded: list[str] = []

    all_ids = set(before_counts) | set(after_counts)
    for item_id in sorted(all_ids):
        delta = after_counts[item_id] - before_counts[item_id]
        if delta > 0:
            added.extend([item_id] * delta)
        elif delta < 0:
            removed.extend([item_id] * (-delta))

    if prefix == "card":
        upgraded, removed, added = _collapse_upgrades(removed, added)

    changes: list[CharacterChange] = []
    for item_id in removed:
        changes.append(CharacterChange(f"{prefix}_removed", value=item_id))
    for item_id in added:
        changes.append(CharacterChange(f"{prefix}_added", value=item_id))
    for base_id in upgraded:
        changes.append(CharacterChange("card_upgraded", value=base_id))
    return changes


def _collapse_upgrades(
    removed: list[str],
    added: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Collapse paired remove-X / add-X+ into card_upgraded entries."""
    upgraded: list[str] = []
    removed_copy = removed.copy()
    added_copy = added.copy()

    for base_id in list(removed_copy):
        upgraded_id = base_id + "+"
        if upgraded_id in added_copy:
            removed_copy.remove(base_id)
            added_copy.remove(upgraded_id)
            upgraded.append(base_id)

    return upgraded, removed_copy, added_copy


def _diff_relics(
    before: tuple[str, ...],
    after: tuple[str, ...],
) -> list[CharacterChange]:
    """Relics are only added in Act 1 — report set additions."""
    new_relics = set(after) - set(before)
    return [CharacterChange("relic_added", value=relic_id) for relic_id in sorted(new_relics)]
