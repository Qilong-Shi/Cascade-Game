from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass

from referee.game import MAX_TURNS, PLACEMENT_TURNS, CellState, Coord, PlayerColor

from .search_state import (
    BLUE,
    CASCADE,
    EAT,
    RED,
    CENTER_WEIGHTS,
    EDGE_WEIGHTS,
    NEXT_INDEX,
    SearchState,
    action_kind,
    color_to_int,
    decode_referee_action,
    decode_source_and_direction,
)


WIN_SCORE = 1_000_000
LOSS_SCORE = -WIN_SCORE
TURN_LIMIT_WIN_SCORE = 100_000
DRAW_BIAS = 50
REPETITION_WEIGHT = 12

EXACT = 0
LOWER_BOUND = 1
UPPER_BOUND = 2

TACTICAL_EXTENSION_LIMIT = int(os.environ.get("AGENT_TACTICAL_EXTENSION", "0"))
MIN_EXTENSION_ENEMY_LOSS = 2


@dataclass(slots=True)
class SearchStats:
    nodes: int = 0
    leaves: int = 0
    cutoffs: int = 0
    tt_hits: int = 0
    completed_depth: int = 0
    max_ply: int = 0


@dataclass(slots=True)
class TTEntry:
    depth: int
    value: float
    flag: int
    best_move: int | None


class SearchTimeout(RuntimeError):
    pass

# Legacy adapter for older diagnostic scripts; the hot path is `iterative_deepening_search()` directly on `SearchState`
def iterative_deepening_search(
    state: SearchState,
    repetition_counts: defaultdict[int, int],
    me: PlayerColor | int,
    max_depth: int,
    deadline: float,
) -> tuple[float, int | None, SearchStats]:
    me_int = color_to_int(me)
    stats = SearchStats()
    transposition_table: dict[tuple[int, int, int], TTEntry] = {}
    repetition_signature = _repetition_signature(repetition_counts)
    best_value = evaluate_state(state, me_int, repetition_counts)
    best_move: int | None = None
    preferred_move: int | None = None

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        try:
            value, move = _alpha_beta(
                state,
                depth,
                float("-inf"),
                float("inf"),
                me_int,
                deadline,
                transposition_table,
                repetition_counts,
                repetition_signature,
                stats,
                ply=0,
                preferred_move=preferred_move,
                extension_remaining=TACTICAL_EXTENSION_LIMIT,
            )
        except SearchTimeout:
            break
        best_value = value
        if move is not None:
            best_move = move
            preferred_move = move
        stats.completed_depth = depth

    return best_value, best_move, stats


def alpha_beta(
    state_counter: defaultdict[int, int],
    board: dict[Coord | tuple[int, int], CellState],
    depth: int,
    color: PlayerColor,
    turn_count: int,
    me: PlayerColor,
    alpha: float,
    beta: float,
) -> tuple[float, object | None]:
    """
    Backwards-compatible wrapper for older diagnostic scripts.

    The hot path uses `iterative_deepening_search()` directly on `SearchState`;
    this adapter exists only so legacy utilities that still pass sparse boards
    continue to work while the engine internals evolve.
    """
    state = SearchState.from_sparse(board, turn_count, color)
    stats = SearchStats()
    value, move = _alpha_beta(
        state,
        depth,
        alpha,
        beta,
        me.value,
        time.perf_counter() + 60.0,
        {},
        state_counter,
        _repetition_signature(state_counter),
        stats,
        ply=0,
        preferred_move=None,
        extension_remaining=TACTICAL_EXTENSION_LIMIT,
    )
    return value, None if move is None else decode_referee_action(move)


def _alpha_beta(
    state: SearchState,
    depth: int,
    alpha: float,
    beta: float,
    me: int,
    deadline: float,
    tt: dict[tuple[int, int, int], TTEntry],
    repetition_counts: defaultdict[int, int],
    repetition_signature: int,
    stats: SearchStats,
    ply: int,
    preferred_move: int | None,
    extension_remaining: int,
) -> tuple[float, int | None]:
    stats.nodes += 1
    stats.max_ply = max(stats.max_ply, ply)
    if stats.nodes & 0xFF == 0 and time.perf_counter() >= deadline:
        raise SearchTimeout

    if is_terminal(state, repetition_counts):
        stats.leaves += 1
        return evaluate_state(state, me, repetition_counts), None

    if depth <= 0:
        if extension_remaining <= 0:
            stats.leaves += 1
            return evaluate_state(state, me, repetition_counts), None
        forcing = forcing_actions(state)
        if not forcing:
            stats.leaves += 1
            return evaluate_state(state, me, repetition_counts), None
        return _search_actions(
            state,
            forcing,
            0,
            alpha,
            beta,
            me,
            deadline,
            tt,
            repetition_counts,
            repetition_signature,
            stats,
            ply,
            extension_remaining - 1,
        )

    tt_key = (state.hash_key, state.turn_count, repetition_signature)
    tt_entry = tt.get(tt_key)
    if tt_entry is not None and tt_entry.depth >= depth:
        stats.tt_hits += 1
        if tt_entry.flag == EXACT:
            return tt_entry.value, tt_entry.best_move
        if tt_entry.flag == LOWER_BOUND:
            alpha = max(alpha, tt_entry.value)
        else:
            beta = min(beta, tt_entry.value)
        if alpha >= beta:
            return tt_entry.value, tt_entry.best_move

    actions = ordered_actions(
        state,
        preferred_move if preferred_move is not None else tt_entry.best_move if tt_entry else None,
    )
    if not actions:
        stats.leaves += 1
        return evaluate_state(state, me, repetition_counts), None

    alpha_orig = alpha
    beta_orig = beta
    value, best_move = _search_actions(
        state,
        actions,
        depth - 1,
        alpha,
        beta,
        me,
        deadline,
        tt,
        repetition_counts,
        repetition_signature,
        stats,
        ply,
        extension_remaining,
    )

    flag = EXACT
    if value <= alpha_orig:
        flag = UPPER_BOUND
    elif value >= beta_orig:
        flag = LOWER_BOUND
    previous = tt.get(tt_key)
    if previous is None or depth >= previous.depth:
        tt[tt_key] = TTEntry(depth, value, flag, best_move)
    return value, best_move


