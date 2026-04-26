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
    _LAG_SLEEP,
)
from .events import Event, subscribe, emit
from .listeners_enemies import ENEMY_SUBSCRIPTIONS, ENEMY_CONDITION_SUBSCRIPTIONS
from .listeners_powers import POWER_SUBSCRIPTIONS
from .listeners_relics import RELIC_SUBSCRIPTIONS
from .listeners_potions import POTION_SUBSCRIPTIONS
from .potions import get_spec as _get_potion_spec, use_potion as _use_potion
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
from .card import Card
from .pending import ChoiceFrame, ThunkFrame

_PLAYER_START_HP = 80
_ENERGY_PER_TURN = 3
_CARDS_PER_DRAW = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _drain_stack(state: CombatState) -> None:
    """Pop and run ThunkFrames until the stack is empty or a ChoiceFrame is on top."""
    while state.pending_stack and isinstance(state.pending_stack[-1], ThunkFrame):
        frame = state.pending_stack.pop()
        frame.run(state)


def _tick_player_start(state: CombatState) -> None:
    """Decrement player duration-based statuses before enemies act."""
    if state.player_powers.vulnerable > 0:
        state.player_powers.vulnerable -= 1
    if state.player_powers.weak > 0:
        state.player_powers.weak -= 1
    if state.player_powers.frail > 0:
        state.player_powers.frail -= 1
    state.player_powers.entangled = False


def damage_player(state: CombatState, raw_dmg: int) -> None:
    """Apply damage to the player, updating block/hp and emitting HP_LOSS.

    After emit returns, callers should re-check ``state.player_hp`` to
    support Fairy-in-a-Bottle resurrection.
    """
    hp_before = state.player_hp
    nb, nhp = apply_damage(raw_dmg, state.player_block, state.player_hp)
    state.player_block = nb
    state.player_hp = nhp
    if nhp < hp_before:
        emit(state, Event.HP_LOSS, "player", hp_before=hp_before)


# Large slime → medium slime spawned on split
# Value is either a single name (both slots get the same) or a tuple of two
# names (slot i gets the first, slot i+1 gets the second).
_SPLIT_INTO: dict[str, str | tuple[str, str]] = {
    "AcidSlimeL":  "AcidSlimeM",
    "SpikeSlimeL": "SpikeSlimeM",
    "SlimeBoss":   ("AcidSlimeM", "SpikeSlimeM"),
}

