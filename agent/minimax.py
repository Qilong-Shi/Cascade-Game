from .moves import apply_action, legal_actions, is_game_over, simple_board_hash, step
from referee.game import (
    PlayerColor,
    Action,
    Coord,
    CellState,
    BOARD_N,
    PLACEMENT_TURNS,
    MAX_TURNS,
    CARDINAL_DIRECTIONS,
)
from collections import defaultdict


WIN_SCORE = 100_000
TURN_LIMIT_WIN_SCORE = 20_000

def push_state(state_counter: defaultdict[int], hsh: tuple) -> None:
    state_counter[hsh] = state_counter.get(hsh, 0) + 1

def pop_state(state_counter: defaultdict[int], hsh: tuple) -> None:
    count = state_counter.get(hsh, 0)
    if count <= 1:
        state_counter.pop(hsh, None)
    else:
        state_counter[hsh] = count - 1

def alpha_beta(state_counter: defaultdict[int], board: dict[Coord, CellState], depth: int, color: PlayerColor, turn_count: int, alpha: float, beta: float) -> tuple[float, Action | None]:
    """
    Return the best action for the current player using the alpha-beta pruning algorithm.
    """
    # Hashing + state_counter only matter for threefold-repetition detection, which
    # is_game_over short-circuits past during placement. Skip the work entirely there.
    hsh = None
    if turn_count >= PLACEMENT_TURNS:
        hsh = simple_board_hash(board, turn_count)
        push_state(state_counter, hsh)


    if depth == 0 or is_game_over(state_counter, board, turn_count, hsh):
        if hsh is not None:
            pop_state(state_counter, hsh)
        return evaluate(state_counter, board, turn_count, hsh), None

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
    
    if hsh is not None:
        pop_state(state_counter, hsh)
    return best_eval, best_action

# Lightweight material-only helper kept for tests / quick diagnostics.
def evaluate_board(board: dict[Coord, CellState]) -> float:
    red_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.RED)                                          
    blue_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.BLUE)
    return red_tokens - blue_tokens

# returns positive if good for red, negative if good for blue
def evaluate(state_counter: defaultdict[int], board: dict[Coord, CellState], turn_count: int, hsh: str | None = None) -> float:
    """
    Heuristic value from RED's perspective.

    The old evaluator mostly measured token difference.  That was enough to
    beat weak play, but it missed the positions that decide Cascade games:
    immediate captures, mobility, whether strength is concentrated in useful
    stacks, and whether material is stranded on the board edge where a cascade
    can remove it cheaply.
    """
    features = board_features(board)
    red = features[PlayerColor.RED]
    blue = features[PlayerColor.BLUE]

    red_tokens = red["tokens"]
    blue_tokens = blue["tokens"]
    material_diff = red_tokens - blue_tokens

    if turn_count >= PLACEMENT_TURNS:
        if blue_tokens == 0:
            return WIN_SCORE - turn_count
        if red_tokens == 0:
            return -WIN_SCORE + turn_count

        play_turn = turn_count - PLACEMENT_TURNS
        if play_turn >= MAX_TURNS:
            if material_diff > 0:
                return TURN_LIMIT_WIN_SCORE + material_diff
            if material_diff < 0:
                return -TURN_LIMIT_WIN_SCORE + material_diff
            return 0

        if hsh is not None and state_counter.get(hsh, 0) >= 3:
            return draw_utility(material_diff)

        if red["mobility"] == 0 or blue["mobility"] == 0:
            return draw_utility(material_diff)

    progress = 0.0
    if turn_count >= PLACEMENT_TURNS:
        progress = min(1.0, (turn_count - PLACEMENT_TURNS) / MAX_TURNS)

    material_weight = 16 + 24 * progress
    center_weight = 5 - 3 * progress
    tactical_weight = 12
    mobility_weight = 0.75
    stack_count_weight = 2.5
    power_weight = 0.6
    edge_weight = 1.5
    initiative_weight = 3
    repetition_weight = 18

    material_score = material_diff * material_weight
    center_score = (red["center_control"] - blue["center_control"]) * center_weight
    tactical_score = (red["capture_value"] - blue["capture_value"]) * tactical_weight
    mobility_score = (red["mobility"] - blue["mobility"]) * mobility_weight
    stack_count_score = (red["stacks"] - blue["stacks"]) * stack_count_weight
    power_score = (red["stack_power"] - blue["stack_power"]) * power_weight
    edge_score = (blue["edge_exposure"] - red["edge_exposure"]) * edge_weight

    side_to_move = PlayerColor.RED if turn_count % 2 == 0 else PlayerColor.BLUE
    initiative_score = red["capture_value"] if side_to_move == PlayerColor.RED else -blue["capture_value"]
    initiative_score *= initiative_weight

    repetition_score = 0
    if hsh is not None:
        repeat_count = state_counter.get(hsh, 0)
        if repeat_count > 1:
            repetition_score = -material_diff * repetition_weight * (repeat_count - 1)

    return (
        material_score
        + center_score
        + tactical_score
        + mobility_score
        + stack_count_score
        + power_score
        + edge_score
        + initiative_score
        + repetition_score
    )


