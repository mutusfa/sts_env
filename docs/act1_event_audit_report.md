# Act 1 Event Audit Report: Python vs C++ Reference

Generated: 2026-05-03  
Python source: `src/sts_env/run/events.py`  
C++ reference: `third_party/sts_lightspeed/src/game/GameContext.cpp`  
C++ event list: `third_party/sts_lightspeed/include/constants/Events.h`

---

## Summary

| Category | Count |
|----------|-------|
| CORRECT  | 0     |
| WRONG    | 10    |
| MISSING  | 7     |
| FABRICATED (not in C++) | 2 |

---

## Act 1 Events (11 required per C++)

### 1. BIG_FISH — **WRONG**

**C++ implementation:**
- setupEvent: `info.hpAmount0 = fractionMaxHp(1/3.0f, FLOOR)` — calculates 1/3 max HP for healing amount, pre-stored at setup
- Choice 0: `playerHeal(fractionMaxHp(1/3.0f))` — heal 33% of max HP
- Choice 1: `playerIncreaseMaxHp(5)` — gain 5 max HP (and current HP increases too)
- Choice 2: obtain a random relic (tier-based) + add Regret curse card

**Python implementation:**
- Choice 0: Lose 5% max HP, gain 50 gold
- Choice 1: Upgrade a random card
- Choice 2: Pay 7 gold to pass

**Issues:**
- ALL THREE choices are completely wrong. The C++ event has nothing to do with gold payment or card upgrading or max HP loss for gold.
- C++ choice 0 is a heal (33% max HP), not gold/HP trade
- C++ choice 1 is +5 max HP, not card upgrade
- C++ choice 2 is relic + Regret card, not gold payment
- The entire event is essentially a different event. This is likely confused with another event entirely.

---

### 2. THE_CLERIC — **WRONG**

**C++ implementation:**
- setupEvent: `info.hpAmount0 = fractionMaxHp(0.25f)` — 25% max HP
- Choice 0: pay 35 gold, heal 25% max HP
- Choice 1: pay **75 gold (Asc15)** or 50 gold (non-A15), remove a card
- Choice 2: leave

**Python implementation:**
- Choice 0: pay 35 gold, heal 25% max HP — **CORRECT**
- Choice 1: pay 50 gold, remove a card — **WRONG** (missing Asc15 price increase to 75)
- Choice 2: leave — **CORRECT**

**Issues:**
- Choice 1 gold cost is wrong for Asc15: should be 75, not 50. The C++ uses `loseGold(unfavorable ? 75 : 50)`.

---

### 3. DEAD_ADVENTURER — **WRONG** (partially correct)

**C++ implementation:**
- setupEvent: shuffle rewards [0,1,2], pick encounter from [THREE_SENTRIES, GREMLIN_NOB, LAGAVULIN_EVENT] via `miscRng.random(2)`
- Choice 0 (Loot): encounter chance = `phase * 25 + (unfavorable ? 35 : 25)`
  - If encounter: fight elite, after combat get gold (25-35 base + 30 per gold slot) + relic (random tier for act 1) + card reward + potion rewards
  - If no encounter: reward==0 → 30 gold; reward==2 → random relic from tier pool; reward==1 → **NOTHING** (no card is given in C++ for the safe-loot path)
- Choice 1: leave

**Python implementation:**
- setupEvent: similar shuffle and encounter selection — **CORRECT** structure
- Encounter chance: `phase * 25 + 25` — **WRONG** (missing Asc15 increase to +35)
- Safe-loot reward==1: adds a random common/uncommon card to deck — **WRONG** (C++ gives NOTHING for reward slot 1 in the safe path; cards only appear as combat rewards)
- Relic from combat: uses `_COMMON_RELICS` list — **WRONG** (C++ uses `returnRandomRelic(returnRandomRelicTier(relicRng, 1))` which is a proper tier-based relic roll)
- Relic from safe loot: uses `_COMMON_RELICS` list — **WRONG** (C++ uses `returnRandomScreenlessRelic(returnRandomRelicTier(relicRng, 1))`)
- Card reward for combat path: not modeled (C++ gives `createCardReward(Room::EVENT)` + `addPotionRewards`)

