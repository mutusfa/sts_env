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
