# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
just test          # run pytest tests/ -q
just test-v        # run tests with verbose output
just run <pattern> # run a specific test file or -k pattern
just check         # build oracle then run all tests
just oracle        # build the sts_lightspeed C++ module
```

Run a single test: `just run tests/test_deck.py` or `pytest tests/test_deck.py -q`.

The `oracle` target runs `./scripts/build_oracle.sh`, which compiles the C++ `sts_lightspeed` pybind11 module (from the `third_party/` submodule) and installs it to the active venv. Requires g++, cmake, and python3.

## Concerns

sts_env concerns itself with game state. There is a sibling project, sts_agent, which concerns itself with all decision making.

## Architecture

**sts_env** implements a Slay the Spire roguelike environment for RL research. There are two independent layers:

### Combat layer (`src/sts_env/combat/`)

Handles single-combat turn-based battles. The public interface is `Combat`:

- `Combat.reset()` → initializes state, returns `Observation`
- `Combat.step(action)` → processes one action, returns `Observation`
- `Combat.observe()` → read-only public snapshot

`CombatState` is the mutable core. `Action` and `Observation` are frozen dataclasses.

**Effect stack**: Complex interactions (multi-card sequences, choices mid-play) are handled via a LIFO pending stack on `CombatState`. A `ChoiceFrame` pauses execution waiting for agent input; a `ThunkFrame` auto-drains pending callbacks. This is what makes `step()` sometimes return a `CHOOSE_CARD` observation mid-turn.

**Card system**: `CardSpec` is a frozen dataclass with declarative effect fields (`attack`, `block`, `strength`, `vulnerable`, `exhaust`, etc.). For cards that can't be expressed declaratively, a `custom` callable on the spec handles the full effect. Upgrades are applied via a "+" suffix on `card_id` that merges upgrade deltas onto the base spec.

**Event/listener system**: `Event` enum + pub/sub registry on `CombatState.subscribers`. Handlers are registered with `@listener` decorators in `listeners_powers.py`, `listeners_enemies.py`, `listeners_relics.py`, `listeners_potions.py`. Crucially, subscribers are stored as strings `(Event, owner_name, listener_name)` — not callables — so `CombatState` can be safely `deepcopy`'d without closure issues.

### Run layer (`src/sts_env/run/`)

Manages the full Act 1 adventure: map navigation, deck building, HP carryover, and combat sequencing.

- **`Character`**: persistent player snapshot (deck, HP, relics, potions, gold, floor)
- **`RunEventBus`**: run-level events (`card_added`, `relic_added`, `combat_won`, etc.) with listener hooks for relic effects
- **`Map`**: 15-floor branching map with room types (Monster/Elite/Rest/Boss/Event/Shop)
- **`Builder.build_combat()`**: resolves `(Character, encounter_type, encounter_id)` → `Combat` instance with character state injected
- **`EncounterQueue`**: faithful StS pool-based monster and elite scheduling (tracks seen encounters to avoid repeats)
- **`Rewards`** (`rewards.py`): post-combat card/potion/relic selection
- **`Relics`** (`relics.py`): run-level relic effects via `RunEventBus`

The top-level function is `run_act1(agent, seed)` in `orchestrator.py`.

### Data flow

```
EncounterQueue → Builder.build_combat() → Combat (tactical)
                                               ↓
                 Character ←── outcomes ── combat result
                     ↓
              Rewards (card/relic/potion choice)
                     ↓
              next encounter
```

### Agent protocol

Agents implement `RunAgentProtocol` (duck-typed, no inheritance): methods for `pick_card`, `pick_potion`, `pick_relic`, and `combat_agent` (which itself handles `Combat.step()` in a loop). See `agents.py` for the `GreedyAgent` reference implementation.

## Key design decisions

- **Deepcopy safety**: `CombatState` must support `deepcopy` for MCTS / tree search. String-keyed subscriber registry (not callables) is the mechanism that enables this.
- **Seeded RNG**: All randomness flows through `RNG(seed)` wrapper → fully deterministic replay given a seed.
- **Declarative + escape hatch**: ~80% of cards use `CardSpec` declarative fields; ~20% need `custom` handlers. Prefer declarative; add `custom` only when the effect truly can't be expressed.
- **No inheritance in card/enemy/relic specs**: Everything is data (`CardSpec`, `EnemySpec`, `RelicSpec` frozen dataclasses), not class hierarchies.

## Information hiding (agent visibility)

Agents must not have access to hidden information that a real Slay the Spire player would not know. The encounter system is the primary example:

**Open knowledge** (may be exposed to agents / included in prompts):
- Pool composition: `WEAK_POOL`, `STRONG_POOL`, `ELITE_POOL`, `BOSS_POOL` and their weights
- Generation rules: 3 weak → 1 first-strong → 12 strong; 2-back no-repeat; no consecutive elite repeats
- Encounter count consumed so far (e.g. "you've fought 2 hallway monsters, 1 elite")
- Which encounters have been seen (a player remembers their fights)
- Boss identity — the boss is revealed on the map as soon as it's generated

**Hidden information** (must NOT be exposed to agents):
- The pre-generated `monster_list[monster_offset:]` — exact upcoming encounters from the queue
- The pre-generated `elite_list[elite_offset:]` — exact upcoming elites
- RNG seed or any internal state that would let an agent predict future rolls

In practice: when building prompts or tool parameters for the strategy agent, derive "possible remaining encounters" from pool composition + filtering rules + encounters already seen — never from the queue itself.

## Implementation status

Several areas are stubs or partially implemented (as of the current codebase):
- EVENT, SHOP, and TREASURE rooms are no-ops (logged but do nothing)
- Most relics are cosmetic — only `BurningBlood` has a mechanical effect in the combat layer
- Some complex cards (`DemonForm`, `Corruption`, etc.) are no-op stubs
- `sts_lightspeed` oracle module is used for validation/comparison, not the primary implementation

## Reference implementation

The `third_party/sts_lightspeed/` directory contains a C++ reimplementation of Slay the Spire (sts_lightspeed by gamerpuppy). This is the authoritative reference for game mechanics. Key locations:

- `include/constants/Events.h` — event enum, IDs, pool definitions per act
- `src/game/GameContext.cpp` — event setup (`setupEvent`) and resolution (`chooseEventOption`)
- `include/constants/MonsterEncounters.h` — encounter IDs including event-specific ones (e.g. `MASKED_BANDITS_EVENT`, `MUSHROOMS_EVENT`, `LAGAVULIN_EVENT`)
- `src/game/Game.cpp`, `src/game/Deck.cpp` — card/deck operations

When implementing or fixing events, always cross-check against `GameContext.cpp::chooseEventOption` for correct outcomes, RNG usage, and edge cases.