def _search_actions(
    state: SearchState,
    actions: list[int],
    next_depth: int,
    alpha: float,
    beta: float,
    me: int,
    deadline: float,
    tt: dict[tuple[int, int, int], TTEntry],
    repetition_counts: defaultdict[int, int],
    repetition_signature: int,
    stats: SearchStats,
    ply: int,
    extension_remaining: int,
) -> tuple[float, int | None]:
    maximizing = state.side_to_move == me
    best_move: int | None = None
    best_value = float("-inf") if maximizing else float("inf")

    for action in actions:
        undo = state.make_move(action)
        child_hash_added = False
        child_repetition_signature = repetition_signature
        if state.play_phase:
            old_count = repetition_counts.get(state.hash_key, 0)
            repetition_counts[state.hash_key] += 1
            child_repetition_signature = _updated_repetition_signature(
                repetition_signature,
                state.hash_key,
                old_count,
                old_count + 1,
            )
            child_hash_added = True
        try:
            value, _ = _alpha_beta(
                state,
                next_depth,
                alpha,
                beta,
                me,
                deadline,
                tt,
                repetition_counts,
                child_repetition_signature,
                stats,
                ply + 1,
                preferred_move=None,
                extension_remaining=extension_remaining,
            )
        finally:
            if child_hash_added:
                _pop_repetition(repetition_counts, state.hash_key)
            state.unmake_move(undo)

        if maximizing:
            if value > best_value:
                best_value = value
                best_move = action
            alpha = max(alpha, best_value)
        else:
            if value < best_value:
                best_value = value
                best_move = action
            beta = min(beta, best_value)

        if alpha >= beta:
            stats.cutoffs += 1
            break

    return best_value, best_move


def ordered_actions(state: SearchState, preferred_move: int | None = None) -> list[int]:
    actions = state.generate_actions()
    if not actions:
        return actions

    def ordering_score(action: int) -> tuple[int, int, int, int]:
        if action == preferred_move:
            return (3, 0, 0, 0)
        kind = action_kind(action)
        if kind == EAT:
            idx, direction = decode_source_and_direction(action)
            target = NEXT_INDEX[idx][direction]
            return (2, state.heights[target], 0, -action)
        if kind == CASCADE:
            return (1, cascade_pressure(state, action), 0, -action)
        return (0, 0, 0, -action)

    actions.sort(key=ordering_score, reverse=True)
    return actions


def forcing_actions(state: SearchState) -> list[int]:
    actions = ordered_actions(state)
    forcing: list[int] = []
    for action in actions:
        kind = action_kind(action)
        if kind == EAT:
            idx, direction = decode_source_and_direction(action)
            target = NEXT_INDEX[idx][direction]
            if target != -1 and state.heights[target] >= MIN_EXTENSION_ENEMY_LOSS:
                forcing.append(action)
        elif kind == CASCADE and cascade_pressure(state, action) > 0:
            forcing.append(action)
    return forcing


def cascade_pressure(state: SearchState, action: int) -> int:
    idx, direction = decode_source_and_direction(action)
    source_color = state.color_at(idx)
    value = 0
    current = idx
    for _ in range(state.heights[idx]):
        current = NEXT_INDEX[current][direction]
        if current == -1:
            break
        target_color = state.color_at(current)
        if target_color != -1 and target_color != source_color:
            value += state.heights[current]
    return value


def is_terminal(state: SearchState, repetition_counts: defaultdict[int, int]) -> bool:
    if not state.play_phase:
        return False
    if state.red_tokens == 0 or state.blue_tokens == 0:
        return True
    if state.turn_count - PLACEMENT_TURNS >= MAX_TURNS:
        return True
    if repetition_counts.get(state.hash_key, 0) >= 3:
        return True
    return not state.has_legal_actions()


