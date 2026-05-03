"""Shared helpers used by both run-level and combat-level code."""


def increase_max_hp(obj: object, amount: int) -> None:
    """Increase max HP by *amount* and also heal by the same amount.

    Every max-HP increase in Slay the Spire also heals the player.
    Works with any object that has ``player_hp`` and ``player_max_hp``
    attributes (``Character``, ``CombatState``, etc.).
    """
    obj.player_max_hp += amount  # type: ignore[attr-defined]
    obj.player_hp = min(  # type: ignore[attr-defined]
        obj.player_hp + amount,  # type: ignore[attr-defined]
        obj.player_max_hp,  # type: ignore[attr-defined]
    )
