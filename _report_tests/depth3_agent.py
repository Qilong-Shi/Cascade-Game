from referee.game import PlayerColor

from agent.program import Agent as CurrentAgent


class Agent(CurrentAgent):
    def __init__(self, color: PlayerColor, **referee: dict):
        super().__init__(color, **referee)
        self.depth = 3
