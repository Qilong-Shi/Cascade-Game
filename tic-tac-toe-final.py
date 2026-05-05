"""
Implementation of the game of tic-tac-toe with a human player and some
computer players utilising different strategies. 

While best efforts have been made to ensure correctness, there is always 
a chance of bugs being present -- we welcome any corrections.
"""

import math as Math
import random
from typing import Literal, Tuple

DEBUG = True # Set to False to disable debug output

BOARD_N = 3 # Dimension of the board

ROWS = [
    ((0, 0), (0, 1), (0, 2)),
    ((1, 0), (1, 1), (1, 2)),
    ((2, 0), (2, 1), (2, 2))
]

COLUMNS = [
    ((0, 0), (1, 0), (2, 0)),
    ((0, 1), (1, 1), (2, 1)),
    ((0, 2), (1, 2), (2, 2))
]

DIAGONALS = [
    ((0, 0), (1, 1), (2, 2)),
    ((0, 2), (1, 1), (2, 0))
]

LINES = ROWS + COLUMNS + DIAGONALS

# Player constants. For convenience in the implementation of Minimax, we use 1
# for PLAYER_X and -1 for PLAYER_O.
PLAYER_X = 1
PLAYER_O = -1

# Mapping of player constants to their names.
PLAYER_NAME = {
    PLAYER_X: "X",
    PLAYER_O: "O"
}

# Type aliases for better readability.
Player = Literal[1] | Literal[-1]
MaybePlayer = Player | Literal[0]
Coord = Tuple[int, int]


class Board:
    """
    Represents the state of the board in a game of tic-tac-toe.
    """
    def __init__(self):
        self._board: dict[Coord, MaybePlayer] = {
            (r, c): 0 for r in range(BOARD_N) for c in range(BOARD_N)
        }
        self._actions = []

    def __getitem__(self, key: Coord) -> MaybePlayer:
        """
        Returns the value of the cell at the given coordinates. By using
        __getitem__, we can access the cell using the syntax `board[(r, c)]`.
        """
        return self._board[key]

    def __str__(self) -> str:
        """
        Returns a string "visualisation" of the board which can be printed.
        """
        return " " + " \n---|---|---\n ".join(
            " | ".join(
                {
                    PLAYER_X: "X",
                    PLAYER_O: "O",
                    0: " ",
                }[self[(i, j)]] for j in range(BOARD_N)
            ) for i in range(BOARD_N)
        )

    @property
    def curr_player(self) -> Player:
        """
        The current player whose turn it is to play.
        """
        return PLAYER_X if len(self._actions) % 2 == 0 else PLAYER_O

    def _is_cell_empty(self, coord: Coord) -> bool:
        return self[coord] == 0

    def _is_full(self) -> bool:
        return all(not self._is_cell_empty(coord) for coord in self._board)

    def is_game_over(self) -> bool:
        """
        Returns True if the game is over, i.e., the board is full (in which
        case it is a draw) or there is a winner.
        """
        return self._is_full() or self.get_winner() != 0
    
    def get_winner(self) -> MaybePlayer:
        """
        Returns the winner of the game, if there is one. Otherwise, returns 0.
        """
        for line in LINES:
            line_sum = sum(self[coord] for coord in line)
            if abs(line_sum) == len(line):
                return PLAYER_X if line_sum > 0 else PLAYER_O
        return 0

    def apply_action(self, coord: Coord) -> None:
        """
        Applies the action to the board. The action is a tuple of the form
        (row, column) where 0 <= row < 3 and 0 <= column < 3.
        """
        if self.is_game_over():
            raise ValueError("Game is over")
        
        if not self._is_cell_empty(coord):
            raise ValueError("Cell is not empty")
        
        self._board[coord] = self.curr_player
        self._actions.append(coord)

    def undo_action(self) -> None:
        """
        Undoes the last action applied to the board.
        """
        if not self._actions:
            raise ValueError("No actions to undo")
        
        coord = self._actions.pop()
        self._board[coord] = 0

    def get_legal_actions(self) -> list[Coord]:
        """
        Returns a list of legal actions. In the case of tic-tac-toe, these are
        simply the coordinates of the empty cells on the board.
        """
        return [coord for coord in self._board if self._is_cell_empty(coord)]
    