def evaluate_board(board: dict[Coord | tuple[int, int], CellState], me: PlayerColor) -> float:
    state = SearchState.from_sparse(board, 0, me)
    return float(state.token_count(me.value) - state.token_count(me.opponent.value))


def evaluate(
    state_counter: defaultdict[int, int],
    board: dict[Coord | tuple[int, int], CellState],
    turn_count: int,
    me: PlayerColor,
    _hsh: tuple | None = None,
) -> float:
    state = SearchState.from_sparse(board, turn_count, PlayerColor.RED if turn_count % 2 == 0 else PlayerColor.BLUE)
    return evaluate_state(state, me.value, state_counter)


def evaluate_state(
    state: SearchState,
    me: int,
    repetition_counts: defaultdict[int, int],
) -> float:
    opp = BLUE if me == RED else RED
    my_tokens = state.token_count(me)
    opp_tokens = state.token_count(opp)

    if state.play_phase:
        if opp_tokens == 0:
            return WIN_SCORE
        if my_tokens == 0:
            return LOSS_SCORE

        repeat_count = repetition_counts.get(state.hash_key, 0)
        if repeat_count >= 3 or not state.has_legal_actions():
            return draw_score(my_tokens, opp_tokens)

        play_turn = state.turn_count - PLACEMENT_TURNS
        if play_turn >= MAX_TURNS:
            token_diff = my_tokens - opp_tokens
            if token_diff > 0:
                return TURN_LIMIT_WIN_SCORE + token_diff
            if token_diff < 0:
                return -TURN_LIMIT_WIN_SCORE + token_diff
            return 0

    material_weight = 24
    tactical_weight = 8
    mobility_weight = 0.5
    stack_weight = 1.5
    center_weight = 2.0
    edge_weight = 1.0

    mine = _feature_vector(state, me)
    theirs = _feature_vector(state, opp)
    repetition_score = repetition_bias(my_tokens, opp_tokens) * max(0, repetition_counts.get(state.hash_key, 0) - 1)

    return (
        (my_tokens - opp_tokens) * material_weight
        + (mine.capture_value - theirs.capture_value) * tactical_weight
        + (mine.mobility - theirs.mobility) * mobility_weight
        + (mine.stacks - theirs.stacks) * stack_weight
        + (mine.center_control - theirs.center_control) * center_weight
        + (theirs.edge_exposure - mine.edge_exposure) * edge_weight
        + repetition_score
    )


@dataclass(slots=True)
class _FeatureVector:
    stacks: int = 0
    mobility: int = 0
    capture_value: int = 0
    center_control: float = 0.0
    edge_exposure: float = 0.0


def _feature_vector(state: SearchState, color: int) -> _FeatureVector:
    result = _FeatureVector()
    own_bits = state.red_bits if color == RED else state.blue_bits
    capture_targets = 0
    bits = own_bits

    while bits:
        bit = bits & -bits
        idx = bit.bit_length() - 1
        height = state.heights[idx]
        result.stacks += 1
        result.center_control += CENTER_WEIGHTS[idx] * height
        result.edge_exposure += EDGE_WEIGHTS[idx] * height
        if height >= 2:
            result.mobility += 4

        for direction in range(4):
            target = NEXT_INDEX[idx][direction]
            if target == -1:
                continue
            target_color = state.color_at(target)
            if target_color == -1 or target_color == color:
                result.mobility += 1
            elif height >= state.heights[target]:
                result.mobility += 1
                capture_targets |= 1 << target

        bits ^= bit

    while capture_targets:
        bit = capture_targets & -capture_targets
        idx = bit.bit_length() - 1
        result.capture_value += state.heights[idx]
        capture_targets ^= bit
    return result


def draw_score(my_tokens: int, opp_tokens: int) -> int:
    if my_tokens > opp_tokens:
        return -DRAW_BIAS
    if my_tokens < opp_tokens:
        return DRAW_BIAS
    return 0


def repetition_bias(my_tokens: int, opp_tokens: int) -> int:
    if my_tokens > opp_tokens:
        return -REPETITION_WEIGHT
    if my_tokens < opp_tokens:
        return REPETITION_WEIGHT
    return 0




def _pop_repetition(repetition_counts: defaultdict[int, int], key: int) -> None:
    count = repetition_counts.get(key, 0)
    if count <= 1:
        repetition_counts.pop(key, None)
    else:
        repetition_counts[key] = count - 1


def _repetition_component(key: int, count: int) -> int:
    if count <= 0:
        return 0
    return ((key * 0x9E3779B97F4A7C15) ^ (count * 0xBF58476D1CE4E5B9)) & 0xFFFFFFFFFFFFFFFF


def _repetition_signature(repetition_counts: defaultdict[int, int]) -> int:
    signature = 0
    for key, count in repetition_counts.items():
        signature ^= _repetition_component(key, count)
    return signature


def _updated_repetition_signature(signature: int, key: int, old_count: int, new_count: int) -> int:
    return signature ^ _repetition_component(key, old_count) ^ _repetition_component(key, new_count)
