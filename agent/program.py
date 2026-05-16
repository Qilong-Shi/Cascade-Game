# COMP30024 Artificial Intelligence, Semester 1 2026
# Project Part B: Game Playing Agent

from __future__ import annotations

import os
import time
from collections import defaultdict

from referee.game import Action, PLACEMENT_TURNS, PlayerColor

from .minimax import iterative_deepening_search
from .search_state import (
    SearchState,
    decode_referee_action,
    encode_referee_action,
)


DEFAULT_MAX_DEPTH = 8
DEFAULT_MOVE_BUDGET_SECONDS = 0.08


class Agent:
    """
    Referee-facing agent wrapper around the packed mutable search engine.
    """

    def __init__(self, color: PlayerColor, **_referee: dict):
        self._color = color
        self.state = SearchState.empty()
        self.repetition_counts: defaultdict[int, int] = defaultdict(int)
        self.max_depth = int(os.environ.get(f"{color.name}_DEPTH", os.environ.get("AGENT_MAX_DEPTH", DEFAULT_MAX_DEPTH)))
        self.default_move_budget = float(os.environ.get("AGENT_MOVE_BUDGET", DEFAULT_MOVE_BUDGET_SECONDS))
        self.debug = os.environ.get("AGENT_DEBUG") == "1"
        self._debug(
            f"Playing as {color.name}, max_depth={self.max_depth}, "
            f"default_move_budget={self.default_move_budget:.2f}s"
        )

    def action(self, **_referee: dict) -> Action | None:
        actions = self.state.generate_actions()
        if not actions:
            return None

        if self.state.turn_count < PLACEMENT_TURNS:
            return decode_referee_action(self._choose_placement(actions))

        move_budget = self._move_budget(_referee.get("time_remaining"))
        deadline = time.perf_counter() + move_budget
        value, best_action, stats = iterative_deepening_search(
            self.state,
            self.repetition_counts,
            self._color,
            self.max_depth,
            deadline,
        )
        if best_action is None:
            best_action = actions[0]

        self._debug(
            f"search value={value:.1f}, depth={stats.completed_depth}, nodes={stats.nodes}, "
            f"cutoffs={stats.cutoffs}, tt_hits={stats.tt_hits}, move_budget={move_budget:.3f}s"
        )
        return decode_referee_action(best_action)

    def update(self, color: PlayerColor, action: Action, **_referee: dict) -> None:
        encoded = encode_referee_action(action)
        if self.state.side_to_move != color.value:
            self._debug(
                f"state side mismatch before update: expected {self.state.side_to_move}, got {color.value}"
            )
        self.state.make_move(encoded)
        if self.state.play_phase:
            self.repetition_counts[self.state.hash_key] += 1

    def _choose_placement(self, actions: list[int]) -> int:
        def placement_score(action: int) -> tuple[float, int]:
            row, col = divmod(action, 8)
            distance = abs(row - 3.5) + abs(col - 3.5)
            tie_break = -action if self._color == PlayerColor.RED else action
            return (-distance, tie_break)

        return max(actions, key=placement_score)

    def _move_budget(self, time_remaining: float | None) -> float:
        if time_remaining is None:
            return self.default_move_budget
        if time_remaining <= 2:
            return 0.02
        if time_remaining <= 10:
            return min(self.default_move_budget, 0.08)
        if time_remaining <= 30:
            return min(self.default_move_budget, 0.20)
        return min(self.default_move_budget, max(0.05, time_remaining / 240))

    def _debug(self, message: str) -> None:
        if self.debug:
            print(message)