class Game:
    def __init__(self, agent_X, agent_O):
        """
        Initialises the game with the two agents that will play against each
        other. Importantly, the parameters are classes, not instances of the 
        agents -- the actual instances are created below.
        
        Both classes must be subclasses of AbstractAgent, that is, they must 
        implement the get_action method. The agents are initialised with the 
        player they represent.
        """
        print("Initialising game...")
        self.board = Board()

        player_X_agent = agent_X(PLAYER_X)
        print(f"Player X: {player_X_agent.__class__.__name__}")

        player_O_agent = agent_O(PLAYER_O)
        print(f"Player O: {player_O_agent.__class__.__name__}")

        self.agents: dict[Player, AbstractAgent] = {
            PLAYER_X: player_X_agent,
            PLAYER_O: player_O_agent
        }
        print()
        
    def play(self) -> MaybePlayer:
        """
        Plays the game until it is over and returns the winner.
        """
        print("Initial board:")
        print(f"\n{self.board}\n")

        while not self.board.is_game_over():
            agent = self.agents[self.board.curr_player]
            action = agent.get_action(self.board)
            self.board.apply_action(action)

            print(f"Player {PLAYER_NAME[-self.board.curr_player]} moves:")
            print(f"\n{self.board}\n")
        
        return self.board.get_winner()


class AbstractAgent:
    def __init__(self, player: Player):
        """
        An agent must be initialised with the player it represents.
        Only two players are allowed: PLAYER_X and PLAYER_O.
        """
        self.player = player
        
    def get_action(self, board: Board) -> Coord:
        """
        An agent must implement this method to return the next action.
        Implementation details are up to the agent, based on the strategy
        it employs.
        """
        raise NotImplementedError
    

class HumanAgent(AbstractAgent):
    def get_action(self, board: Board) -> Coord:
        """
        Prompts the user to enter the row and column of the cell they want to
        place their mark in. This allows a human player to play the game.
        """
        while True:
            try:
                input_ln = input("Enter row/column (space separated): ")
                row, col = map(int, input_ln.split())

                if board[(row, col)] == 0:
                    return row, col
                else:
                    print("Cell is not empty")
            except Exception as e:
                print(f"Error: {e}")
                continue


class RandomAgent(AbstractAgent):
    def get_action(self, board: Board) -> Coord:
        """
        Chooses a random legal action. Useful for testing purposes.
        """
        return random.choice(board.get_legal_actions())


class MinimaxAgent(AbstractAgent):
    def __init__(self, player: Player = PLAYER_X):
        self.player = player
        self._is_max = True if player == PLAYER_X else False

        # The following attributes are used for debugging purposes.
        self._num_nodes = 0
        self._num_terminal_nodes = 0

    def get_action(self, board: Board) -> Coord:
        """
        Chooses the best action for the current player using the Minimax
        algorithm (without alpha-beta pruning).
        """
        if DEBUG:
            print(" DEBUG ".center(40, "="))
            print(f"Player: {PLAYER_NAME[self.player]}" +
                    f"{' (MAX)' if self._is_max else ' (MIN)'}\n")

            self._num_nodes = 0
            self._num_terminal_nodes = 0
        
        value: dict[Coord, float] = {}

        for action in board.get_legal_actions():
            board.apply_action(action)
            value[action] = self._minimax(board)
            board.undo_action()
            if DEBUG:
                print(f"Try action: {action}")
                print(f"Value: {value[action]}")
                print()

        if self._is_max:
            best_action, best_value = max(value.items(), key=lambda x: x[1])
        else:
            best_action, best_value = min(value.items(), key=lambda x: x[1])
        
        if DEBUG:
            print(f"Chosen action: {best_action} (value: {best_value})")
            print()
            print(f"Number of nodes: {self._num_nodes}")
            print(f"Number of terminal nodes: {self._num_terminal_nodes}")
            print("=" * 40)
            print()

        return best_action

    def _minimax(
        self, 
        board: Board
    ) -> float:
        """
        Returns the minimax value of the current board state. 
        """
        self._num_nodes += 1
        if board.is_game_over():
            self._num_terminal_nodes += 1
            return board.get_winner()
        
        elif board.curr_player == PLAYER_X:
            highest = -Math.inf
            for action in board.get_legal_actions():
                board.apply_action(action)
                value = self._minimax(board)
                board.undo_action()
                highest = max(highest, value)
            return highest
        
        else:
            lowest = Math.inf
            for action in board.get_legal_actions():
                board.apply_action(action)
                value = self._minimax(board)
                board.undo_action()
                lowest = min(lowest, value)
            return lowest


def main():
    """
    Main entry point of the program.
    """
    agent_X = MinimaxAgent
    agent_O = RandomAgent
    game = Game(agent_X, agent_O)
    winner = game.play()
    if winner:
        print(f"Player {PLAYER_NAME[winner]} wins!")
    else:
        print("It's a draw!")


if __name__ == "__main__":
    main()