---

### 4. GOLDEN_IDOL — **WRONG**

**C++ implementation:**
- setupEvent: `hpAmount0 = fractionMaxHp(unfavorable ? 0.35f : 0.25f)`, `hpAmount1 = fractionMaxHp(unfavorable ? 0.10f : 0.08f)`
- **5 choices:**
  - Choice 0: obtain Golden Idol relic
  - Choice 1: leave
  - Choice 2: obtain Injury card
  - Choice 3: `damagePlayer(hpAmount0)` — 25%/35% max HP damage
  - Choice 4: `loseMaxHp(hpAmount1)` — 8%/10% max HP loss

**Python implementation:**
- **2 choices:**
  - Choice 0: lose 5% max HP, gain 50 gold
  - Choice 1: heal 25% missing HP, gain random common relic

**Issues:**
- The Python event has ONLY 2 choices; C++ has 5.
- Neither Python choice corresponds to ANY C++ choice.
- Python has max-HP-for-gold and heal-for-relic mechanics that don't exist in the C++ Golden Idol.
- The C++ Golden Idol event is about a relic (Golden Idol relic, Injury card, HP damage, max HP loss) — none of these are present in Python.
- Missing: Ascension-dependent values, damagePlayer vs loseMaxHp distinction.

---

### 5. WING_STATUE — **WRONG** (Python has "Golden Wing" + "Wing Statue" = 2 events for 1 C++ event)

**C++ implementation:**
- **3 choices:**
  - Choice 0: `damagePlayer(7)` — take 7 damage (NOT lose max HP), then open card remove screen
  - Choice 1: obtain random gold 50-80
  - Choice 2: leave

**Python "Golden Wing" event (lines 445-480):**
- Choice 0: lose 5% max HP, gain 100 gold
- Choice 1: lose all gold, heal 25% max HP
- **This entire event is fabricated** — it doesn't match any C++ event

**Python "Wing Statue" event (lines 639-673):**
- Choice 0: remove a Strike or Defend from deck
- Choice 1: leave
- **Completely wrong mechanics.** C++ does `damagePlayer(7)` then opens a card removal screen (remove ANY card). Python just removes a random Strike/Defend for free with no damage cost.

**Issues:**
- Python splits this into TWO events ("Golden Wing" and "Wing Statue") but C++ has ONE event (WING_STATUE).
- Neither Python event correctly implements the C++ event.
- Missing: damagePlayer(7) before card removal, gold reward choice.

---

### 6. WORLD_OF_GOOP — **MISSING**

**C++ implementation:**
- setupEvent: `info.goldLoss = min(gold, miscRng.random(35,75))` for Asc15, or `min(gold, miscRng.random(20,50))` for non-A15
- Choice 0: `damagePlayer(11)`, obtain 75 gold
- Choice 1: `loseGold(info.goldLoss)` — lose random amount of gold (20-50 non-A15, 35-75 A15)

**Python:** Not implemented.

---

### 7. THE_SSSSSERPENT — **WRONG** (Python has "Liars Game" instead)

**C++ implementation:**
- **2 choices:**
  - Choice 0: obtain 175 gold (150 Asc15) + obtain Doubt curse card
  - Choice 1: leave

**Python "Liars Game" event (lines 483-518):**
- Choice 0: pay 5 gold, 50% chance gain 50, 50% lose 5 more
- Choice 1: leave
- **Completely wrong.** The C++ Ssssserpent is a simple gold+curse trade, not a gambling game.

**Issues:**
- The Python event is named "Liars Game" (which IS the C++ string name for this event enum) but the mechanics are completely different.
- Missing: Doubt card addition, Asc15 gold reduction, no gambling mechanic in C++.

---

### 8. LIVING_WALL — **MISSING**

