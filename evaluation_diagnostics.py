"""
Offline diagnostics for comparing the static evaluator against shallow search.

Run:
    python evaluation_diagnostics.py
    python evaluation_diagnostics.py --depth 3
"""

from __future__ import annotations

import argparse
import time
from collections import defaultdict
from dataclasses import dataclass

from agent.minimax import _feature_vector, evaluate_state, iterative_deepening_search
from agent.search_state import SearchState, decode_referee_action
from benchmark import SCENARIOS
from referee.game import CellState, PlayerColor


@dataclass(frozen=True, slots=True)
class ActionDiagnostic:
    action: int
    static_value: float
    search_value: float
    static_rank: int
    search_rank: int
    my_features: object
    opp_features: object

    @property
    def rank_gap(self) -> int:
        return self.static_rank - self.search_rank


def clone_state(state: SearchState) -> SearchState:
    return SearchState(
        state.red_bits,
        state.blue_bits,
        state.heights.copy(),
        state.red_tokens,
        state.blue_tokens,
        state.turn_count,
        state.side_to_move,
        state.hash_key,
    )


def analyze_position(
    label: str,
    board: dict[tuple[int, int], CellState],
    turn_count: int,
    color: PlayerColor,
    depth: int,
) -> list[ActionDiagnostic]:
    root = SearchState.from_sparse(board, turn_count, color)
    records: list[tuple[int, float, float]] = []

    for action in root.generate_actions():
        child = clone_state(root)
        child.make_move(action)
        static_value = evaluate_state(child, color.value, defaultdict(int))
        my_features = _feature_vector(child, color.value)
        opp_features = _feature_vector(child, color.opponent.value)
        search_value, _move, _stats = iterative_deepening_search(
            child,
            defaultdict(int),
            color,
            depth,
            time.perf_counter() + 30.0,
        )
        records.append((action, static_value, search_value, my_features, opp_features))

    static_sorted = sorted(records, key=lambda item: item[1], reverse=True)
    search_sorted = sorted(records, key=lambda item: item[2], reverse=True)
    static_rank = {action: idx + 1 for idx, (action, _s, _d, _mf, _of) in enumerate(static_sorted)}
    search_rank = {action: idx + 1 for idx, (action, _s, _d, _mf, _of) in enumerate(search_sorted)}

    diagnostics = [
        ActionDiagnostic(
            action=action,
            static_value=static_value,
            search_value=search_value,
            static_rank=static_rank[action],
            search_rank=search_rank[action],
            my_features=my_features,
            opp_features=opp_features,
        )
        for action, static_value, search_value, my_features, opp_features in records
    ]
    diagnostics.sort(
        key=lambda item: (
            abs(item.rank_gap),
            abs(item.static_value - item.search_value),
            -item.search_value,
        ),
        reverse=True,
    )

    print()
    print(f"== {label} ==")
    print(f"side_to_move={color.name} actions={len(diagnostics)} compare_depth={depth}")
    print(
        f"{'Action':<22} {'Static':>10} {'Search':>10} "
        f"{'Static rank':>12} {'Search rank':>12} {'Gap':>6}"
    )
    for item in diagnostics[:10]:
        print(
            f"{str(decode_referee_action(item.action)):<22} "
            f"{item.static_value:>10.2f} {item.search_value:>10.2f} "
            f"{item.static_rank:>12} {item.search_rank:>12} {item.rank_gap:>6}"
        )
        print(f"    mine={item.my_features}")
        print(f"    opp ={item.opp_features}")
    return diagnostics


def mirrored_opening_position() -> tuple[str, dict[tuple[int, int], CellState], int, PlayerColor]:
    board = {
        (2, 3): CellState(PlayerColor.RED, 3),
        (2, 4): CellState(PlayerColor.RED, 3),
        (3, 2): CellState(PlayerColor.RED, 3),
        (3, 3): CellState(PlayerColor.RED, 3),
        (4, 4): CellState(PlayerColor.BLUE, 3),
        (4, 5): CellState(PlayerColor.BLUE, 3),
        (5, 3): CellState(PlayerColor.BLUE, 3),
        (5, 4): CellState(PlayerColor.BLUE, 3),
    }
    return "mirrored-opening", board, 8, PlayerColor.RED


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=2)
    args = parser.parse_args()

    scenarios = [scenario() for scenario in SCENARIOS]
    scenarios.append(mirrored_opening_position())

    for label, board, turn_count, color in scenarios:
        analyze_position(label, board, turn_count, color, args.depth)


if __name__ == "__main__":
    main()
