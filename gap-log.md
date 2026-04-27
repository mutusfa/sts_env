# Gap Log: Slay the Spire Scenario 3 — Act 1 Runner

**Started:** 2026-04-25
**Mode:** in-session
**Goal:** Play out scenario 3: 3 hallway fights (easy) + 1 hallway (hard) + 1 elite.
  - Strategic layer (card pick, potion saving) is out of scope.
  - Random card on card rewards is acceptable.
  - Using potion immediately is acceptable.
  - Ironclad's starter relic (Burning Blood: heal 6 HP at end of combat) must be implemented.

## Iteration 0 — Initial State
Status: Both repos cloned, codebase understood.

### What Exists
**sts_env:** Full combat engine with enemies, cards, potions, powers, deck, encounters.
  - 20+ enemies (all Act 1), 20+ cards (Ironclad starter + rewards), 13 potions.
  - Encounter factories: single enemies, multi-enemy, pool selectors (weak/strong).
  - No run-level state (no HP carryover, no relics, no card rewards, no map).

**sts_agent:** BattlePlanner (TreeSearch, MCTS), BattleAgent (Random), runners, CLI.
  - No run-level orchestration (no multi-combat runner, no relic logic, no card reward logic).

### Gaps Identified
1. [CRITICAL] No RunState — no HP tracking across combats, no relic tracking
2. [CRITICAL] No Burning Blood relic — heal 6 HP after combat wins
3. [CRITICAL] No card reward system — after combat, pick from 3 random cards
4. [CRITICAL] No scenario runner — can't chain 3 easy + 1 hard + 1 elite encounters
5. [HIGH] No elite encounter definitions (Gremlin Nob, Lagavulin, 3 Sentries)
6. [HIGH] No "hard hallway" encounter definitions (strong pool)
7. [MEDIUM] No potion slot management across combats (start with 3 empty slots, can get from rewards)
8. [LOW] No map/floor tracking

---

## Iteration 1 — Review
Status: Scenario 3 runner works end-to-end. MCTSPlanner clears 5 floors with 63/80 HP remaining.

### Gaps Identified
1. [CRITICAL] Gremlin Nob Bellow doesn't reduce player energy — entire point of the fight
2. [CRITICAL] Gremlin Nob skill-punish mechanic missing — 2nd core Nob mechanic
3. [CRITICAL] damage_taken can go negative (Feed card heals more than damage taken)
4. [CRITICAL] player_max_hp never propagated back to RunState after combat (Feed card)
5. [HIGH] Lagavulin strength drain capped at 0 (should push negative)
6. [HIGH] Lagavulin Siphon Soul stats capped at 0
7. [HIGH] Lagavulin loses one attack turn on wake-up
8. [HIGH] Sentry Bolt adds Dazed to discard (should be draw pile)
9. [HIGH] State key missing enemy.misc, pending_split, is_escaping, enemy.max_hp, player_max_hp
10. [MEDIUM] Scenario3 ignores weighted selection for strong encounters
11. [MEDIUM] Duck-type planner/agent detection fragile
12. [MEDIUM] Potion "immediate use" strategy unimplemented (but agents can use potions)
13. [MEDIUM] _observe() doesn't expose asleep or enemy_metallicize powers
14. [LOW] Zero test coverage for run/elite mechanics
15. [LOW] Several card implementations are no-ops (acceptable for v1)

### Gaps Resolved (from iteration 0)
- ✓ No RunState — created run/state.py
- ✓ No Burning Blood relic — created run/relics.py
- ✓ No card reward system — created run/rewards.py
- ✓ No scenario runner — created sts_agent/run.py
- ✓ No elite encounter definitions — added GremlinNob, Lagavulin, Sentry
- ✓ No "hard hallway" encounter definitions — already existed in encounters.py

### Carried-Forward Gaps
(none)

---

## Iteration 2 — Fix Critical/High Bugs
Status: All 9 critical/high bugs fixed. 26 new tests passing.

