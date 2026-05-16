from referee.game import PlayerColor

from agent.program import Agent as CurrentAgent


class Agent(CurrentAgent):
    def __init__(self, color: PlayerColor, **referee: dict):
        super().__init__(color, **referee)
        self.max_depth = 3

    def _choose_placement(self, actions: list[int]) -> int:
        def placement_score(action: int) -> tuple[float, int]:
            row, col = divmod(action, 8)
            distance = abs(row - 3.5) + abs(col - 3.5)
            return (-distance, -action)

        return max(actions, key=placement_score)