**C++ implementation:**
- **3 choices:**
  - Choice 0: open card remove screen (remove any card)
  - Choice 1: open card transform screen (transform 1 card)
  - Choice 2: open card upgrade screen (upgrade 1 card)

**Python:** Not implemented.

---

### 9. HYPNOTIZING_COLORED_MUSHROOMS — **WRONG**

**C++ implementation:**
- Choice 0: enter combat with MUSHROOMS_EVENT. After combat: gold (20-30) + Odd Mushroom relic + potion rewards + card reward
- Choice 1: obtain 99 gold (50 Asc15)

**Python implementation:**
- Choice 0: fight mushrooms — gold + Odd Mushroom relic. **Missing: potion rewards, card reward.** Also gold/relic applied immediately instead of as post-combat reward.
- Choice 1: gain 99 gold — **WRONG** (no Asc15 handling, should be 50 gold at Asc15)

**Issues:**
- Choice 0 doesn't properly model post-combat rewards (card reward, potions).
- Choice 1 missing Asc15 gold reduction (99 → 50).
- Gold and relic should be delivered as combat rewards, not immediately.

---

### 10. SCRAP_OOZE — **WRONG**

**C++ implementation:**
- **2 choices:**
  - Choice 0: `damagePlayer(unfavorable ? 5 : 3)`. Roll `miscRng.random(99)`. If `roll >= 99 - relicChance` where `relicChance = info.eventData*10 + 25`: obtain a random relic (tier-based for act 1), event ends. Otherwise `++info.eventData` (relic chance increases by 10% each attempt, repeats).
  - Choice 1: leave

**Python implementation:**
- Choice 0: obtain a random colorless card — **COMPLETELY WRONG**
- Choice 1: pay 3 gold to pass — **COMPLETELY WRONG**

**Issues:**
- The Python implementation has no damage, no relic, no scaling chance mechanic.
- C++ is about taking damage to dig for a relic with increasing odds. Python gives a free colorless card or charges 3 gold.
- Missing: damagePlayer, relic scaling, multi-attempt mechanic.

---

### 11. SHINING_LIGHT — **WRONG**

**C++ implementation:**
- setupEvent: `info.hpAmount0 = fractionMaxHp(unfavorable ? 0.30f : 0.20f, ROUND)` — 20%/30% max HP
- **2 choices:**
  - Choice 0: `damagePlayer(info.hpAmount0)` (take damage FIRST), then upgrade up to 2 random upgradeable cards
  - Choice 1: leave (nothing happens)

**Python implementation:**
- Choice 0: upgrade 2 random cards (NO damage!) — **WRONG** (missing damage entirely)
- Choice 1: take 7 damage — **WRONG** (C++ choice 1 is "leave", not "take damage")

**Issues:**
- The damage + upgrade is a SINGLE choice in C++ (choice 0), not two separate choices.
- Python choice 1 (take 7 damage) doesn't exist in C++ — choice 1 is just "leave".
- Python choice 0 is missing the damagePlayer component entirely.
- The damage amount should be 20%/30% of max HP (ascension-dependent), not a flat 7.

---

## Act 1 Shrines (6 required per C++)

### 12. MATCH_AND_KEEP — **MISSING**

**C++ implementation:** Complex memory card game. Generates 6 cards (rare, uncommon, common, colorless uncommon or curse, curse, starter card), duplicates them into 12, shuffles into 4x3 grid. Player has 5 attempts to find matching pairs.

**Python:** Not implemented.

---

### 13. GOLDEN_SHRINE — **MISSING**

**C++ implementation:**
- Choice 0: obtain 100 gold (50 Asc15)
- Choice 1: obtain 275 gold + Regret card
- Choice 2: leave

**Python:** Not implemented.

---

### 14. TRANSMORGRIFIER — **MISSING**

**C++ implementation:**
- Choice 0: open card transform screen (transform 1 card using miscRng)
- Choice 1: leave

**Python:** Not implemented.

---

### 15. PURIFIER — **MISSING**