### Gaps Resolved
- ✓ [CRITICAL] Gremlin Nob Bellow reduces player energy by 2 (Intent.energy_loss + CombatState.energy_loss_next_turn)
- ✓ [CRITICAL] Gremlin Nob skill-punish: playing a Skill → Nob gains 2 Strength (EnemyState.skill_played_str)
- ✓ [CRITICAL] damage_taken clamped to max(0, ...) — Feed no longer causes negative damage
- ✓ [CRITICAL] player_max_hp propagated back to RunState after combat
- ✓ [HIGH] Lagavulin strength drain can push below 0 (removed > 0 guards)
- ✓ [HIGH] Lagavulin Siphon Soul pushes str/dex below 0
- ✓ [HIGH] Lagavulin attacks immediately on wake-up (both timer and attack paths)
- ✓ [HIGH] Sentry Bolt adds Dazed to draw pile (Intent.status_to_draw field)
- ✓ [HIGH] State key includes misc, pending_split, is_escaping, max_hp, player_max_hp, energy_loss_next_turn
- ✓ [MEDIUM] Scenario3 uses weighted selection for strong encounters
- ✓ [MEDIUM] Duck-type planner/agent detection made more robust (try/except)
- ✓ [MEDIUM] _observe() now exposes asleep, enemy_metallicize, spore_cloud, entangled powers
- ✓ [LOW] 26 tests added for elite mechanics, run state, scenarios, builder, rewards, damage clamp

### Remaining Gaps (acceptable for v1)
1. [MEDIUM] Potion "immediate use" strategy unimplemented (agents can still use potions manually)
2. [LOW] Several card implementations are no-ops (DemonForm, Corruption, etc.)
3. [LOW] Builder uses private attribute mutation for potions/max_hp on Combat
4. [LOW] Encounter ID string matching is fragile (labels must match exactly)

### Verification
- MCTSPlanner clears scenario 3 across 5 different seeds (42, 7, 99, 1337, 2026)
- 26 env tests pass, 27 agent tests pass
- HP range across seeds: 42–58/80 after 5 floors

---

## Iteration 3 — Full Act 1 Adventure (Map + Rest Sites + Card Upgrades)
Status: **Complete**
**Expanded Goal:** Replace fixed linear encounter sequence with a real StS-style Act 1:
  - Map generation with branching paths and diverse room types
  - Rest Sites (heal 30% max_hp OR upgrade a card)
  - Card upgrade system wired into the engine (card_id "+" suffix → upgrade deltas → play_card)
  - Boss relic reward (6 relics offered, BurningBlood has mechanical effect)
  - Strategy agent probe-based routing at map forks
  - Shops and Events are out of scope for this iteration (v2)

### Gaps Resolved
- ✓ [CRITICAL] Card upgrade system — upgrade deltas in CardSpec, all handlers accept `upgraded` param, card_id "+" suffix carries upgrade state
- ✓ [CRITICAL] Map generation — MapNode/MapEdge/StSMap data structures, 15-floor branching map, generate_act1_map(), all_paths()
- ✓ [CRITICAL] Room types — RoomType enum (MONSTER/ELITE/REST/BOSS/EVENT/SHOP/TREASURE), room-specific encounter dispatch
- ✓ [CRITICAL] Rest Site logic — rest_heal (30% max_hp), rest_upgrade (card→card+), pick_rest_choice with 3 strategies
- ✓ [HIGH] run_act1 rewired — `use_map=True` default, `_run_act1_map()` + `_run_act1_linear()` (backwards compat)
- ✓ [HIGH] Strategy agent routing — `SimStrategyAgent.pick_path()` with probe-based branch evaluation (survival rate, room priority, low-HP rest preference)
- ✓ [HIGH] Boss relic reward — 6 relics offered (BurningBlood, RingOfSerpents, TinyHouse, BustedCrown, CoffeeDripper, FusionHammer)
- ✓ [MEDIUM] Map visualization — `StSMap.__str__()` renders ASCII map with room symbols
- ✓ [MEDIUM] Elite encounter pool separated from strong hallway pool (Gremlin Nob, Lagavulin, Three Sentries)
- ✓ [MEDIUM] potions.py _SPECS shadowing bug fixed (renamed import to _CARD_SPECS)
- ✓ [LOW] 70 new tests: 25 map, 17 upgrade, 28 rooms, 5 path picking, 9 act1 map integration

### Test Results
- **sts_env**: 141 passed ✅
- **sts_agent**: 67 passed, 9 skipped ✅
- Total: **208 tests passing**

### Remaining Gaps (acceptable for v1 → v2)
1. [MEDIUM] EVENT/SHOP/TREASURE rooms are no-ops (logged and skipped)
2. [MEDIUM] Only BurningBlood has mechanical effect among boss relics
3. [MEDIUM] Potion "immediate use" strategy unimplemented (agents can still use potions manually)
4. [LOW] Several card implementations are no-ops (DemonForm, Corruption, etc.)
5. [LOW] Builder uses private attribute mutation for potions/max_hp on Combat
6. [LOW] Encounter ID string matching is fragile (labels must match exactly)
7. [LOW] _pick_path greedy walk doesn't look ahead past immediate branch

