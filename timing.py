"""
perf_counter-based timing for full referee-run games.

Usage:
    from timing import timeit, timed, set_label

    # Decorate functions:
    @timeit
    def legal_actions(...): ...

    # Or time arbitrary blocks:
    def alpha_beta(...):
        with timed("alpha_beta:loop"):
            for action in legal_actions(...): ...

    # In Agent.__init__, label this subprocess's summary by color:
    set_label(color.name)

Run normally:
    python -m referee agent agent

After each agent subprocess exits gracefully, a summary prints to stderr.

Caveats:
- Agent subprocesses SIGKILL'd by the referee on time/space limit violation
  do NOT fire atexit, so you lose the summary for that agent.
- Two summaries print, one per agent subprocess; set_label() distinguishes them.
- Output goes to stderr (which the referee forwards to your terminal by default).
"""

import atexit
import os
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps

_totals: dict[str, float] = defaultdict(float)
_counts: dict[str, int] = defaultdict(int)
_label: str = f"pid={os.getpid()}"


def set_label(name: str) -> None:
    global _label
    _label = name


@contextmanager
def timed(name: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        _totals[name] += time.perf_counter() - t0
        _counts[name] += 1


def timeit(func):
    name = func.__qualname__

    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            _totals[name] += time.perf_counter() - t0
            _counts[name] += 1

    return wrapper


def _report() -> None:
    if not _totals:
        return
    rows = sorted(_totals.items(), key=lambda kv: -kv[1])
    name_w = max(len(n) for n, _ in rows)
    name_w = max(name_w, len("Name"))
    bar_w = name_w + 38
    bar = "=" * bar_w

    print(bar, file=sys.stderr)
    print(f"Timing summary [{_label}]", file=sys.stderr)
    print(bar, file=sys.stderr)
    print(
        f"  {'Name'.ljust(name_w)}  {'Total':>10s}  {'Calls':>8s}  {'Per call':>12s}",
        file=sys.stderr,
    )
    print(
        f"  {'-' * name_w}  {'-' * 10}  {'-' * 8}  {'-' * 12}",
        file=sys.stderr,
    )
    for name, total in rows:
        n = _counts[name]
        per_call_ms = total / n * 1000 if n else 0
        print(
            f"  {name.ljust(name_w)}  {total:>9.4f}s  {n:>8d}  {per_call_ms:>9.3f}ms",
            file=sys.stderr,
        )
    print(bar, file=sys.stderr)
    sys.stderr.flush()


atexit.register(_report)
