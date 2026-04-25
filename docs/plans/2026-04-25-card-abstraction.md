# Card Abstraction Refactor

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace bare `str` card identities with a `Card` dataclass, enabling per-instance state (cost overrides, upgrades). Unblocks AttackPotion/SkillPotion/PowerPotion.

**Architecture:** Introduce a frozen `Card` dataclass in a new `card.py` module. `Piles` holds `list[Card]` internally. The API boundary (Observation, Combat constructor, reward rollers) continues to accept/emit plain `str` for backward compatibility — conversion happens at the boundary.

**Tech Stack:** Python 3.13, dataclasses, pytest

---

## Design Decisions

### Card identity vs Card instance
- `card_id: str` = the card *type* (e.g., "Strike"). Maps 1:1 to a `CardSpec`.
- A `Card` object is one *copy* of that card, potentially with instance-specific modifiers.
- Two `Card("Strike")` objects are equal and interchangeable if their modifiers match.
- Transposition table keys use `Card` tuples (card_id + modifiers) for correctness.

### API boundary
- `Combat(deck=["Strike", "Defend", ...])` — still takes `list[str]` (convenience)
- `Observation.hand: list[Card]` — agents see full Card instances (can check cost_override, upgraded)
- `Observation.draw_pile: dict[str, int]` — counts by card_id (cost_override cleared on discard, so no per-instance info needed)
- `Observation.discard_pile: dict[str, int]` — same
- `Observation.exhaust_pile: dict[str, int]` — same
- Agents import `Card` from `sts_env.combat.card` — already in their dependency tree

### cost_override semantics
- `cost_override: int | None = None` — None means "use spec cost"
- Set by potion-generated cards (Attack/Skill/Power Potion add a card with `cost_override=0`)
- Cleared when card moves to discard (cost_override is ephemeral — only applies on the turn it enters hand)
- Actually: cost_override should persist through the combat. In StS, the card costs 0 for the turn it was generated. But on redraw, it costs normal. The simplest correct model: cost_override is set when the card is created by a potion, and cleared when the card is discarded at end of turn.

Wait — this means cost_override needs to be mutable, or we need to replace the Card at end of turn. Since Card is frozen, the cleanest approach: when a potion creates a card, it sets `cost_override=0`. At end-of-turn discard, the engine replaces each Card with `Card(card_id=c.card_id)` (no override) before moving to discard. This is a small but important detail.

Actually, simpler: just don't make Card frozen. Use `slots=True` for performance but allow mutation of `cost_override`. The transposition table should snapshot the state anyway (it builds tuples).

**Revised:** `Card` is a mutable dataclass with `slots=True`. This lets us clear `cost_override` at end of turn without object replacement. Transposition table keys explicitly build tuples from Card fields.

### Where cards are created (string → Card conversion)
1. `Combat.__init__` converts `list[str]` deck → `list[Card]`
2. Card handlers that create cards: `Card("Anger")`, `Card("WildStrike")`, `Card("Dazed")`, `Card("RecklessCharge")` → `Card("Dazed")`
3. Enemy intents that add status cards: `Card("Dazed")`
4. Reward rollers return `list[str]` → converted at the run level when adding to deck

### Where cards are consumed (Card → str conversion)
1. `Observation.hand` = `[c.card_id for c in state.piles.hand]`
2. `Observation.draw_pile` = `Counter(c.card_id for c in state.piles.draw)`
3. `base._fmt_action` receives `hand: list[str]` — no change needed
4. Logging always uses `.card_id`

---

## File-by-file changes

### A. New file: `src/sts_env/combat/card.py`
```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class Card:
    card_id: str
    cost_override: int | None = None  # None = use spec cost
    upgraded: int = 0                 # 0 = base, future use

    def to_key(self) -> tuple:
        """Hashable key for transposition tables."""
        return (self.card_id, self.cost_override, self.upgraded)

    def clear_cost_override(self) -> None:
        """Reset cost override (called at end of turn for potion-generated cards)."""
        self.cost_override = None
```

### B. Modify: `src/sts_env/combat/deck.py` (Piles)
- Type changes: `list[str]` → `list[Card]`
- `draw_cards()` returns `list[Card]`, appends `Card` to hand
- `place_on_top(card: str | Card)` → accepts both, wraps str
- `add_to_discard(card: str | Card)` → accepts both, wraps str
- `discard_hand()` moves `Card` objects

### C. Modify: `src/sts_env/combat/cards.py`
- `play_card()`: get `card = state.piles.hand[hand_index]` (now a Card), use `card.card_id` for spec lookup, use `card.cost_override ?? spec.cost` for energy
- Card handlers that create cards: use `Card("Anger")` instead of `"Anger"`

### D. Modify: `src/sts_env/combat/engine.py`
- `__init__`: convert `deck: list[str]` → `list[Card]`
- `valid_actions()`: use `card.card_id` for spec lookup, use card cost
- `step()`: same
- `_observe()`: convert Card lists to str for Observation
- `_resolve_end_of_player_turn()`: clear cost_override on discarded cards
- Dazed exhaust cleanup: compare with `Card("Dazed")` or check `.card_id`

### E. Modify: `src/sts_env/combat/state.py`
- `Observation.hand: list[str]` → `list[Card]`
- Import `Card` from `.card`
- `draw_pile`, `discard_pile`, `exhaust_pile` stay `dict[str, int]`

### F. Modify: `src/sts_env/combat/potions.py`
- SwiftPotion: `draw_cards` returns `list[Card]` — already appends to hand, no change
- New potions (Attack/Skill/Power): create `Card(random_card_id, cost_override=0)`, append to hand