# Ironclad starter deck: 5×Strike, 4×Defend, 1×Bash
IRONCLAD_STARTER: list[str] = (
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
        player_max_hp: int | None = None,
        potions: list[str] | None = None,
        max_potion_slots: int = 3,
        relics: frozenset[str] | None = None,
    ) -> None:
        potions = list(potions) if potions else []
        if len(potions) > max_potion_slots:
            raise ValueError(
                f"Too many potions ({len(potions)}) for max_potion_slots={max_potion_slots}."
            )
        self._deck = [Card(c) if isinstance(c, str) else c for c in deck]
        self._enemy_names = list(enemies)
        self._seed = seed
        self._player_start_hp = player_hp
        self._player_max_hp = player_max_hp if player_max_hp is not None else player_hp
        self._starting_potions = potions
        self._max_potion_slots = max_potion_slots
        self._starting_relics = relics if relics is not None else frozenset()
        self._state: CombatState | None = None
        self._damage_taken: int = 0
        self._max_hp_gained: int = 0
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
            player_max_hp=self._player_max_hp,
            player_block=0,
            player_powers=Powers(),
            energy=_ENERGY_PER_TURN,
            piles=piles,
            enemies=enemies,
            rng=rng,
            turn=0,
            potions=list(self._starting_potions),
            max_potion_slots=self._max_potion_slots,
            relics=self._starting_relics,
        )
        self._damage_taken = 0
        self._max_hp_gained = 0

        # Wire subscriptions for relics
        for relic_name in self._state.relics:
            for event, handler_name in RELIC_SUBSCRIPTIONS.get(relic_name, []):
                subscribe(self._state, event, handler_name, "player")

        # Wire subscriptions for potions
        # Potions can stack (e.g. two FairyInABottle), so we append one
        # subscriber per potion instance (bypassing idempotency).
        for potion_id in self._state.potions:
            for event, handler_name in POTION_SUBSCRIPTIONS.get(potion_id, []):
                self._state.subscribers[event]["player"].append(handler_name)

        # Wire subscriptions for player powers.
        # Duration-tick listeners for the player are NOT subscribed here because
        # the player tick is handled by _tick_player_start in the engine.
        # Enemy ticks are wired per-enemy via TURN_START events.
        # Triggered-effect and turn-boundary listeners are subscribed when active.
        always_subscribe_player = (
            "metallicize", "demon_form", "brutality", "berserk_energy",
            "strength_loss_eot", "dexterity_loss_eot",
        )
        for attr, subs in POWER_SUBSCRIPTIONS.items():
            if attr in always_subscribe_player:
                for event, handler_name in subs:
                    subscribe(self._state, event, handler_name, "player")
            elif attr not in ("vulnerable", "weak", "frail", "entangled", "ritual"):
                val = getattr(self._state.player_powers, attr, 0)
                if isinstance(val, bool):
                    if val:
                        for event, handler_name in subs:
                            subscribe(self._state, event, handler_name, "player")
                elif val > 0:
                    for event, handler_name in subs:
                        subscribe(self._state, event, handler_name, "player")

        # Run pre-battle hooks (skip Empty slots)
        for i, enemy in enumerate(self._state.enemies):
            if enemy.name != "Empty":
                run_pre_battle(enemy, self._state)
                # Wire name-based enemy subscriptions
                for event, handler_name in ENEMY_SUBSCRIPTIONS.get(enemy.name, []):
                    owner = "player" if event == Event.CARD_PLAYED else i
                    subscribe(self._state, event, handler_name, owner)
        # Wire condition-based enemy subscriptions (curl_up, spore_cloud, ritual)
        # and always subscribe tick handlers (they guard with > 0 internally)
        for i, enemy in enumerate(self._state.enemies):
            if enemy.name == "Empty":
                continue
            for power_attr, event, handler_name, owner_override in ENEMY_CONDITION_SUBSCRIPTIONS:
                owner = owner_override if owner_override is not None else i
                subscribe(self._state, event, handler_name, owner)

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

        # Fire COMBAT_START event
        emit(self._state, Event.COMBAT_START, "player")

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
            card = state.piles.hand[action.hand_index]
            card_spec = _get_card_spec(card.card_id)
            block_before = state.player_block
            _play_card(state, action.hand_index, action.target_index)
            block_gained = state.player_block - block_before

            # Emit CARD_PLAYED for subscribed listeners (Rage, Gremlin Nob)
            emit(state, Event.CARD_PLAYED, "player", card=card, card_spec=card_spec)

            # Emit BLOCK_GAINED if block was gained (Juggernaut)
            if block_gained > 0:
                emit(state, Event.BLOCK_GAINED, "player", amount=block_gained)

            # Triggered exhaust effects (Dark Embrace, Feel No Pain, Sentinel)
            if card_spec.exhausts or (state.player_powers.corruption and card_spec.card_type == CardType.SKILL):
                emit(state, Event.CARD_EXHAUSTED, "player", card=card)
            _drain_stack(state)

        elif action.action_type == ActionType.END_TURN:
            self._resolve_end_of_player_turn()

        elif action.action_type == ActionType.USE_POTION:
            _use_potion(state, action.potion_index, action.target_index)
            _drain_stack(state)

        elif action.action_type == ActionType.DISCARD_POTION:
            state.potions.pop(action.potion_index)

        elif action.action_type == ActionType.CHOOSE_CARD:
            frame = state.pending_stack.pop()
            assert isinstance(frame, ChoiceFrame)
            card = frame.choices[action.choice_index]
            frame.on_choose(state, card)
            _drain_stack(state)

        elif action.action_type == ActionType.SKIP_CHOICE:
            frame = state.pending_stack.pop()
            assert isinstance(frame, ChoiceFrame)
            frame.on_skip(state)
            _drain_stack(state)

        self._damage_taken = self._player_start_hp - state.player_hp
        self._max_hp_gained = state.player_max_hp - self._player_max_hp
        reward = float(state.player_hp - hp_before)

        info: dict = {}
        return self._observe(), reward, info

    @property
    def damage_taken(self) -> int:
        return self._damage_taken

    @property
    def max_hp_gained(self) -> int:
        """Max HP gained during this combat (e.g. from Feed killing an enemy)."""
        return self._max_hp_gained

    def valid_actions(self) -> list[Action]:
        """Return all legal actions for the current state.

        Returns an empty list when combat is done.  Card actions are returned
        for every (hand_index, target_index) combination — caller is responsible
        for deduplication if needed.  END_TURN is always included when not done.
        """
        if self._state is None or self._is_done():
            return []

        state = self._state

        # If a ChoiceFrame is on top of the stack, ONLY CHOOSE_CARD / SKIP_CHOICE are valid
        if state.pending_stack and isinstance(state.pending_stack[-1], ChoiceFrame):
            frame = state.pending_stack[-1]
            actions: list[Action] = []
            for i in range(len(frame.choices)):
                actions.append(Action.choose_card(i))
            actions.append(Action.skip_choice())
            return actions

        live_enemy_indices = [
            i for i, e in enumerate(state.enemies)
            if e.alive and not e.is_escaping
        ]
        entangled = state.player_powers.entangled
        actions: list[Action] = []

        for hi, card in enumerate(state.piles.hand):
            spec = _get_card_spec(card.card_id)
            if not spec.playable:
                continue
            # Corruption: skills cost 0
            if state.player_powers.corruption and spec.card_type == CardType.SKILL:
                effective_cost = card.cost_override if card.cost_override is not None else 0
            elif spec.x_cost:
                # X-cost cards cost all remaining energy (playable if energy > 0)
                effective_cost = card.cost_override if card.cost_override is not None else state.energy
            else:
                effective_cost = (
                    card.cost_override
                    if card.cost_override is not None
                    else spec.cost + (spec.upgrade.get("cost", 0) if card.upgraded else 0)
                )
            if effective_cost > state.energy:
                continue
            if entangled and spec.card_type in (CardType.SKILL, CardType.POWER):
                continue
            if spec.target == TargetType.SINGLE_ENEMY:
                for ti in live_enemy_indices:
                    actions.append(Action.play_card(hi, ti))
            else:
                actions.append(Action.play_card(hi, 0))

        for pi, potion_id in enumerate(state.potions):
            spec = _get_potion_spec(potion_id)
            if spec.target == TargetType.SINGLE_ENEMY:
                for ti in live_enemy_indices:
                    actions.append(Action.use_potion(pi, ti))
            else:
                actions.append(Action.use_potion(pi))
            actions.append(Action.discard_potion(pi))

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
                        "asleep": enemy.powers.asleep,
                        "enemy_metallicize": enemy.powers.enemy_metallicize,
                        "spore_cloud": enemy.powers.spore_cloud,
                        "entangled": enemy.powers.entangled,
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
                "dexterity": state.player_powers.dexterity,
                "metallicize": state.player_powers.metallicize,
                "strength_loss_eot": state.player_powers.strength_loss_eot,
                "dexterity_loss_eot": state.player_powers.dexterity_loss_eot,
            },
            energy=state.energy,
            hand=list(state.piles.hand),
            draw_pile=dict(Counter(c.card_id for c in state.piles.draw)),
            discard_pile=dict(Counter(c.card_id for c in state.piles.discard)),
            exhaust_pile=dict(Counter(c.card_id for c in state.piles.exhaust)),
            enemies=enemy_obs,
            done=self._is_done(),
            player_dead=state.player_hp <= 0,
            turn=state.turn,
            potions=list(state.potions),
            max_potion_slots=state.max_potion_slots,
            max_hp_gained=self._max_hp_gained,
            pending_choices=(
                list(state.pending_stack[-1].choices)
                if state.pending_stack and isinstance(state.pending_stack[-1], ChoiceFrame)
                else []
            ),
            pending_choice_kind=(
                state.pending_stack[-1].kind
                if state.pending_stack and isinstance(state.pending_stack[-1], ChoiceFrame)
                else ""
            ),
        )

    def _resolve_end_of_player_turn(self) -> None:
        state = self._state
        assert state is not None

        # Emit player TURN_END (Metallicize, strength/dex_loss_eot, etc.)
        emit(state, Event.TURN_END, "player")

        # Reset per-turn triggered power counters
        state.player_powers.rage_block = 0
        state.player_powers.double_tap = 0

        # Clear ephemeral cost overrides before discarding
        for card in state.piles.hand:
            card.clear_cost_override()

        # Ethereal: cards with ethereal=True that are still in hand are exhausted
        ethereal_in_hand = []
        for card in state.piles.hand:
            spec = _get_card_spec(card.card_id)
            if spec.ethereal:
                ethereal_in_hand.append(card)
        for card in ethereal_in_hand:
            state.piles.hand.remove(card)
            state.piles.move_to_exhaust(card)
            emit(state, Event.CARD_EXHAUSTED, "player", card=card)

        # Discard hand
        state.piles.discard_hand(state.rng)

        # Tick player power durations *before* enemies act so that statuses
        # applied by enemies this turn survive until the next player turn
        # (mirrors sts_lightspeed's decrementIfNotJustApplied logic).
        _tick_player_start(state)

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

            # Emit enemy TURN_START (vulnerable/weak/frail tick, etc.)
            emit(state, Event.TURN_START, i)

            # Sleeping enemies (Lagavulin): gain block from enemy_metallicize,
            # drain player strength, decrement sleep counter
            if enemy.powers.asleep:
                enemy.block += enemy.powers.enemy_metallicize
                if enemy.misc > 0:
                    enemy.misc -= 1
                if enemy.misc <= 0:
                    # Wake up after sleep timer expires — fall through to
                    # resolve an awake intent immediately (don't skip turn)
                    enemy.powers.asleep = False
                    enemy.powers.enemy_metallicize = 0
                    # Pick first awake intent and override the stored sleep intent
                    next_intent = pick_intent_with_state(
                        enemy, state.rng, state.turn + 1, state=state, enemy_index=i
                    )
                    self._intents[i] = next_intent
                else:
                    # Drain 1 player strength while sleeping (can push negative)
                    state.player_powers.strength -= 1
                    # Emit enemy TURN_END (Ritual, etc.)
                    emit(state, Event.TURN_END, i)
                    if not enemy.alive or enemy.is_escaping:
                        new_intents.append(self._intents[i])
                        continue
                    # Pick next intent (still sleeping)
                    next_intent = pick_intent_with_state(
                        enemy, state.rng, state.turn + 1, state=state, enemy_index=i
                    )
                    new_intents.append(next_intent)
                    continue

            # If enemy was woken up by player attack this turn (e.g. Lagavulin),
            # the stored intent is still the sleep intent — re-pick an awake one
            if enemy.name == "Lagavulin" and not enemy.powers.asleep and self._intents[i] is _LAG_SLEEP:
                next_intent = pick_intent_with_state(
                    enemy, state.rng, state.turn, state=state, enemy_index=i
                )
                self._intents[i] = next_intent

            # Resolve the intent chosen at start of last player turn
            intent = self._intents[i]
            self._resolve_enemy_intent(enemy, intent, i)

            # Emit enemy TURN_END (Ritual, etc.)
            emit(state, Event.TURN_END, i)

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
        # Apply accumulated energy loss (e.g. Gremlin Nob Bellow)
        if state.energy_loss_next_turn > 0:
            state.energy -= state.energy_loss_next_turn
            state.energy = max(0, state.energy)
            state.energy_loss_next_turn = 0

        # Emit player TURN_START (Demon Form, Brutality, Berserk, vulnerable/weak/frail tick)
        emit(state, Event.TURN_START, "player")

        state.piles.draw_cards(_CARDS_PER_DRAW, state.rng)

    def _resolve_split(self, enemy: EnemyState, idx: int) -> None:
        """Replace enemy at idx and idx+1 with two fresh medium slimes."""
        state = self._state
        assert state is not None

        split_target = _SPLIT_INTO[enemy.name]
        split_hp = enemy.hp

        if isinstance(split_target, tuple):
            # Heterogeneous split (e.g. SlimeBoss → AcidSlimeM + SpikeSlimeM)
            names = (split_target[0], split_target[1])
        else:
            # Homogeneous split (e.g. AcidSlimeL → 2× AcidSlimeM)
            names = (split_target, split_target)

        for slot, name in zip((idx, idx + 1), names):
            state.enemies[slot] = EnemyState(
                name=name,
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

        # Lagavulin Siphon Soul: -1 str, -1 dex to player (can push negative)
        if enemy.name == "Lagavulin" and intent.intent_type == IntentType.DEBUFF:
            state.player_powers.strength -= 1
            state.player_powers.dexterity -= 1
            return

        if intent.intent_type in (IntentType.ATTACK, IntentType.ATTACK_DEFEND, IntentType.ATTACK_DEBUFF):
            for _ in range(intent.hits):
                raw = calc_damage(intent.damage, enemy.powers, state.player_powers)
                damage_player(state, raw)
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

        # Status cards added to the player's discard or draw pile
        if intent.status_card_count:
            for _ in range(intent.status_card_count):
                if intent.status_to_draw:
                    state.piles.place_on_top(Card(intent.status_card_id))
                else:
                    state.piles.add_to_discard(Card(intent.status_card_id))

        # Energy loss applied at start of player's next turn (e.g. Gremlin Nob Bellow)
        if intent.energy_loss > 0:
            state.energy_loss_next_turn += intent.energy_loss
