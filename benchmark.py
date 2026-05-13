"""
Timing benchmark for the minimax / alpha-beta implementation.

Profiles `alpha_beta` at depth 3 across four representative board states
(empty, mid-placement, post-placement, mid-play) and reports which functions
in agent/minimax.py and agent/moves.py dominate runtime.

Run:
    python3 benchmark.py
"""

import cProfile
import pstats
import statistics
import time
from collections import defaultdict

from agent.minimax import alpha_beta
from agent.moves import is_game_over, legal_actions
from referee.game import CellState, Coord, PlayerColor


DEPTH = 4
WALL_CLOCK_REPEATS = 3
REPORT_ROWS = 15


def empty_board() -> tuple[str, str, dict[Coord, CellState], int, PlayerColor]:
    return "empty", "empty (turn 0, placement start)", {}, 0, PlayerColor.RED


def mid_placement_board() -> tuple[str, str, dict[Coord, CellState], int, PlayerColor]:
    board = {
        Coord(0, 0): CellState(PlayerColor.RED, 3),
        Coord(7, 7): CellState(PlayerColor.RED, 3),
        Coord(0, 7): CellState(PlayerColor.BLUE, 3),
        Coord(7, 0): CellState(PlayerColor.BLUE, 3),
    }
    return "mid-place", "mid-placement (turn 4)", board, 4, PlayerColor.RED


def post_placement_board() -> tuple[str, str, dict[Coord, CellState], int, PlayerColor]:
    board = {
        Coord(0, 0): CellState(PlayerColor.RED, 3),
        Coord(2, 2): CellState(PlayerColor.RED, 3),
        Coord(5, 5): CellState(PlayerColor.RED, 3),
        Coord(7, 7): CellState(PlayerColor.RED, 3),
        Coord(0, 7): CellState(PlayerColor.BLUE, 3),
        Coord(2, 5): CellState(PlayerColor.BLUE, 3),
        Coord(5, 2): CellState(PlayerColor.BLUE, 3),
        Coord(7, 0): CellState(PlayerColor.BLUE, 3),
    }
    return "post-place", "post-placement (turn 8)", board, 8, PlayerColor.RED


def mid_play_board() -> tuple[str, str, dict[Coord, CellState], int, PlayerColor]:
    # Mixed stack heights, both colors, adjacent pieces so eat/cascade options
    # all exercise their branches.
    board = {
        Coord(1, 1): CellState(PlayerColor.RED, 2),
        Coord(2, 3): CellState(PlayerColor.RED, 3),
        Coord(4, 4): CellState(PlayerColor.RED, 1),
        Coord(5, 2): CellState(PlayerColor.RED, 2),
        Coord(3, 3): CellState(PlayerColor.BLUE, 1),
        Coord(3, 4): CellState(PlayerColor.BLUE, 2),
        Coord(6, 5): CellState(PlayerColor.BLUE, 3),
        Coord(5, 5): CellState(PlayerColor.BLUE, 1),
    }
    return "mid-play", "mid-play (turn 30)", board, 30, PlayerColor.RED


SCENARIOS = [
    empty_board,
    mid_placement_board,
    post_placement_board,
    mid_play_board,
]


def sanity_check(name: str, board: dict[Coord, CellState], turn: int, color: PlayerColor) -> None:
    counter = defaultdict(int)
    assert not is_game_over(counter, board, turn), (
        f"[{name}] board is terminal — minimax will short-circuit and profile will be empty"
    )
    actions = legal_actions(board, color, turn)
    assert actions, f"[{name}] no legal actions for {color.name} — minimax has nothing to search"


def run_once(board: dict[Coord, CellState], turn: int, color: PlayerColor) -> float:
    counter: defaultdict[str, int] = defaultdict(int)
    t0 = time.perf_counter()
    alpha_beta(counter, board, DEPTH, color, turn, float('-inf'), float('inf'))
    return time.perf_counter() - t0


def profile_once(board: dict[Coord, CellState], turn: int, color: PlayerColor) -> pstats.Stats:
    counter: defaultdict[str, int] = defaultdict(int)
    profiler = cProfile.Profile()
    profiler.enable()
    alpha_beta(counter, board, DEPTH, color, turn, float('-inf'), float('inf'))
    profiler.disable()
    return pstats.Stats(profiler)


def print_section(title: str) -> None:
    bar = "=" * 78
    print(f"\n{bar}\n{title}\n{bar}")


def extract_func_tottime(stats: pstats.Stats) -> dict[str, float]:
    """Pull self-time (tottime) per agent-module function for the summary table.

    We use tottime, not cumtime: cumtime double-counts because every parent's
    cumtime includes children. e.g. `evaluate`'s cumtime includes the
    `is_game_over` → `legal_actions` calls it makes internally. Tottime is the
    function's own work, which is what you want when answering "which function
    should I optimize first?"
    """
    result: dict[str, float] = {}
    for (filename, _lineno, funcname), (_cc, _nc, tt, _ct, _callers) in stats.stats.items():
        if "minimax.py" in filename or "moves.py" in filename:
            result[funcname] = result.get(funcname, 0.0) + tt
    return result


def main() -> None:
    print(f"Benchmarking alpha_beta at depth={DEPTH}")
    print(f"Wall-clock repeats per scenario: {WALL_CLOCK_REPEATS}")

    summary: list[tuple[str, str, float, dict[str, float]]] = []

    for scenario in SCENARIOS:
        short_name, name, board, turn, color = scenario()
        print_section(f"Scenario: {name}  |  side to move: {color.name}")

        sanity_check(name, board, turn, color)

        wall_clocks = [run_once(board, turn, color) for _ in range(WALL_CLOCK_REPEATS)]
        median_wall = statistics.median(wall_clocks)
        print(
            f"Wall-clock (no profiler): "
            f"min={min(wall_clocks):.4f}s  median={median_wall:.4f}s  max={max(wall_clocks):.4f}s"
        )

        stats = profile_once(board, turn, color)
        stats.sort_stats("cumulative").print_stats(r"(minimax|moves)\.py", REPORT_ROWS)

        summary.append((short_name, name, median_wall, extract_func_tottime(stats)))

    print_cross_scenario_summary(summary)


def print_cross_scenario_summary(
    summary: list[tuple[str, str, float, dict[str, float]]],
) -> None:
    print_section(
        "Cross-scenario summary: SELF-time per function (seconds)\n"
        "(self-time only — excludes time spent in children. Pick the biggest row to optimize.)"
    )

    all_funcs = set()
    for _, _, _, funcs in summary:
        all_funcs.update(funcs)

    name_width = max(len(f) for f in all_funcs) + 2
    col_width = 12

    header = "Function".ljust(name_width) + "".join(
        s[0].rjust(col_width) for s in summary
    )
    print(header)
    print("-" * len(header))

    func_totals = []
    for func in all_funcs:
        total = sum(funcs.get(func, 0.0) for _, _, _, funcs in summary)
        func_totals.append((func, total))
    func_totals.sort(key=lambda x: -x[1])

    for func, _ in func_totals:
        row = func.ljust(name_width)
        for _, _, _, funcs in summary:
            cumt = funcs.get(func, 0.0)
            row += f"{cumt:>{col_width}.4f}"
        print(row)

    print()
    print("Wall-clock (median, no profiler):")
    for _, name, median_wall, _ in summary:
        print(f"  {name:40s}  {median_wall:.4f}s")


if __name__ == "__main__":
    main()
