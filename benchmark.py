"""
Benchmark the packed search engine on play-phase positions.

Quick run:
    python benchmark.py

Deeper stress run:
    python benchmark.py --stress
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections import defaultdict

from agent.minimax import iterative_deepening_search
from agent.search_state import SearchState
from referee.game import CellState, PlayerColor


def post_placement_board():
    board = {
        (0, 0): CellState(PlayerColor.RED, 3),
        (2, 2): CellState(PlayerColor.RED, 3),
        (5, 5): CellState(PlayerColor.RED, 3),
        (7, 7): CellState(PlayerColor.RED, 3),
        (0, 7): CellState(PlayerColor.BLUE, 3),
        (2, 5): CellState(PlayerColor.BLUE, 3),
        (5, 2): CellState(PlayerColor.BLUE, 3),
        (7, 0): CellState(PlayerColor.BLUE, 3),
    }
    return "post-placement", board, 8, PlayerColor.RED


def mid_play_board():
    board = {
        (1, 1): CellState(PlayerColor.RED, 2),
        (2, 3): CellState(PlayerColor.RED, 3),
        (4, 4): CellState(PlayerColor.RED, 1),
        (5, 2): CellState(PlayerColor.RED, 2),
        (3, 3): CellState(PlayerColor.BLUE, 1),
        (3, 4): CellState(PlayerColor.BLUE, 2),
        (6, 5): CellState(PlayerColor.BLUE, 3),
        (5, 5): CellState(PlayerColor.BLUE, 1),
    }
    return "mid-play", board, 30, PlayerColor.RED


def tactical_board():
    board = {
        (1, 1): CellState(PlayerColor.RED, 4),
        (2, 1): CellState(PlayerColor.RED, 2),
        (4, 3): CellState(PlayerColor.RED, 2),
        (1, 2): CellState(PlayerColor.BLUE, 2),
        (3, 3): CellState(PlayerColor.BLUE, 3),
        (4, 4): CellState(PlayerColor.BLUE, 1),
        (6, 5): CellState(PlayerColor.BLUE, 2),
    }
    return "tactical", board, 42, PlayerColor.RED


SCENARIOS = (post_placement_board, mid_play_board, tactical_board)


def run_once(state: SearchState, color: PlayerColor, max_depth: int, budget: float):
    counter = defaultdict(int)
    started = time.perf_counter()
    value, move, stats = iterative_deepening_search(
        state,
        counter,
        color,
        max_depth,
        started + budget,
    )
    return time.perf_counter() - started, value, move, stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", action="store_true")
    args = parser.parse_args()

    repeats = 3 if not args.stress else 1
    max_depth = 6 if not args.stress else 8
    budget = 0.50 if not args.stress else 2.0
    print(f"Benchmarking packed search: max_depth={max_depth}, budget={budget:.2f}s, repeats={repeats}")

    for scenario in SCENARIOS:
        label, board, turn_count, color = scenario()
        durations = []
        depths = []
        nodes = []
        print(f"\n== {label} ==")
        for _ in range(repeats):
            state = SearchState.from_sparse(board, turn_count, color)
            elapsed, value, move, stats = run_once(state, color, max_depth, budget)
            durations.append(elapsed)
            depths.append(stats.completed_depth)
            nodes.append(stats.nodes)
            print(
                f"elapsed={elapsed:.4f}s value={value:.1f} move={move} "
                f"depth={stats.completed_depth} nodes={stats.nodes} cutoffs={stats.cutoffs} tt_hits={stats.tt_hits}"
            )
        print(
            f"median_elapsed={statistics.median(durations):.4f}s "
            f"median_depth={statistics.median(depths)} median_nodes={int(statistics.median(nodes))}"
        )


if __name__ == "__main__":
    main()
