import random

from agent.moves import apply_action, legal_actions
from agent.utils import rewrap_action, unwrap_action
from referee.game import Action, PlayerColor


class Agent:
    def __init__(self, color: PlayerColor, **referee: dict):
        self._color = color
        self._turn_count = 0
        self._board = {}
        self._rng = random.Random(30024 + (0 if color == PlayerColor.RED else 1))

    def action(self, **referee: dict) -> Action:
        action = self._rng.choice(legal_actions(self._board, self._color, self._turn_count))
        return rewrap_action(action)

    def update(self, color: PlayerColor, action: Action, **referee: dict):
        action = unwrap_action(action)
        self._turn_count += 1
        self._board = apply_action(self._board, action, color)
