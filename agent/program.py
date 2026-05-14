# COMP30024 Artificial Intelligence, Semester 1 2026
# Project Part B: Game Playing Agent

import os
from .moves import apply_action, legal_actions, simple_board_hash
from referee.game import PlayerColor, Action, PLACEMENT_TURNS

from collections import defaultdict
from .minimax import alpha_beta
from .utils import rewrap_action, unwrap_action

DEFAULT_DEPTH = 3

class Agent:
    """
    This class is the "entry point" for your agent, providing an interface to
    respond to various Cascade game events.
    """

    def __init__(self, color: PlayerColor, **_referee: dict):
        """
        This constructor method runs when the referee instantiates the agent.
        Any setup and/or precomputation should be done here.
        """
        self._color = color
        self._turn_count = 0
        self.board = {}
        self.state_counter = defaultdict(int)

        # Use the environment override only as a maximum. The agent still caps
        # search dynamically so it can return before Gradescope timeouts.
        self.depth = int(os.environ.get(f"{color.name}_DEPTH", DEFAULT_DEPTH))
        self.debug = os.environ.get("AGENT_DEBUG") == "1"
        self._debug(f"Playing as {color.name}, max_depth={self.depth}")

    def action(self, **_referee: dict) -> Action | None:
        """
        This method is called by the referee each time it is the agent's turn
        to take an action. It must always return an action object.
        """
        actions = legal_actions(self.board, self._color, self._turn_count)
        if not actions:
            return None

        if self._turn_count < PLACEMENT_TURNS:
            best_action = self._choose_placement(actions)
            return rewrap_action(best_action)

        depth = self._effective_depth(len(actions), _referee.get("time_remaining"))
        best_action = alpha_beta(
            self.state_counter,
            self.board,
            depth,
            self._color,
            self._turn_count,
            float('-inf'),
            float('inf')
        )[1]
        if best_action is None:
            best_action = actions[0]
        return rewrap_action(best_action)

    def update(self, color: PlayerColor, action: Action, **referee: dict):
        """
        This method is called by the referee after a player has taken their
        turn. You should use it to update the agent's internal game state.
        """
        action = unwrap_action(action)

        # Store current board state
        self.state_counter[simple_board_hash(self.board, self._turn_count)] += 1

        # Increment turn count
        self._turn_count += 1

        # Update board:
        self.board = apply_action(self.board, action, color)

        if self.debug:
            self._debug(
                f"{color.name} played {type(action).__name__}; "
                f"time={referee.get('time_remaining')}s; "
                f"memory={referee.get('space_remaining')}MB"
            )

    def _choose_placement(self, actions: list[Action]) -> Action:
        """
        Pick a legal placement quickly. Searching the full placement tree has
        very high branching and was the source of timeout failures.
        """
        def placement_score(action: Action) -> tuple[float, int, int]:
            coord = action.coord
            row = coord[0]
            col = coord[1]
            distance = abs(row - 3.5) + abs(col - 3.5)
            return (-distance, row, col)

        return max(actions, key=placement_score)

    def _effective_depth(self, action_count: int, time_remaining: float | None) -> int:
        depth = max(1, self.depth)

        if action_count > 24:
            depth = min(depth, 2)
        elif action_count > 12:
            depth = min(depth, 3)

        if time_remaining is not None:
            if time_remaining < 10:
                depth = 1
            elif time_remaining < 40:
                depth = min(depth, 2)

        return depth

    def _debug(self, message: str) -> None:
        if self.debug:
            print(message)