### G. Modify: `src/sts_env/combat/enemies.py`
- Status card creation: use `Card("Dazed")` instead of `"Dazed"`

### H. Modify: `src/sts_agent/battle/tree_search.py`
- `_state_key_base`: use `tuple(sorted(c.to_key() for c in s.piles.hand))` etc.
- `_dedupe_actions`: use `card.card_id` from `s.piles.hand[action.hand_index]`
- `_order_key`: same
- Card tier lookup: use `card.card_id`

### I. Modify: `src/sts_agent/battle/mcts.py`
- `_action_concept_key`: include `cost_override` in key (same reasoning as tree_search dedup)
  ```python
  card = s.piles.hand[action.hand_index]
  return ("CARD", card.card_id, card.cost_override, action.target_index)
  ```

### J. Modify: `src/sts_agent/battle/base.py`
- `_fmt_action`: hand param becomes `list[Card]`, use `.card_id` for display
- `_fmt_obs`: `obs.hand` is now `list[Card]`, join with `.card_id`
- `run_agent`/`run_planner` logging: use `.card_id` for hand display

### K. Modify: tests in both repos
- Direct `piles.hand = ["Strike", ...]` → `piles.hand = [Card("Strike"), ...]`
- `piles.hand[action.hand_index]` → `.card_id` where needed
- `.count("Dazed")` → count by card_id
- `obs.hand.index("Strike")` stays (Observation.hand is still list[str])

---

## Task breakdown

### Task 1: Create Card dataclass
**Files:** Create `src/sts_env/combat/card.py`
- Define `Card` with `card_id`, `cost_override`, `upgraded`, `to_key()`, `clear_cost_override()`
- Add `__eq__` and `__hash__` based on all fields (for set/dict usage)

### Task 2: Update deck.py (Piles)
**Files:** Modify `src/sts_env/combat/deck.py`
- Import `Card`
- Change type hints: `list[str]` → `list[Card]`
- Update `place_on_top`, `add_to_discard` to accept `str | Card`, wrapping str
- Update `draw_cards` — pop returns Card, append Card
- Update `discard_hand` — moves Card objects

### Task 3: Update cards.py (play_card + handlers)
**Files:** Modify `src/sts_env/combat/cards.py`
- Import `Card`
- `play_card()`: get Card from hand, use `card.card_id` for spec, use cost_override
- Card handlers creating cards: `Card("Anger")`, `Card("WildStrike")`, `Card("Dazed")`

### Task 4: Update engine.py
**Files:** Modify `src/sts_env/combat/engine.py`
- Import `Card`
- Convert deck strings to Cards in `__init__`
- `valid_actions()`: get card from hand, use `.card_id` and cost
- `step()`: use `.card_id` for type checks
- `_observe()`: convert Card→str for Observation
- End-of-turn: clear cost_override on discarded cards
- Dazed cleanup: compare `.card_id == "Dazed"`

### Task 5: Update enemies.py
**Files:** Modify `src/sts_env/combat/enemies.py`
- Status card creation: wrap in `Card()`

### Task 6: Update tree_search.py + mcts.py state keys
### H. Modify: `src/sts_agent/battle/tree_search.py`
- `_state_key_base`: use `Card.to_key()` for pile entries
  ```python
  tuple(sorted(c.to_key() for c in s.piles.hand))
  ```
- `_dedupe_actions`: action key must include `cost_override` — a free Strike and a regular Strike produce different successors
  ```python
  card = s.piles.hand[action.hand_index]
  key = ("CARD", card.card_id, card.cost_override, action.target_index)
  ```
- `_order_key`: use `card.card_id` for tier lookup, factor effective cost into sort so free cards sort first
  ```python
  effective_cost = card.cost_override if card.cost_override is not None else spec.cost
  return (tier, effective_cost, target_hp, card.card_id)
  ```
- **Never hash Card directly** — always use `.to_key()` tuple (Card is mutable)
- `_action_concept_key`: use `.card_id`

### Task 7: Update tests
**Files:** Modify `tests/test_scenario3.py` (sts_env), `tests/battle/test_tree_search.py` (sts_agent)
- Import `Card` where needed
- Wrap string literals in `Card()` for direct pile manipulation
- `obs.hand.index("Strike")` → find by `.card_id`, or compare Card objects
- `obs.hand == ...` → compare Card objects or `[c.card_id for c in obs.hand]`

### Task 8: Run full test suite and fix
- `cd ~/projects/sts_env && uv run pytest tests/ -v`
- `cd ~/projects/sts_agent && uv run pytest tests/ -v`
- Fix any remaining type mismatches

### Task 9: Add Attack/Skill/Power Potion handlers
**Files:** Modify `src/sts_env/combat/potions.py`, `src/sts_env/combat/cards.py`
- Import `Card` from card module
- Filter `_SPECS` by `CardType` to build type-specific pools
- Implement 3 new potion handlers that create `Card(random_id, cost_override=0)` and append to hand

### Task 10: Add potion reward entries + tests
**Files:** Modify `src/sts_env/run/rewards.py`, `tests/test_scenario3.py`
- Add new potions to reward pools
- Test: potion creates card in hand, card costs 0, after discard costs normal

---

## Verification
```bash
cd ~/projects/sts_env && uv run pytest tests/ -v
cd ~/projects/sts_agent && uv run pytest tests/ -v
```
All existing tests pass. New potion tests verify cost-override lifecycle.