**C++ implementation:**
- Choice 0: open card remove screen (remove 1 card)
- Choice 1: leave

**Python:** Not implemented.

---

### 16. UPGRADE_SHRINE — **MISSING**

**C++ implementation:**
- Choice 0: open card upgrade screen (upgrade 1 card)
- Choice 1: leave

**Python:** Not implemented.

---

### 17. WHEEL_OF_CHANGE — **WRONG**

**C++ implementation:**
- 1 choice (spin the wheel), rolls `miscRng.random(5)` for 6 outcomes:
  - 0: obtain `act * 100` gold (100 for act 1)
  - 1: obtain a random relic (tier-based for current act)
  - 2: heal to full HP (`playerHeal(maxHp)`)
  - 3: obtain Decay curse card
  - 4: open card remove screen
  - 5: `playerLoseHp(fractionMaxHp(unfavorable ? 0.15f : 0.10f))` — lose 10%/15% current HP

**Python implementation:**
- 1 choice, rolls `rng.randint(1, 5)` for only 5 outcomes:
  - 1: gain 50 gold — **WRONG** (should be act*100=100, not 50)
  - 2: obtain a random curse — **WRONG** (C++ outcome 1 is relic, not curse)
  - 3: obtain a random common/uncommon card — **WRONG** (C++ outcome 2 is full heal, not card)
  - 4-5: "nothing happens" — **WRONG** (should be Decay curse, card remove, or HP loss)
  - Missing outcomes: full heal, card removal, HP loss

**Issues:**
- Uses `randint(1, 5)` (5 outcomes) instead of `random(5)` (6 outcomes, 0-5).
- Only 1 of 6 C++ outcomes is even approximately right (gold), and its amount is wrong.
- The Python maps outcomes incorrectly: curse where relic should be, card where heal should be, etc.

---

## Fabricated Events (exist in Python but NOT in C++ Act 1)

### "Golden Wing" — **FABRICATED**
- Python lines 445-480. Not a valid C++ event. The C++ WING_STATUE event is a completely different event (see item 5 above).

### "Bonfire" — **FABRICATED**
- Python lines 599-636. Not a valid C++ event. There is a "Bonfire Spirits" event in C++ (BONFIRE_SPIRITS) but it's a one-time event (not Act 1), and its mechanics are completely different (sacrifice a card to fight Bonfire Elementals for relic reward). The Python "Bonfire" event (upgrade card + lose 5 max HP) doesn't match anything.

---

## Cross-Cutting Issues

### damagePlayer vs playerLoseHp vs loseMaxHp
The Python code conflates these three distinct mechanics:
- **damagePlayer**: reduces curHp by amount (can trigger relics like Torii, etc.). Used by Golden Idol choice 3, Wing Statue choice 0, Scrap Ooze, Shining Light, World of Goop.
- **playerLoseHp**: reduces curHp by amount (different relic interactions, blocks on Tick Mark/LoseHp actions). Used by Dead Adventurer combat rewards context, Wheel of Change outcome 5.
- **loseMaxHp**: reduces BOTH maxHp AND curHp by amount. Used by Golden Idol choice 4, Wing Statue is NOT this.

Python's `_lose_max_hp` helper is used where `damagePlayer` should be used (e.g., Big Fish choice 0 uses loseMaxHp but the C++ doesn't use loseMaxHp for Big Fish at all).

### Ascension 15 Handling
Almost completely absent from Python. C++ uses `const bool unfavorable = ascension >= 15` extensively:
- Dead Adventurer: encounter chance +35 instead of +25
- Golden Idol: 35%/10% instead of 25%/8%
- World of Goop: gold loss range 35-75 instead of 20-50
- Shining Light: 30% instead of 20%
- The Ssssserpent: 150 gold instead of 175
- Mushrooms: 50 gold instead of 99
- Scrap Ooze: 5 damage instead of 3
- Wheel of Change: 15% HP loss instead of 10%
- Golden Shrine: 50 gold instead of 100
- The Cleric: 75 gold instead of 50 for removal