### Verification
- Full 15-floor map generation works with branching paths
- Map-based run_act1 clears all room types (Monster, Elite, Rest, Boss)
- SimStrategyAgent.pick_path prefers REST when HP < 40%, Elite when HP healthy
- Card upgrades work end-to-end: rest_upgrade appends "+" → Card.card_id carries "+" → play_card resolves upgrade deltas

---

## Iteration 4 — Card System Overhaul + Pending Effect Stack
Status: **Complete** (user-driven)

**Changes by Julius:**
- **Declarative card system**: Replaced 61 imperative handlers with `CardSpec` dataclass carrying declarative effect fields (attack, block, vulnerable, weak, etc.) + optional `custom` callable escape hatch. Only ~20 cards need custom handlers now.
- **Pending effect stack**: `pending.py` with `ChoiceFrame` (agent input) and `ThunkFrame` (auto-drain). LIFO resolution lets complex cards like Havoc push thunks before sub-effects.
- **Card upgrade via "+" suffix**: `Card.card_id` carries upgrade state (`"Strike+"`). `CardSpec.upgrade` dict maps field→delta. `get_spec()` strips "+" for lookup.
- **Complex cards implemented**: BurningPact, Headbutt, Armaments (choice-based upgrade), DualWield, Havoc (thunk-based exhaust), SecondWind, Rampage, SearingBlow, LimitBreak.
- **No-ops eliminated**: DemonForm, Corruption, DarkEmbrace, DoubleTap, Juggernaut, Brutality all now have working custom handlers.
- **Massive test suite**: 586 env tests (was 141) — 77 cards, 52 engine, 44 powers, 100 enemies, 75 encounters, 24 potions, 20 split, 12 pending, 7 havoc, etc.

**Agent adapter fix:**
- `tree_search.py` state key updated: `pending_choices` → `pending_stack` compact representation + `rampage_extra`
- 67 agent tests passing

### Test Results
- **sts_env**: 586 passed, 3 skipped ✅
- **sts_agent**: 67 passed, 9 skipped ✅
- Total: **653 tests passing**

### Remaining Gaps
1. [MEDIUM] EVENT/SHOP/TREASURE rooms are no-ops (logged and skipped)
2. [MEDIUM] Only BurningBlood has mechanical effect among boss relics
3. [MEDIUM] Oracle tests need `slaythespire` module (external dependency)
4. [LOW] Builder uses private attribute mutation for potions/max_hp on Combat
5. [LOW] Encounter ID string matching is fragile (labels must match exactly)
6. [LOW] _pick_path greedy walk doesn't look ahead past immediate branch

---

## Iteration 5 — Full Act 1: Events, Shops, Treasures, Boss Relics
Status: **Complete**

**Goal:** Complete all remaining Act 1 room types so the entire adventure system is functional.

### Gaps Resolved
- ✓ [MEDIUM] **Events**: 7 Act 1 events (Big Fish, Golden Idol, The Cleric, Dead Adventurer, Golden Wing, Liars Game, Scrap Ooze) with choice-based outcomes (gold, HP, card upgrade, card removal, relics, max HP)
- ✓ [MEDIUM] **Shops**: Full shop system — 5 cards (3 common + 1 uncommon + 1 rare), 3 potions, 1 relic, card removal service. Gold economy with StS-accurate pricing (50/75/150 for cards, 75 for removal)
- ✓ [MEDIUM] **Treasure rooms**: 20-30 gold + 25% relic drop chance from common relic pool
- ✓ [MEDIUM] **Boss relic registry**: RedSkull, CentennialPuzzle, JuzuBracelet, Orichalcum, CeramicFish registered with specs
- ✓ [MEDIUM] **Orichalcum run-layer effect**: +4 HP heal after combat (simplified from combat-internal block gain)
- ✓ [HIGH] **Dispatch wiring**: `_run_act1_map` now handles all 6 room types (Monster, Elite, Rest, Event, Shop, Treasure, Boss). No more no-ops.
- ✓ [HIGH] **Auto-shop AI**: heuristic shopping (remove worst card → buy best affordable card → buy potion if slot free)
- ✓ [HIGH] **Event choice hook**: strategy agents can implement `pick_event_choice(event, character)` for smarter event decisions

