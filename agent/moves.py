from referee.game import (
    Action,
    BOARD_N,
    CARDINAL_DIRECTIONS,
    CascadeAction,
    CellState,
    Coord,
    Direction,
    EatAction,
    MoveAction,
    PlayerColor,
    PLACEMENT_TURNS,
    MAX_TURNS,
    PlaceAction
)

def legal_actions(board: dict[Coord, CellState], color: PlayerColor, turn_count: int) -> list[Action]:
    """
    Generate all legal actions for any coloured stacks.
    """
    actions: list[Action] = []

    # During placement phase, can only place on empty cells
    if turn_count < PLACEMENT_TURNS:
        # Generate list of all empty coordinates
        legal_coords = []
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                coord = Coord(r, c)
                if board.get(coord, CellState()).is_empty:
                    legal_coords.append(coord)

        # append place action for each legal coordinate
        for coord in legal_coords:
            actions.append(PlaceAction(coord))
    
    else:
        for coord, cell in board.items():
            if cell.color != color:
                continue

            for direction in CARDINAL_DIRECTIONS:
                if cell.height > 1:
                    actions.append(CascadeAction(coord, direction))

                target = step(coord, direction)
                if target is None:
                    continue

                target_cell = board.get(target, CellState())

                if target_cell.is_empty or target_cell.color == cell.color:
                    actions.append(MoveAction(coord, direction))

                if (
                    not target_cell.is_empty
                    and target_cell.color != cell.color
                    and cell.height >= target_cell.height
                ):
                    actions.append(EatAction(coord, direction))

    return actions

def step(coord: Coord, direction: Direction) -> Coord | None:
    """
    Return next coordinate in bounds, otherwise None.
    """
    new_r = coord.r + direction.r
    new_c = coord.c + direction.c
    if 0 <= new_r < BOARD_N and 0 <= new_c < BOARD_N:
        return Coord(new_r, new_c)
    return None


def apply_move(board: dict[Coord, CellState], action: MoveAction) -> dict[Coord, CellState]:
    """
    return new board of the move action applied on the cell
    """
    new_board = board.copy()

    source_coord = action.coord
    source_state = board[source_coord]
    target_coord = step(source_coord, action.direction)
    if target_coord is None:
        raise ValueError(f"MoveAction direction out of bounds from {source_coord}")
    target_state = board.get(target_coord, CellState())

    if target_state.is_empty:
        new_board[target_coord] = source_state
        del new_board[source_coord]
    elif target_state.color == source_state.color:
        new_board[target_coord] = CellState(
            source_state.color, target_state.height + source_state.height
        )
        del new_board[source_coord]
    else:
        raise ValueError(f"Cannot move to enemy-occupied cell at {target_coord}")

    return new_board


def apply_eat(board: dict[Coord, CellState], action: EatAction) -> dict[Coord, CellState]:
    """
    return new board of the eat action applied on the cell
    """
    new_board = board.copy()

    source_coord = action.coord
    source_state = board[source_coord]
    target_coord = step(source_coord, action.direction)
    if target_coord is None:
        raise ValueError(f"EatAction direction out of bounds from {source_coord}")

    new_board[target_coord] = source_state
    del new_board[source_coord]

    return new_board


def apply_cascade(board: dict[Coord, CellState], action: CascadeAction
) -> dict[Coord, CellState]:
    """
    Return new board with cascade action applied.
    """
    new_board = board.copy()

    source_coord = action.coord
    source_state = board[source_coord]
    direction = action.direction
    height = source_state.height

    del new_board[source_coord]

    def push_stack(coord: Coord) -> None:
        """
        Push a stack one step in the cascade direction.
        Stacks pushed out of bounds are eliminated.
        """
        current_state = new_board.get(coord, CellState())
        if current_state.is_empty:
            return

        next_coord = step(coord, direction)
        if next_coord is None:
            del new_board[coord]
            return

        if new_board.get(next_coord, CellState()).is_stack:
            push_stack(next_coord)

        new_board[next_coord] = current_state
        del new_board[coord]

    def drop_token(target_coord: Coord | None, color: PlayerColor) -> None:
        """
        Drop one token of given color at target.
        If occupied, push the stack first.
        """
        if target_coord is None:
            return

        target_state = new_board.get(target_coord, CellState())
        if target_state.is_empty:
            new_board[target_coord] = CellState(color, 1)
        else:
            push_stack(target_coord)
            new_board[target_coord] = CellState(color, 1)

    current = source_coord
    for _ in range(height):
        next_coord = step(current, direction)
        if next_coord is None:
            break
        drop_token(next_coord, source_state.color)
        current = next_coord

    return new_board


def apply_action(board: dict[Coord, CellState], action: Action) -> dict[Coord, CellState]:
    if isinstance(action, MoveAction):
        return apply_move(board, action)
    if isinstance(action, EatAction):
        return apply_eat(board, action)
    if isinstance(action, CascadeAction):
        return apply_cascade(board, action)
    raise ValueError("Unknown action type")


def is_game_over(board: dict[Coord, CellState], turn_count: int, color: PlayerColor) -> bool:
    # No win conditions during placement phase
    if turn_count < PLACEMENT_TURNS:                                                                                                   
        return False                                      
                                                                                                                                        
    # Elimination
    red_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.RED)                                          
    blue_tokens = sum(cell.height for cell in board.values() if cell.color == PlayerColor.BLUE)
    if red_tokens == 0 or blue_tokens == 0:                                                                                            
        return True
                                                                                                                                        
    # Turn limit                                          
    if (turn_count - PLACEMENT_TURNS) >= MAX_TURNS:
        return True                                                                                                                    

    # Stalemate                                                                                                                        
    if not legal_actions(board, color, turn_count):       
        return True

    return False 