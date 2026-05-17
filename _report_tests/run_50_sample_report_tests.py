from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import sys
import time


@dataclass(frozen=True)
class GameSpec:
    label: str
    red: str
    blue: str
    current_is_red: bool
    trial: int
    seed: int | None = None


# 24 + 14 + 12 = 50 total games, with each group split evenly by side.
TEST_GROUPS = [
    ("Versus random baseline", "Tests robustness against seeded random legal play", "_report_tests.random_agent", 12),
    ("Versus greedy baseline", "Tests tactical strength against one-step evaluation", "_report_tests.greedy_agent", 7),
    ("Self-play against earlier version", "Compares against the depth-3 earlier variant", "_report_tests.depth3_agent", 6),
]

BASE_RANDOM_SEED = 300500
SUMMARY_PATH = Path("_report_tests") / "sample50_summary.md"


def run_game(spec: GameSpec) -> tuple[str, float]:
    safe = re.sub(r"[^a-z0-9]+", "_", spec.label.lower()).strip("_")
    side = "current_red" if spec.current_is_red else "current_blue"
    seed_suffix = f"_seed_{spec.seed}" if spec.seed is not None else ""
    log_path = Path("_report_tests") / f"sample50_{safe}_{side}_game_{spec.trial:02d}{seed_suffix}.log"

    env = os.environ.copy()
    if spec.seed is not None:
        env["REPORT_RANDOM_SEED"] = str(spec.seed)

    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        proc = subprocess.run(
            [sys.executable, "-m", "referee", "-v", "0", spec.red, spec.blue],
            cwd=".",
            env=env,
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            timeout=360,
        )
    elapsed = time.perf_counter() - started
    output = log_path.read_text(encoding="utf-8", errors="replace")

    if proc.returncode != 0:
        tail = "\n".join(output.splitlines()[-25:])
        raise RuntimeError(f"Game failed ({spec.red} vs {spec.blue}), rc={proc.returncode}\n{tail}")

    match = re.search(r"result:\s*(.+)", output)
    if not match:
        tail = "\n".join(output.splitlines()[-25:])
        raise RuntimeError(f"Could not parse result for {spec.red} vs {spec.blue}\n{tail}")

    return match.group(1).strip(), elapsed


def current_agent_won(result: str, current_is_red: bool) -> bool:
    if result == "draw":
        return False
    return ("player 1 [agent:Agent]" in result) if current_is_red else ("player 2 [agent:Agent]" in result)


def build_specs() -> list[GameSpec]:
    specs: list[GameSpec] = []
    next_seed = BASE_RANDOM_SEED
    for name, _notes, opponent, repeats_per_side in TEST_GROUPS:
        for i in range(1, repeats_per_side + 1):
            seed = next_seed if opponent.endswith("random_agent") else None
            specs.append(GameSpec(name, "agent", opponent, True, i, seed))
            if seed is not None:
                next_seed += 1
        for i in range(1, repeats_per_side + 1):
            seed = next_seed if opponent.endswith("random_agent") else None
            specs.append(GameSpec(name, opponent, "agent", False, i, seed))
            if seed is not None:
                next_seed += 1
    return specs


def emit(lines: list[str], text: str = "") -> None:
    print(text)
    lines.append(text)


def main() -> None:
    specs = build_specs()
    grouped: dict[str, dict[str, object]] = {
        name: {"games": 0, "red_games": 0, "blue_games": 0, "red_wins": 0, "blue_wins": 0, "elapsed": []}
        for name, _notes, _opponent, _repeats in TEST_GROUPS
    }
    lines: list[str] = []

    emit(lines, "# 50-sample local opponent test summary")
    emit(lines)
    emit(lines, f"Planned games: {len(specs)}")
    emit(lines)

    for idx, spec in enumerate(specs, start=1):
        progress = (
            f"[{idx}/{len(specs)}] {spec.label} | "
            f"{'current RED' if spec.current_is_red else 'current BLUE'} | "
            f"trial={spec.trial} | seed={spec.seed}"
        )
        print(progress, flush=True)
        result, elapsed = run_game(spec)
        won = current_agent_won(result, spec.current_is_red)
        row = grouped[spec.label]
        row["games"] = int(row["games"]) + 1
        row["elapsed"].append(elapsed)
        if spec.current_is_red:
            row["red_games"] = int(row["red_games"]) + 1
            row["red_wins"] = int(row["red_wins"]) + int(won)
        else:
            row["blue_games"] = int(row["blue_games"]) + 1
            row["blue_wins"] = int(row["blue_wins"]) + int(won)
        print(f"    result={result}; current_won={won}; elapsed={elapsed:.1f}s", flush=True)

    notes_by_name = {name: notes for name, notes, _opponent, _repeats in TEST_GROUPS}

    emit(lines, "| Test Setting | Games Played | Agent as Red | Agent as Blue | Win Rate | Notes |")
    emit(lines, "|---|---:|---:|---:|---:|---|")
    total_games = 0
    total_wins = 0
    all_elapsed: list[float] = []
    for name, _notes, _opponent, _repeats in TEST_GROUPS:
        row = grouped[name]
        games = int(row["games"])
        red_games = int(row["red_games"])
        blue_games = int(row["blue_games"])
        red_wins = int(row["red_wins"])
        blue_wins = int(row["blue_wins"])
        wins = red_wins + blue_wins
        total_games += games
        total_wins += wins
        win_rate = wins / games * 100 if games else 0.0
        elapsed_values = list(row["elapsed"])
        all_elapsed.extend(elapsed_values)
        avg_elapsed = sum(elapsed_values) / len(elapsed_values)
        emit(
            lines,
            f"| {name} | {games} | {red_wins}/{red_games} | {blue_wins}/{blue_games} | "
            f"{win_rate:.0f}% | {notes_by_name[name]}; average game runtime {avg_elapsed:.1f}s |",
        )

    emit(lines)
    emit(lines, f"Total local opponent games: {total_games}")
    emit(lines, f"Overall local win rate: {total_wins}/{total_games} ({total_wins / total_games * 100:.0f}%)")
    emit(lines, f"Average runtime across all games: {sum(all_elapsed) / len(all_elapsed):.1f}s")

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote summary to {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
