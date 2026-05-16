"""
Rule-parity and make/unmake checks for the packed search engine.

Run:
    python engine_checks.py
"""

from __future__ import annotations

import random

from collections import defaultdict

from agent.minimax import is_terminal
from agent.moves import apply_action, is_game_over, legal_actions, simple_board_hash
from agent.search_state import SearchState, decode_referee_action, encode_referee_action
from referee.game import CellState, MAX_TURNS, PLACEMENT_TURNS, PlayerColor


def action_set(actions) -> set[int]:
    return {encode_referee_action(action) for action in actions}


def assert_sparse_equal(state: SearchState, sparse: dict) -> None:
    expected = {
        tuple(coord): (cell.color, cell.height)
        for coord, cell in sparse.items()
    }
    actual = {
        tuple(coord): (cell.color, cell.height)
        for coord, cell in state.to_sparse().items()
    }
    assert actual == expected, f"board mismatch\nactual={actual}\nexpected={expected}"


def fixed_scenarios() -> list[tuple[dict, int, PlayerColor]]:
    return [
        (
            {},
            0,
            PlayerColor.RED,
        ),
        (
            {
                (0, 0): CellState(PlayerColor.RED, 3),
                (7, 7): CellState(PlayerColor.BLUE, 3),
            },
            2,
            PlayerColor.RED,
        ),
        (
            {
                (1, 1): CellState(PlayerColor.RED, 2),
                (2, 3): CellState(PlayerColor.RED, 3),
                (4, 4): CellState(PlayerColor.RED, 1),
                (5, 2): CellState(PlayerColor.RED, 2),
                (3, 3): CellState(PlayerColor.BLUE, 1),
                (3, 4): CellState(PlayerColor.BLUE, 2),
                (6, 5): CellState(PlayerColor.BLUE, 3),
                (5, 5): CellState(PlayerColor.BLUE, 1),
            },
            30,
            PlayerColor.RED,
        ),
    ]


def check_fixed_scenarios() -> None:
    for sparse, turn_count, color in fixed_scenarios():
        state = SearchState.from_sparse(sparse, turn_count, color)
        assert action_set(legal_actions(sparse, color, turn_count)) == set(state.generate_actions())
        assert_sparse_equal(state, sparse)
        for action in state.generate_actions():
            before = state.signature()
            undo = state.make_move(action)
            state.unmake_move(undo)
            assert state.signature() == before, f"make/unmake mismatch for action={action}"


def check_random_play(seed: int = 30024, plies: int = 120) -> None:
    rng = random.Random(seed)
    sparse: dict = {}
    state = SearchState.empty()

    for turn_count in range(plies):
        color = PlayerColor.RED if turn_count % 2 == 0 else PlayerColor.BLUE
        sparse_actions = legal_actions(sparse, color, turn_count)
        packed_actions = state.generate_actions()
        assert action_set(sparse_actions) == set(packed_actions), f"legal action mismatch at turn {turn_count}"
        if not sparse_actions:
            break
        action = rng.choice(sparse_actions)
        encoded = encode_referee_action(action)
        sparse = apply_action(sparse, action, color)
        state.make_move(encoded)
        assert_sparse_equal(state, sparse)


def check_terminal_semantics() -> None:
    scenarios = [
        (
            {
                (0, 0): CellState(PlayerColor.RED, 3),
            },
            PLACEMENT_TURNS,
            PlayerColor.RED,
        ),
        (
            {
                (0, 0): CellState(PlayerColor.RED, 1),
                (0, 1): CellState(PlayerColor.BLUE, 2),
                (1, 0): CellState(PlayerColor.BLUE, 2),
            },
            PLACEMENT_TURNS + 5,
            PlayerColor.RED,
        ),
        (
            {
                (0, 0): CellState(PlayerColor.RED, 3),
                (7, 7): CellState(PlayerColor.BLUE, 3),
            },
            PLACEMENT_TURNS + MAX_TURNS,
            PlayerColor.RED,
        ),
    ]
    for sparse, turn_count, color in scenarios:
        legacy_counter = defaultdict(int)
        legacy_hash = simple_board_hash(sparse, turn_count)
        state = SearchState.from_sparse(sparse, turn_count, color)
        assert is_game_over(legacy_counter, sparse, turn_count, legacy_hash) == is_terminal(
            state, defaultdict(int)
        )

    repeated = SearchState.from_sparse(
        {
            (0, 0): CellState(PlayerColor.RED, 3),
            (7, 7): CellState(PlayerColor.BLUE, 3),
        },
        PLACEMENT_TURNS + 4,
        PlayerColor.RED,
    )
    repetitions = defaultdict(int)
    repetitions[repeated.hash_key] = 3
    assert is_terminal(repeated, repetitions)


def main() -> None:
    check_fixed_scenarios()
    check_random_play()
    check_terminal_semantics()
    print("engine checks passed")


if __name__ == "__main__":
    main()