# helper function

def weighting_from_center(coord: Coord) -> float:
    """
    Return a weighting based on distance from the centre of the board, used to break ties during placement phase.
    Returns higher values for coordinates closer to the centre, lower values for coordinates further from the centre.
    """
    center = (3.5, 3.5)
    distance = (abs(coord[0] - center[0]) + abs(coord[1] - center[1]))
    return 1 / (1 + distance)


def board_features(board: dict[Coord, CellState]) -> dict[PlayerColor, dict[str, float]]:
    """
    Extract low-cost tactical / positional features for both players in one pass.

    `capture_value` counts unique immediately capturable enemy tokens, so a
    target threatened by two stacks is not double-counted.  `mobility` mirrors
    the legal move categories without constructing full Action objects, which
    keeps leaf evaluation much cheaper than repeatedly calling `legal_actions`.
    """
    features: dict[PlayerColor, dict[str, float]] = {
        PlayerColor.RED: {
            "tokens": 0,
            "stacks": 0,
            "stack_power": 0,
            "center_control": 0.0,
            "edge_exposure": 0.0,
            "mobility": 0,
            "capture_value": 0,
        },
        PlayerColor.BLUE: {
            "tokens": 0,
            "stacks": 0,
            "stack_power": 0,
            "center_control": 0.0,
            "edge_exposure": 0.0,
            "mobility": 0,
            "capture_value": 0,
        },
    }
    capture_targets: dict[PlayerColor, set[Coord]] = {
        PlayerColor.RED: set(),
        PlayerColor.BLUE: set(),
    }

    for coord, cell in board.items():
        color_features = features[cell.color]
        color_features["tokens"] += cell.height
        color_features["stacks"] += 1
        color_features["stack_power"] += cell.height * cell.height
        color_features["center_control"] += weighting_from_center(coord) * cell.height
        color_features["edge_exposure"] += edge_exposure(coord) * cell.height

        if cell.height > 1:
            color_features["mobility"] += len(CARDINAL_DIRECTIONS)

        for direction in CARDINAL_DIRECTIONS:
            target = step(coord, direction)
            if target is None:
                continue

            target_cell = board.get(target)
            if target_cell is None or target_cell.color == cell.color:
                color_features["mobility"] += 1
            elif cell.height >= target_cell.height:
                color_features["mobility"] += 1
                capture_targets[cell.color].add(target)

    for color, targets in capture_targets.items():
        features[color]["capture_value"] = sum(board[target].height for target in targets)

    return features


def edge_exposure(coord: Coord) -> float:
    """
    Penalise material that is easy to push off the board with a cascade.

    Edge squares are most exposed; squares one step in are still slightly risky.
    Deeper interior squares get no penalty here because center control already
    handles their positional value.
    """
    edge_distance = min(
        coord[0],
        coord[1],
        BOARD_N - 1 - coord[0],
        BOARD_N - 1 - coord[1],
    )
    if edge_distance == 0:
        return 1.0
    if edge_distance == 1:
        return 0.5
    return 0.0


def draw_utility(material_diff: float) -> float:
    """
    Treat a draw as slightly unattractive for the materially leading side.

    The official game result is still a draw, but this search bias prevents the
    agent from cashing out winning positions into repeated shuffles simply
    because the raw utility of the repeated state is 0.
    """
    return -25 if material_diff > 0 else 25 if material_diff < 0 else 0
