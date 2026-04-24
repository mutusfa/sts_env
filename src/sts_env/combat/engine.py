"""Turn loop, action dispatch, and termination logic.

Turn structure (player turn):
  1. Start of turn: wipe player block, tick player power durations,
     give energy (3), draw 5 cards.
  2. Player acts: play cards or end turn.
  3. End of player turn: discard hand.
  4. Enemy turns: each living enemy resolves its intent then picks next intent.

Enemy turn structure:
  1. Wipe enemy block (from previous round).
  2. Tick enemy power durations.
  3. Resolve current intent (apply damage/block/buffs to player and enemy).
  4. Pick next intent for the upcoming player turn display.
"""

from __future__ import annotations

import copy
from collections import Counter

from .cards import get_spec as _get_card_spec, play_card as _play_card, CardType, TargetType
from .enemies import (
    Intent,
    IntentType,
    pick_intent_with_state,
    roll_hp,
    run_pre_battle,
)
from .powers import Powers, apply_damage, calc_damage
from .rng import RNG
from .state import (
    Action,
    ActionType,
    CombatState,
    EnemyObs,
    EnemyState,
    Observation,
)
from .deck import Piles

_PLAYER_START_HP = 80
_ENERGY_PER_TURN = 3
_CARDS_PER_DRAW = 5

# Large slime → medium slime spawned on split
_SPLIT_INTO: dict[str, str] = {
    "AcidSlimeL":  "AcidSlimeM",
    "SpikeSlimeL": "SpikeSlimeM",
}

# Ironclad starter deck: 5×Strike, 4×Defend, 1×Bash
IRONCLAD_STARTER = (
    ["Strike"] * 5
    + ["Defend"] * 4
    + ["Bash"] * 1
)


