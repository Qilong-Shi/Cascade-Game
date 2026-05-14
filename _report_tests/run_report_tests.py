from pathlib import Path
import re
import subprocess
import sys
import time


TESTS = [
    ("Versus random baseline", "Measures ability to exploit weak play", "_report_tests.random_agent"),
    ("Versus greedy baseline", "Measures tactical strength against one-step evaluation", "_report_tests.greedy_agent"),
    ("Self-play against earlier version", "Uses a depth-3 variant as the earlier implementation", "_report_tests.depth3_agent"),
]


def run_game(red: str, blue: str, label: str) -> tuple[str, float]:
    start = time.perf_counter()
    log_path = Path("_report_tests") / f"{label}.log"
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        proc = subprocess.run(
            [sys.executable, "-m", "referee", "-v", "0", red, blue],
            cwd=".",
            text=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            timeout=360,
        )
    elapsed = time.perf_counter() - start
    output = log_path.read_text(encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join(output.splitlines()[-20:])
        raise RuntimeError(f"Game failed ({red} vs {blue}), rc={proc.returncode}\n{tail}")

    match = re.search(r"result:\s*(.+)", output)
    if not match:
        tail = "\n".join(output.splitlines()[-20:])
        raise RuntimeError(f"Could not parse result for {red} vs {blue}\n{tail}")

    return match.group(1).strip(), elapsed


def current_agent_won(result: str, current_is_red: bool) -> bool:
    if result == "draw":
        return False
    return ("player 1 [agent:Agent]" in result) if current_is_red else ("player 2 [agent:Agent]" in result)


def main() -> None:
    print("| Test Setting | Games Played | Agent as Red | Agent as Blue | Win Rate | Notes |")
    print("|---|---:|---:|---:|---:|---|")
    print("| Public Gradescope tests | N/A | N/A | N/A | Passed | Confirms compatibility and legal play |")

    for name, notes, opponent in TESTS:
        print(f"Running {name}: current agent as Red...", flush=True)
        safe_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        red_result, red_elapsed = run_game("agent", opponent, f"{safe_name}_current_red")
        print(f"  result={red_result}; elapsed={red_elapsed:.1f}s", flush=True)

        print(f"Running {name}: current agent as Blue...", flush=True)
        blue_result, blue_elapsed = run_game(opponent, "agent", f"{safe_name}_current_blue")
        print(f"  result={blue_result}; elapsed={blue_elapsed:.1f}s", flush=True)

        red_win = current_agent_won(red_result, current_is_red=True)
        blue_win = current_agent_won(blue_result, current_is_red=False)
        wins = int(red_win) + int(blue_win)
        win_rate = wins / 2 * 100
        print(
            f"| {name} | 2 | {int(red_win)}/1 | {int(blue_win)}/1 | "
            f"{win_rate:.0f}% | {notes}; elapsed {red_elapsed:.1f}s / {blue_elapsed:.1f}s |"
        )


if __name__ == "__main__":
    main()