None of these ascension adjustments are implemented in Python.

### Relic Pools
Python uses a hardcoded `_COMMON_RELICS` list. C++ uses `returnRandomRelic(returnRandomRelicTier(relicRng, act))` which rolls for rarity tier (common/uncommon/rare based on act-specific chances) then picks from the appropriate pool. This is a significant difference — Python events only ever give common relics, while C++ can give any tier.

### Card Rewards from Combat
Python doesn't model the card reward system from combat events (Dead Adventurer, Mushrooms). In C++, these events give `createCardReward(Room::EVENT)` which generates a 3-card reward screen with rarity distribution. Python either skips this or adds a single random card.

---

## Detailed Event-by-Event Verdict

| # | Event | Status | Severity |
|---|-------|--------|----------|
| 1 | BIG_FISH | WRONG | CRITICAL — all 3 choices are wrong, completely different event |
| 2 | THE_CLERIC | WRONG | MINOR — choice 1 gold cost missing Asc15 increase |
| 3 | DEAD_ADVENTURER | WRONG | MODERATE — missing Asc15, wrong reward for card slot, wrong relic pools |
| 4 | GOLDEN_IDOL | WRONG | CRITICAL — only 2 of 5 choices, neither matches C++ |
| 5 | WING_STATUE | WRONG | CRITICAL — split into 2 fabricated events, neither correct |
| 6 | WORLD_OF_GOOP | MISSING | — |
| 7 | THE_SSSSSERPENT | WRONG | CRITICAL — "Liars Game" is a gambling game, not gold+curse |
| 8 | LIVING_WALL | MISSING | — |
| 9 | HYPNOTIZING_COLORED_MUSHROOMS | WRONG | MODERATE — missing Asc15, wrong reward delivery |
| 10 | SCRAP_OOZE | WRONG | CRITICAL — completely wrong mechanics |
| 11 | SHINING_LIGHT | WRONG | CRITICAL — damage+upgrade split into separate choices |
| 12 | MATCH_AND_KEEP | MISSING | — |
| 13 | GOLDEN_SHRINE | MISSING | — |
| 14 | TRANSMORGRIFIER | MISSING | — |
| 15 | PURIFIER | MISSING | — |
| 16 | UPGRADE_SHRINE | MISSING | — |
| 17 | WHEEL_OF_CHANGE | WRONG | CRITICAL — wrong number of outcomes, wrong mechanics |
| — | Golden Wing (Python-only) | FABRICATED | Remove or merge into correct Wing Statue |
| — | Bonfire (Python-only) | FABRICATED | Remove entirely |

---

## Recommendations

1. **Remove fabricated events** "Golden Wing" and "Bonfire" — they don't exist in the C++ reference.
2. **Rewrite BIG_FISH** — the current implementation appears to be from a completely different game or a misunderstanding. C++ choices: heal 33% max HP / +5 max HP / relic + Regret card.
3. **Rewrite GOLDEN_IDOL** — needs 5 choices: relic / leave / Injury card / damage / max HP loss.
4. **Rewrite WING_STATUE** — consolidate into one event: take 7 damage + card removal / gold (50-80) / leave.
5. **Rewrite THE_SSSSSERPENT** (rename from "Liars Game") — gold + Doubt card / leave.
6. **Rewrite SCRAP_OOZE** — damage + escalating relic chance / leave.
7. **Rewrite SHINING_LIGHT** — single choice: take damage THEN upgrade 2 cards / leave.
8. **Rewrite WHEEL_OF_CHANGE** — 6 outcomes: gold/relic/full heal/Decay/remove card/HP loss.
9. **Implement all MISSING events**: World of Goop, Living Wall, Match and Keep, Golden Shrine, Transmorgrifier, Purifier, Upgrade Shrine.
10. **Add Ascension 15 support** across all events.
11. **Fix relic pool system** — replace hardcoded common relic list with proper tier-based rolling.
12. **Add card reward screens** for combat events instead of immediately granting cards/relics.