### New Files
- `src/sts_env/run/events.py` — Event registry, 7 events with `EventSpec`/`EventChoice` dataclasses, `random_act1_event()`, `resolve_event()`
- `src/sts_env/run/shop.py` — Shop system with `ShopInventory`/`ShopResult`, `generate_shop()`, `buy_card()`, `buy_potion()`, `buy_relic()`, `remove_worst_card()`
- `src/sts_env/run/treasure.py` — Treasure room with `open_treasure()`, `TreasureResult`
- `tests/test_events.py` — 28 tests
- `tests/test_shop.py` — 31 tests
- `tests/test_treasure.py` — 13 tests

### Test Results
- **sts_env**: 658 passed, 3 skipped ✅
- **sts_agent**: 67 passed, 9 skipped ✅
- Total: **725 tests passing**

### Remaining Gaps (post-Act 1)
1. [MEDIUM] Oracle tests need `slaythespire` module (external dependency)
2. [LOW] RedSkull/CentennialPuzzle/JuzuBracelet/CeramicFish need combat-engine hooks (currently specs only)
3. [LOW] Encounter ID string matching is fragile (labels must match exactly)
4. [LOW] _pick_path greedy walk doesn't look ahead past immediate branch
5. [LOW] Shop relic and treasure relic pools may overlap with boss rewards

---

## Iteration 6 — Complete Act 1 Environment
Status: **In Progress**
**Goal:** Fill all remaining gaps for a complete, faithful Act 1 experience (environment only — agent improvements deferred).

### Gaps Identified
1. [CRITICAL] Only 1 of 3 Act 1 bosses — missing Guardian and Hexaghost. Map always picks Slime Boss. **→ DONE ✅**
2. [CRITICAL] No Neow blessing — the starting choice (max HP, random relic, remove a card, etc.) is entirely absent. **→ DONE ✅**
3. [HIGH] No elite relic reward — elites should drop a random common/uncommon relic. Currently only card + gold + potion. **→ DONE ✅**
4. [HIGH] Potion sync bug — consumed potions not synced from combat back to run state (FIXED: committed to both repos). **→ DONE ✅**
5. [HIGH] Card.to_key() TypeError — None cost_override not sortable with int (FIXED: committed to sts_env). **→ DONE ✅**
6. [MEDIUM] Boss relic effects are mostly stubs — only BurningBlood and Orichalcum have mechanical effects. **→ DONE ✅** (CoffeeDripper, FusionHammer wired; combat-internal ones RedSkull/CentennialPuzzle/JuzuBracelet remain combat-engine hooks)
7. [MEDIUM] No relic pool tracking — shop/treasure/elite/boss relic rewards can overlap (no "already owned" check). **→ DONE ✅** (Unified pool in rewards.py, neow.py imports from it)
8. [MEDIUM] Map room distribution should follow StS weighted probabilities. **→ DONE ✅** (MONSTER 35%, ELITE 15%, REST 12%, EVENT 15%, SHOP 8%, TREASURE 15%)
9. [LOW] Oracle tests need `slaythespire` module (external dependency).
10. [LOW] Encounter ID string matching is fragile (labels must match exactly).
11. [LOW] Shop relic and treasure relic pools may overlap with boss rewards.

### Changes Made
- `src/sts_env/combat/enemies.py`: Added Guardian (240 HP, charging/defensive stance cycle) and Hexaghost (250 HP, divider+activation loop) enemy specs
- `src/sts_env/combat/encounters.py`: Added `guardian()` and `hexaghost()` combat builder functions, updated boss encounter list
- `src/sts_env/run/neow.py`: New file — Neow blessing system with 4 choices (MAX_HP, RANDOM_RELIC, REMOVE_CARD, RANDOM_CARD)
- `src/sts_env/run/rewards.py`: Added `roll_elite_relic()` with duplicate avoidance via owned relics
- `src/sts_env/run/relics.py`: Added CoffeeDripper (blocks rest), FusionHammer (blocks upgrade), BustedCrown, TinyHouse, RingOfSerpents specs; added `can_rest()` and `can_upgrade()` helpers
- `src/sts_env/run/rooms.py`: `pick_rest_choice()` now respects CoffeeDripper/FusionHammer restrictions
- `src/sts_env/run/map.py`: Updated room type distribution to StS-weighted probabilities with EVENT/SHOP/TREASURE rooms
- `src/sts_env/run/neow.py`: Imports `COMMON_RELICS` from rewards.py (single source of truth for relic pool)
- `tests/test_neow.py`: 15 new Neow tests
- `tests/test_rewards.py`: New test file for elite relic rewards
- `tests/test_map.py`, `tests/test_rooms.py`: Updated for 3-boss pool and all room types

### Test Results
- **sts_env**: 691 passed, 3 skipped ✅
