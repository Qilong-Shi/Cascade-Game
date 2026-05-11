# COMP30024 Artificial Intelligence, Semester 1 2026
# Project Part B: Game Playing Agent

import os
from agent.moves import apply_action
from referee.game import PlayerColor, Coord, Direction, \
    Action, PlaceAction, MoveAction, EatAction, CascadeAction

from .minimax import alpha_beta

DEFAULT_DEPTH = 4

class Agent:
    """
    This class is the "entry point" for your agent, providing an interface to
    respond to various Cascade game events.
    """

    def __init__(self, color: PlayerColor, **referee: dict):
        """
        This constructor method runs when the referee instantiates the agent.
        Any setup and/or precomputation should be done here.
        """
        self._color = color
        self._turn_count = 0
        self.board = {}
        self.depth = int(os.environ.get(f"{color.name}_DEPTH", DEFAULT_DEPTH))
        match color:
            case PlayerColor.RED:
                print(f"Testing: I am playing as RED (first player), depth={self.depth}")
            case PlayerColor.BLUE:
                print(f"Testing: I am playing as BLUE, depth={self.depth}")

    def action(self, **referee: dict) -> Action | None:
        """
        This method is called by the referee each time it is the agent's turn
        to take an action. It must always return an action object.
        """

        # Below we have hardcoded actions to be played depending on whether
        # the agent is playing as BLUE or RED. Obviously this won't work beyond
        # the initial moves of the game, so you should use some game playing
        # technique(s) to determine the best action to take.

        # During placement phase (first 8 turns total, 4 per player)
        # if self._turn_count < 4:
        #     match self._color:
        #         case PlayerColor.RED:
        #             print("Testing: RED is playing a PLACE action")
        #             return PlaceAction(Coord(0, self._turn_count))
        #         case PlayerColor.BLUE:
        #             print("Testing: BLUE is playing a PLACE action")
        #             return PlaceAction(Coord(7, self._turn_count))

        # # During play phase
        # match self._color:
        #     case PlayerColor.RED:
        #         print("Testing: RED is playing a MOVE action")
        #         return MoveAction(Coord(0, 0), Direction.Down)
        #     case PlayerColor.BLUE:
        #         print("Testing: BLUE is playing a MOVE action")
        #         return MoveAction(Coord(7, 0), Direction.Up)
        # return minimax(self.board, self.depth, self._color, self._turn_count)[1]
        return alpha_beta(self.board, self.depth, self._color, self._turn_count, float('-inf'), float('inf'))[1]

    def update(self, color: PlayerColor, action: Action, **referee: dict):
        """
        This method is called by the referee after a player has taken their
        turn. You should use it to update the agent's internal game state.
        """
        # if color == self._color:
        #     self._turn_count += 1
        self._turn_count += 1

        # Update board:
        self.board = apply_action(self.board, action, color)

        # Performance evaluaton
        print(f"Color: {color}, Time Remaining: {referee['time_remaining']}s")
        print(f"Color: {color}, Memory Remaining: {referee['space_remaining']}MB")

        # There are four possible action types: PLACE, MOVE, EAT, and CASCADE.
        # Below we check which type of action was played and print out the
        # details of the action for demonstration purposes. You should replace
        # this with your own logic to update your agent's internal game state.
        match action:
            case PlaceAction(coord):
                print(f"Testing: {color} played PLACE action at {coord}")
            case MoveAction(coord, direction):
                print(f"Testing: {color} played MOVE action:")
                print(f"  Coord: {coord}")
                print(f"  Direction: {direction}")
            case EatAction(coord, direction):
                print(f"Testing: {color} played EAT action:")
                print(f"  Coord: {coord}")
                print(f"  Direction: {direction}")
            case CascadeAction(coord, direction):
                print(f"Testing: {color} played CASCADE action:")
                print(f"  Coord: {coord}")
                print(f"  Direction: {direction}")
            case _:
                raise ValueError(f"Unknown action type: {action}")
