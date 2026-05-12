from .moves import apply_action, legal_actions, is_game_over, simple_board_hash
from referee.game import PlayerColor, Action, Coord, CellState
from collections import defaultdict
import numpy as np

def alpha_beta(state_counter: defaultdict[int], board: dict[Coord, CellState], depth: int, color: PlayerColor, turn_count: int, alpha: float, beta: float) -> tuple[float, Action | None]:
    """
    Return the best action for the current player using the alpha-beta pruning algorithm.
    """
    hsh = simple_board_hash(board, turn_count)
    state_counter[hsh] += 1

    if depth == 0 or is_game_over(state_counter, board, turn_count):
        state_counter[hsh] -= 1 # decrement state counter before returning
        return evaluate(state_counter, board, turn_count), None

    best_action = None # allows for single return call
    best_eval = None

    if color == PlayerColor.RED:
        max_eval = float('-inf')
        for action in legal_actions(board, color, turn_count):
            new_board = apply_action(board, action, color)
            value, _ = alpha_beta(state_counter, new_board, depth - 1, PlayerColor.BLUE, turn_count + 1, alpha, beta)
            if value > max_eval:
                max_eval = value
                best_action = action
            alpha = max(alpha, value)
            if beta <= alpha:
                break
        best_eval = max_eval

    else:
        min_eval = float('inf')
        for action in legal_actions(board, color, turn_count):
            new_board = apply_action(board, action, color)
            value, _ = alpha_beta(state_counter, new_board, depth - 1, PlayerColor.RED, turn_count + 1, alpha, beta)
            if value < min_eval:
                min_eval = value
                best_action = action
            beta = min(beta, value)
            if beta <= alpha:
                break
        best_eval = min_eval
    
    state_counter[hsh] -= 1 # decrement state counter before returning
    return best_eval, best_action


# very simple evaluation function, just return difference in number of tokens
def evaluate_board(board: dict[Coord, CellState]) -> float:
    red_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.RED)                                          
    blue_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.BLUE)
    return red_tokens - blue_tokens

# returns positive if good for red, negative if good for blue
def evaluate(state_counter: defaultdict[int], board: dict[Coord, CellState], turn_count: int) -> float:

    eval_score = 0

    center_score = 0
    tie_score = 0
    diff_score = 0
    win_score = 0

    turn_limit_score = 0
    CENTER_WEIGHT = 10
    TIE_WEIGHT = 5

    for coord, cell in board.items():
        if cell.is_empty:
            continue
        color_mult = 1 if cell.color == PlayerColor.RED else -1
        center_score += color_mult * weighting_from_center(coord) * CENTER_WEIGHT
    center_score *= 1/300 * (turn_count - 8) + 1 # dropoff function


    if turn_count >= 8: # only evaluate win conditions during play phase
        red_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.RED)
        blue_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.BLUE)
        diff_score = red_tokens - blue_tokens
        if blue_tokens == 0: # winning is best, even better if it wins faster
            win_score = 1000 - turn_count # arbitrary large value to represent a win
        if red_tokens == 0: # losing is worst, even worse if it loses faster
            win_score = -1000 + turn_count # arbitrary large negative value to represent a loss

        hsh = simple_board_hash(board, turn_count)
        state_counter[hsh] += 1 # decrement state counter to check for win conditions without counting current state
        if is_game_over(state_counter, board, turn_count) and (red_tokens and blue_tokens): # if game finishes from draw
            tie_score = -TIE_WEIGHT # bad for red, since red wants to win as it has a starting advantage
            if red_tokens > blue_tokens: # even worse for red since it is winning, it does not want to draw
                tie_score -= TIE_WEIGHT
            else:
                tie_score *= -1 # good for red since it is losing, it wants to draw, makes tie_score positive

        state_counter[hsh] -= 1 # restore state counter

        # reward turn limit wins since they are the same

        turn_limit_score = diff_score * 1/(1+np.exp(-0.05*(turn_count-100))) * 100


    eval_score = center_score + tie_score + diff_score + turn_limit_score + win_score
    return eval_score


# helper function

def weighting_from_center(coord1: Coord) -> float:
    """
    Return a weighting based on distance from the centre of the board, used to break ties during placement phase.
    Returns higher values for coordinates closer to the centre, lower values for coordinates further from the centre.
    """
    center = (3.5, 3.5)
    distance = (abs(coord1.r - center[0]) + abs(coord1.c - center[1]))
    return 1 / (1 + distance)