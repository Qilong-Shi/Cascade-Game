from .moves import apply_action, legal_actions, is_game_over, simple_board_hash
from referee.game import PlayerColor, Action, Coord, CellState
from collections import defaultdict

def alpha_beta(state_counter: defaultdict[int], board: dict[Coord, CellState], depth: int, color: PlayerColor, turn_count: int, alpha: float, beta: float) -> tuple[float, Action | None]:
    """
    Return the best action for the current player using the alpha-beta pruning algorithm.
    """
    hsh = simple_board_hash(board, turn_count)
    state_counter[hsh] += 1

    if depth == 0 or is_game_over(state_counter, board, turn_count):
        state_counter[hsh] -= 1 # decrement state counter before returning
        return evaluate_board(board), None

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
