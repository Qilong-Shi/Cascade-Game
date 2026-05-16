from collections import defaultdict

from agent.minimax import evaluate
from agent.moves import apply_action, legal_actions
from agent.utils import rewrap_action, unwrap_action
from referee.game import Action, PlayerColor


class Agent:
    def __init__(self, color: PlayerColor, **referee: dict):
        self._color = color
        self._turn_count = 0
        self._board = {}

    def action(self, **referee: dict) -> Action:
        actions = legal_actions(self._board, self._color, self._turn_count)
        scored = []
        for action in actions:
            board = apply_action(self._board, action, self._color)
            score = evaluate(defaultdict(int), board, self._turn_count + 1, self._color)
            scored.append((score, action))

        best_action = max(scored, key=lambda item: item[0])[1]

        return rewrap_action(best_action)

    def update(self, color: PlayerColor, action: Action, **referee: dict):
        action = unwrap_action(action)
        self._turn_count += 1
        self._board = apply_action(self._board, action, color)
