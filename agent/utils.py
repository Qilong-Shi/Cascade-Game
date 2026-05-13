from referee.game import (
    Action,
    CascadeAction,
    EatAction,
    MoveAction,
    PlayerColor,
    PlaceAction,
    CellState,
    Direction,
    Coord
)

def rewrap_action(action: Action) -> Action:
    """
    Rewrap an action to ensure it is in the correct format for the rest of the codebase.
    This is necessary because the action received from the referee may be in a different format than what our code expects.
    """
    coord = Coord(action.coord[0], action.coord[1])
    if isinstance(action, PlaceAction):
        return PlaceAction(coord)
    elif isinstance(action, MoveAction):
        return MoveAction(coord, direction=action.direction)
    elif isinstance(action, EatAction):
        return EatAction(coord, direction=action.direction)
    elif isinstance(action, CascadeAction):
        return CascadeAction(coord, direction=action.direction)
    else:
        raise ValueError(f"Unknown action type: {type(action)}")

def unwrap_action(action: Action) -> Action:
    """
    Unwrap an action to ensure it is in the correct format for the referee.
    This is necessary because the action we generate may be in a different format than what the referee expects.
    """
    if isinstance(action, PlaceAction):
        return PlaceAction((action.coord.r, action.coord.c))
    elif isinstance(action, MoveAction):
        return MoveAction((action.coord.r, action.coord.c), direction=action.direction)
    elif isinstance(action, EatAction):
        return EatAction((action.coord.r, action.coord.c), direction=action.direction)
    elif isinstance(action, CascadeAction):
        return CascadeAction((action.coord.r, action.coord.c), direction=action.direction)
    else:
        raise ValueError(f"Unknown action type: {type(action)}")