class Combat:
    """One combat encounter.

    Usage::

        combat = Combat.ironclad_starter(enemy="JawWorm", seed=42)
        obs = combat.reset()
        while not obs.done:
            action = my_policy(obs)
            obs, info = combat.step(action)
        print(combat.damage_taken)
    """

    def __init__(
        self,
        deck: list[str],
        enemies: list[str],
        seed: int,
        player_hp: int = _PLAYER_START_HP,
    ) -> None:
        self._deck = list(deck)
        self._enemy_names = list(enemies)
        self._seed = seed
        self._player_start_hp = player_hp
        self._state: CombatState | None = None
        self._damage_taken: int = 0
        self._intents: list[Intent] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reset(self) -> Observation:
        """(Re)initialise the combat and return the first observation."""
        rng = RNG(self._seed)

        # Build piles: shuffle deck into draw pile
        piles = Piles(draw=list(self._deck))
        rng.shuffle(piles.draw)

        # Roll enemy HP; "Empty" slots are inert pre-allocated slots for splits
        enemies = []
        for name in self._enemy_names:
            if name == "Empty":
                enemies.append(EnemyState(name="Empty", hp=0, max_hp=0))
            else:
                hp = roll_hp(name, rng)
                enemies.append(EnemyState(name=name, hp=hp, max_hp=hp))

        self._state = CombatState(
            player_hp=self._player_start_hp,
            player_max_hp=self._player_start_hp,
            player_block=0,
            player_powers=Powers(),
            energy=_ENERGY_PER_TURN,
            piles=piles,
            enemies=enemies,
            rng=rng,
            turn=0,
        )
        self._damage_taken = 0

        # Run pre-battle hooks (skip Empty slots)
        for enemy in self._state.enemies:
            if enemy.name != "Empty":
                run_pre_battle(enemy, self._state)

        # Pick initial intents for all enemies (None sentinel for Empty slots)
        self._intents = []
        for i, enemy in enumerate(self._state.enemies):
            if enemy.name == "Empty":
                self._intents.append(Intent(IntentType.BUFF))  # inert placeholder
            else:
                intent = pick_intent_with_state(enemy, rng, turn=0, state=self._state, enemy_index=i)
                self._intents.append(intent)

        # Draw opening hand
        self._state.piles.draw_cards(_CARDS_PER_DRAW, rng)

        return self._observe()

    def step(self, action: Action) -> tuple[Observation, float, dict]:
        """Apply one player action. Returns (observation, reward, info).

        reward = hp_after - hp_before (negative when damage is taken, 0 otherwise).
        """
        if self._state is None:
            raise RuntimeError("Call reset() before step().")

        state = self._state
        hp_before = state.player_hp

        if self._is_done():
            raise RuntimeError("Combat is already done.")

        if action.action_type == ActionType.PLAY_CARD:
            _play_card(state, action.hand_index, action.target_index)

        elif action.action_type == ActionType.END_TURN:
            self._resolve_end_of_player_turn()

        self._damage_taken = self._player_start_hp - state.player_hp
        reward = float(state.player_hp - hp_before)

        info: dict = {}
        return self._observe(), reward, info

    @property
    def damage_taken(self) -> int:
        return self._damage_taken

    def valid_actions(self) -> list[Action]:
        """Return all legal actions for the current state.

        Returns an empty list when combat is done.  Card actions are returned
        for every (hand_index, target_index) combination — caller is responsible
        for deduplication if needed.  END_TURN is always included when not done.
        """
        if self._state is None or self._is_done():
            return []

        state = self._state
        live_enemy_indices = [
            i for i, e in enumerate(state.enemies)
            if e.alive and not e.is_escaping
        ]
        entangled = state.player_powers.entangled
        actions: list[Action] = []

        for hi, card_id in enumerate(state.piles.hand):
            spec = _get_card_spec(card_id)
            if spec.cost < 0 or spec.cost > state.energy:
                continue
            if entangled and spec.card_type in (CardType.SKILL, CardType.POWER):
                continue
            if spec.target == TargetType.SINGLE_ENEMY:
                for ti in live_enemy_indices:
                    actions.append(Action.play_card(hi, ti))
            else:
                actions.append(Action.play_card(hi, 0))

        actions.append(Action.end_turn())
        return actions

    def clone(self) -> "Combat":
        """Return a deep copy of this combat, including RNG state.

        The clone is fully independent: stepping one does not affect the other.
        """
        return copy.deepcopy(self)

    def observe(self) -> Observation:
        """Return current observation without advancing state."""
        if self._state is None:
            raise RuntimeError("Call reset() before observe().")
        return self._observe()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_done(self) -> bool:
        state = self._state
        assert state is not None
        all_enemies_done = all(
            not e.alive or e.is_escaping
            for e in state.enemies if e.name != "Empty"
        )
        return state.player_hp <= 0 or all_enemies_done

    def _observe(self) -> Observation:
        state = self._state
        assert state is not None

        enemy_obs = []
        for i, enemy in enumerate(state.enemies):
            intent = self._intents[i] if i < len(self._intents) else None
            enemy_obs.append(
                EnemyObs(
                    name=enemy.name,
                    hp=enemy.hp,
                    max_hp=enemy.max_hp,
                    block=enemy.block,
                    powers={
                        "strength": enemy.powers.strength,
                        "vulnerable": enemy.powers.vulnerable,
                        "weak": enemy.powers.weak,
                        "curl_up": enemy.powers.curl_up,
                        "angry": enemy.powers.angry,
                    },
                    intent_type=intent.intent_type.name if intent else "NONE",
                    intent_damage=intent.damage if intent else 0,
                    intent_damage_effective=(
                        calc_damage(intent.damage, enemy.powers, state.player_powers)
                        if intent and intent.intent_type in (IntentType.ATTACK, IntentType.ATTACK_DEFEND, IntentType.ATTACK_DEBUFF)
                        else 0
                    ),
                    intent_hits=intent.hits if intent else 0,
                    intent_block_gain=intent.block_gain if intent else 0,
                )
            )

        return Observation(
            player_hp=state.player_hp,
            player_max_hp=state.player_max_hp,
            player_block=state.player_block,
            player_powers={
                "strength": state.player_powers.strength,
                "vulnerable": state.player_powers.vulnerable,
                "weak": state.player_powers.weak,
                "frail": state.player_powers.frail,
            },
            energy=state.energy,
            hand=list(state.piles.hand),
            draw_pile=dict(Counter(state.piles.draw)),
            discard_pile=dict(Counter(state.piles.discard)),
            exhaust_pile=dict(Counter(state.piles.exhaust)),
            enemies=enemy_obs,
            done=self._is_done(),
            player_dead=state.player_hp <= 0,
            turn=state.turn,
        )

    def _resolve_end_of_player_turn(self) -> None:
        state = self._state
        assert state is not None

        # Discard hand
        state.piles.discard_hand(state.rng)

        # Tick player power durations *before* enemies act so that statuses
        # applied by enemies this turn survive until the next player turn
        # (mirrors sts_lightspeed's decrementIfNotJustApplied logic).
        state.player_powers.tick_start_of_turn()

        # Each living enemy resolves its stored intent, then picks next intent
        new_intents: list[Intent] = []
        for i, enemy in enumerate(state.enemies):
            if enemy.name == "Empty" or not enemy.alive or enemy.is_escaping:
                new_intents.append(self._intents[i])
                continue

            # Override stored intent with SPLIT if pending
            if enemy.pending_split:
                enemy.pending_split = False
                self._intents[i] = Intent(IntentType.SPLIT)

            # Wipe enemy block at start of enemy turn
            enemy.block = 0
            # Tick enemy power durations (Vulnerable/Weak)
            enemy.powers.tick_start_of_turn()

            # Resolve the intent chosen at start of last player turn
            intent = self._intents[i]
            self._resolve_enemy_intent(enemy, intent, i)

            # Apply ritual stacks *after* the attack (end-of-round effect).
            # ritual_just_applied ensures no strength gain on the turn ritual
            # is first acquired, matching sts_lightspeed's justApplied flag.
            enemy.powers.apply_ritual()

            if not enemy.alive or enemy.is_escaping:
                new_intents.append(intent)
                continue

            # Newly spawned mediums (from split) need their initial intent picked
            # The _resolve_split call already set their name; they are alive.
            # Check if this slot was replaced (name changed to a medium).
            if intent.intent_type == IntentType.SPLIT:
                # Slot i was replaced with a medium; also handle slot i+1 if it was too
                # Both slots now hold fresh mediums — pick turn=0 intents for them.
                for split_idx in (i, i + 1):
                    if split_idx < len(state.enemies) and state.enemies[split_idx].name != "Empty":
                        medium = state.enemies[split_idx]
                        if medium.alive:
                            ni = pick_intent_with_state(
                                medium, state.rng, turn=0, state=state, enemy_index=split_idx
                            )
                            # Ensure new_intents is long enough
                            while len(new_intents) <= split_idx:
                                new_intents.append(Intent(IntentType.BUFF))
                            new_intents[split_idx] = ni
                continue

            # Pick next intent for next turn display
            next_intent = pick_intent_with_state(
                enemy, state.rng, state.turn + 1, state=state, enemy_index=i
            )
            new_intents.append(next_intent)

        # Advance the round counter once, after all enemies have acted.
        state.turn += 1
        self._intents = new_intents

        # Start next player turn
        state.player_block = 0
        state.energy = _ENERGY_PER_TURN
        state.piles.draw_cards(_CARDS_PER_DRAW, state.rng)

    def _resolve_split(self, enemy: EnemyState, idx: int) -> None:
        """Replace enemy at idx and idx+1 with two fresh medium slimes."""
        state = self._state
        assert state is not None

        medium_name = _SPLIT_INTO[enemy.name]
        split_hp = enemy.hp

        # Replace both slots with fresh medium EnemyStates at split_hp
        for slot in (idx, idx + 1):
            state.enemies[slot] = EnemyState(
                name=medium_name,
                hp=split_hp,
                max_hp=split_hp,
            )

    def _resolve_enemy_intent(
        self, enemy: EnemyState, intent: Intent, enemy_index: int
    ) -> None:
        state = self._state
        assert state is not None

        if intent.intent_type == IntentType.SPLIT:
            self._resolve_split(enemy, enemy_index)
            return

        if intent.intent_type == IntentType.ESCAPE:
            enemy.is_escaping = True
            return

        if intent.intent_type in (IntentType.ATTACK, IntentType.ATTACK_DEFEND, IntentType.ATTACK_DEBUFF):
            for _ in range(intent.hits):
                raw = calc_damage(intent.damage, enemy.powers, state.player_powers)
                nb, nhp = apply_damage(raw, state.player_block, state.player_hp)
                state.player_block = nb
                state.player_hp = nhp
                if state.player_hp <= 0:
                    return

        if intent.intent_type in (IntentType.DEFEND, IntentType.ATTACK_DEFEND):
            enemy.block += intent.block_gain

        if intent.strength_gain:
            enemy.powers.strength += intent.strength_gain

        # Post-resolution debuffs applied to the player
        if intent.applies_weak:
            state.player_powers.weak += intent.applies_weak
        if intent.applies_frail:
            state.player_powers.frail += intent.applies_frail
        if intent.applies_vulnerable:
            state.player_powers.vulnerable += intent.applies_vulnerable
        if intent.applies_entangle:
            state.player_powers.entangled = True

        # Ally-targeting block (Shield Gremlin pattern)
        if intent.ally_block_gain:
            live_allies = [e for i, e in enumerate(state.enemies)
                           if e.alive and i != enemy_index]
            if live_allies:
                target = live_allies[state.rng.randint(0, len(live_allies) - 1)]
                target.block += intent.ally_block_gain

        # Status cards added to the player's discard pile
        if intent.status_card_count:
            for _ in range(intent.status_card_count):
                state.piles.add_to_discard(intent.status_card_id)


