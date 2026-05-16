from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from referee.game import (
    BOARD_N,
    INITIAL_STACK_HEIGHT,
    PLACEMENT_TURNS,
    Action,
    CascadeAction,
    CellState,
    Coord,
    Direction,
    EatAction,
    MoveAction,
    PlaceAction,
    PlayerColor,
)


BOARD_CELLS = BOARD_N * BOARD_N

RED = PlayerColor.RED.value
BLUE = PlayerColor.BLUE.value
EMPTY = -1

PLACE = 0
MOVE = 1
EAT = 2
CASCADE = 3

MOVE_BASE = 64
EAT_BASE = 320
CASCADE_BASE = 576

DIRECTIONS = (
    Direction.Up,
    Direction.Down,
    Direction.Left,
    Direction.Right,
)
DIR_DELTAS = tuple((direction.r, direction.c) for direction in DIRECTIONS)
DIR_TO_INDEX = {direction: idx for idx, direction in enumerate(DIRECTIONS)}


def _build_next_index() -> tuple[tuple[int, int, int, int], ...]:
    rows: list[tuple[int, int, int, int]] = []
    for idx in range(BOARD_CELLS):
        row, col = divmod(idx, BOARD_N)
        next_cells = []
        for dr, dc in DIR_DELTAS:
            nr = row + dr
            nc = col + dc
            next_cells.append(nr * BOARD_N + nc if 0 <= nr < BOARD_N and 0 <= nc < BOARD_N else -1)
        rows.append(tuple(next_cells))  # type: ignore[arg-type]
    return tuple(rows)


NEXT_INDEX = _build_next_index()
NEIGHBOR_MASKS = tuple(
    sum(1 << nxt for nxt in NEXT_INDEX[idx] if nxt != -1)
    for idx in range(BOARD_CELLS)
)
CENTER_WEIGHTS = tuple(
    1 / (1 + abs(row - 3.5) + abs(col - 3.5))
    for row in range(BOARD_N)
    for col in range(BOARD_N)
)
EDGE_WEIGHTS = tuple(
    1.0
    if min(row, col, BOARD_N - 1 - row, BOARD_N - 1 - col) == 0
    else 0.5
    if min(row, col, BOARD_N - 1 - row, BOARD_N - 1 - col) == 1
    else 0.0
    for row in range(BOARD_N)
    for col in range(BOARD_N)
)


def _mix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return value ^ (value >> 31)


MAX_STACK_HEIGHT = 12
ZOBRIST = tuple(
    tuple(
        tuple(_mix64((idx + 1) * 131 + color * 17 + height * 977) for height in range(MAX_STACK_HEIGHT + 1))
        for color in (RED, BLUE)
    )
    for idx in range(BOARD_CELLS)
)
SIDE_TO_MOVE_HASH = _mix64(0xC0DEC0DE)


@dataclass(slots=True)
class UndoRecord:
    red_bits: int
    blue_bits: int
    red_tokens: int
    blue_tokens: int
    turn_count: int
    side_to_move: int
    hash_key: int
    changes: tuple[tuple[int, int, int], ...]


class SearchState:
    __slots__ = (
        "red_bits",
        "blue_bits",
        "heights",
        "red_tokens",
        "blue_tokens",
        "turn_count",
        "side_to_move",
        "hash_key",
    )

    def __init__(
        self,
        red_bits: int = 0,
        blue_bits: int = 0,
        heights: list[int] | None = None,
        red_tokens: int = 0,
        blue_tokens: int = 0,
        turn_count: int = 0,
        side_to_move: int = RED,
        hash_key: int = 0,
    ) -> None:
        self.red_bits = red_bits
        self.blue_bits = blue_bits
        self.heights = heights if heights is not None else [0] * BOARD_CELLS
        self.red_tokens = red_tokens
        self.blue_tokens = blue_tokens
        self.turn_count = turn_count
        self.side_to_move = side_to_move
        self.hash_key = hash_key

    @classmethod
    def empty(cls) -> "SearchState":
        return cls()

    @classmethod
    def from_sparse(
        cls,
        board: dict[Coord | tuple[int, int], CellState],
        turn_count: int,
        side_to_move: PlayerColor | int | None = None,
    ) -> "SearchState":
        side = turn_count & 1 if side_to_move is None else color_to_int(side_to_move)
        state = cls(turn_count=turn_count, side_to_move=side)
        if side == BLUE:
            state.hash_key ^= SIDE_TO_MOVE_HASH
        for coord, cell in board.items():
            if cell.color is None:
                continue
            row, col = coord
            state._set_cell(row * BOARD_N + col, cell.color.value, cell.height)
        return state

    @property
    def occupied_bits(self) -> int:
        return self.red_bits | self.blue_bits

    @property
    def play_phase(self) -> bool:
        return self.turn_count >= PLACEMENT_TURNS

    def color_at(self, idx: int) -> int:
        bit = 1 << idx
        if self.red_bits & bit:
            return RED
        if self.blue_bits & bit:
            return BLUE
        return EMPTY

    def token_count(self, color: int) -> int:
        return self.red_tokens if color == RED else self.blue_tokens

    def generate_actions(self, color: int | None = None) -> list[int]:
        side = self.side_to_move if color is None else color
        actions: list[int] = []

        if self.turn_count < PLACEMENT_TURNS:
            occupied = self.occupied_bits
            enemy_bits = self.blue_bits if side == RED else self.red_bits
            for idx in range(BOARD_CELLS):
                bit = 1 << idx
                if occupied & bit:
                    continue
                if NEIGHBOR_MASKS[idx] & enemy_bits:
                    continue
                actions.append(idx)
            return actions

        own_bits = self.red_bits if side == RED else self.blue_bits
        friendly_bits = own_bits
        enemy_bits = self.blue_bits if side == RED else self.red_bits

        bits = own_bits
        while bits:
            bit = bits & -bits
            idx = bit.bit_length() - 1
            height = self.heights[idx]
            base = idx * 4

            if height >= 2:
                actions.extend(CASCADE_BASE + base + direction for direction in range(4))

            for direction in range(4):
                target = NEXT_INDEX[idx][direction]
                if target == -1:
                    continue
                target_bit = 1 << target
                if not self.occupied_bits & target_bit or friendly_bits & target_bit:
                    actions.append(MOVE_BASE + base + direction)
                elif enemy_bits & target_bit and height >= self.heights[target]:
                    actions.append(EAT_BASE + base + direction)

            bits ^= bit

        return actions

    def has_legal_actions(self) -> bool:
        if self.turn_count < PLACEMENT_TURNS:
            return bool(self.generate_actions())

        side = self.side_to_move
        own_bits = self.red_bits if side == RED else self.blue_bits
        friendly_bits = own_bits
        enemy_bits = self.blue_bits if side == RED else self.red_bits

        bits = own_bits
        while bits:
            bit = bits & -bits
            idx = bit.bit_length() - 1
            height = self.heights[idx]
            if height >= 2:
                return True

            for direction in range(4):
                target = NEXT_INDEX[idx][direction]
                if target == -1:
                    continue
                target_bit = 1 << target
                if not self.occupied_bits & target_bit or friendly_bits & target_bit:
                    return True
                if enemy_bits & target_bit and height >= self.heights[target]:
                    return True

            bits ^= bit
        return False

    def make_move(self, action: int) -> UndoRecord:
        saved: dict[int, tuple[int, int]] = {}

        def remember(idx: int) -> None:
            if idx not in saved:
                saved[idx] = (self.color_at(idx), self.heights[idx])

        undo = UndoRecord(
            self.red_bits,
            self.blue_bits,
            self.red_tokens,
            self.blue_tokens,
            self.turn_count,
            self.side_to_move,
            self.hash_key,
            (),
        )

        kind = action_kind(action)
        if kind == PLACE:
            idx = action
            remember(idx)
            self._set_cell(idx, self.side_to_move, INITIAL_STACK_HEIGHT)
        else:
            idx, direction = decode_source_and_direction(action)
            source_color = self.color_at(idx)
            if source_color == EMPTY:
                raise ValueError(f"Cannot act from empty cell at {idx}")

            if kind == MOVE:
                target = NEXT_INDEX[idx][direction]
                if target == -1:
                    raise ValueError(f"Move goes out of bounds from {idx}")
                remember(idx)
                remember(target)
                target_color = self.color_at(target)
                if target_color == EMPTY:
                    self._set_cell(target, source_color, self.heights[idx])
                    self._set_cell(idx, EMPTY, 0)
                elif target_color == source_color:
                    self._set_cell(target, source_color, self.heights[target] + self.heights[idx])
                    self._set_cell(idx, EMPTY, 0)
                else:
                    raise ValueError(f"Cannot move onto enemy stack at {target}")

            elif kind == EAT:
                target = NEXT_INDEX[idx][direction]
                if target == -1:
                    raise ValueError(f"Eat goes out of bounds from {idx}")
                remember(idx)
                remember(target)
                self._set_cell(target, source_color, self.heights[idx])
                self._set_cell(idx, EMPTY, 0)

            elif kind == CASCADE:
                source_height = self.heights[idx]
                remember(idx)
                self._set_cell(idx, EMPTY, 0)

                def push_stack(current_idx: int) -> None:
                    current_color = self.color_at(current_idx)
                    if current_color == EMPTY:
                        return
                    current_height = self.heights[current_idx]
                    next_idx = NEXT_INDEX[current_idx][direction]
                    remember(current_idx)
                    if next_idx == -1:
                        self._set_cell(current_idx, EMPTY, 0)
                        return
                    if self.color_at(next_idx) != EMPTY:
                        push_stack(next_idx)
                    remember(next_idx)
                    self._set_cell(next_idx, current_color, current_height)
                    self._set_cell(current_idx, EMPTY, 0)

                current_idx = idx
                for _ in range(source_height):
                    next_idx = NEXT_INDEX[current_idx][direction]
                    if next_idx == -1:
                        break
                    if self.color_at(next_idx) != EMPTY:
                        push_stack(next_idx)
                    remember(next_idx)
                    self._set_cell(next_idx, source_color, 1)
                    current_idx = next_idx
            else:
                raise ValueError(f"Unknown action code: {action}")

        self.turn_count += 1
        self.side_to_move ^= 1
        self.hash_key ^= SIDE_TO_MOVE_HASH
        undo.changes = tuple((idx, color, height) for idx, (color, height) in saved.items())
        return undo

    def unmake_move(self, undo: UndoRecord) -> None:
        self.red_bits = undo.red_bits
        self.blue_bits = undo.blue_bits
        self.red_tokens = undo.red_tokens
        self.blue_tokens = undo.blue_tokens
        self.turn_count = undo.turn_count
        self.side_to_move = undo.side_to_move
        self.hash_key = undo.hash_key
        for idx, _color, height in undo.changes:
            self.heights[idx] = height

    def to_sparse(self) -> dict[tuple[int, int], CellState]:
        board: dict[tuple[int, int], CellState] = {}
        bits = self.occupied_bits
        while bits:
            bit = bits & -bits
            idx = bit.bit_length() - 1
            color = int_to_player_color(self.color_at(idx))
            board[divmod(idx, BOARD_N)] = CellState(color, self.heights[idx])
            bits ^= bit
        return board

    def signature(self) -> tuple[int, int, tuple[int, ...], int, int, int, int, int]:
        return (
            self.red_bits,
            self.blue_bits,
            tuple(self.heights),
            self.red_tokens,
            self.blue_tokens,
            self.turn_count,
            self.side_to_move,
            self.hash_key,
        )

    def _set_cell(self, idx: int, color: int, height: int) -> None:
        old_color = self.color_at(idx)
        old_height = self.heights[idx]
        bit = 1 << idx

        if old_color != EMPTY:
            self.hash_key ^= ZOBRIST[idx][old_color][old_height]
            if old_color == RED:
                self.red_bits &= ~bit
                self.red_tokens -= old_height
            else:
                self.blue_bits &= ~bit
                self.blue_tokens -= old_height

        self.heights[idx] = height
        if color == RED:
            self.red_bits |= bit
            self.red_tokens += height
            self.hash_key ^= ZOBRIST[idx][RED][height]
        elif color == BLUE:
            self.blue_bits |= bit
            self.blue_tokens += height
            self.hash_key ^= ZOBRIST[idx][BLUE][height]


def action_kind(action: int) -> int:
    if action < MOVE_BASE:
        return PLACE
    if action < EAT_BASE:
        return MOVE
    if action < CASCADE_BASE:
        return EAT
    return CASCADE


def decode_source_and_direction(action: int) -> tuple[int, int]:
    kind = action_kind(action)
    if kind == PLACE:
        return action, 0
    base = MOVE_BASE if kind == MOVE else EAT_BASE if kind == EAT else CASCADE_BASE
    offset = action - base
    return offset // 4, offset % 4


def encode_referee_action(action: Action) -> int:
    row, col = action.coord
    idx = row * BOARD_N + col
    if isinstance(action, PlaceAction):
        return idx
    direction = DIR_TO_INDEX[action.direction]
    if isinstance(action, MoveAction):
        return MOVE_BASE + idx * 4 + direction
    if isinstance(action, EatAction):
        return EAT_BASE + idx * 4 + direction
    if isinstance(action, CascadeAction):
        return CASCADE_BASE + idx * 4 + direction
    raise ValueError(f"Unknown action: {action}")


def decode_referee_action(action: int) -> Action:
    kind = action_kind(action)
    if kind == PLACE:
        idx = action
        return PlaceAction(Coord(idx // BOARD_N, idx % BOARD_N))

    idx, direction = decode_source_and_direction(action)
    coord = Coord(idx // BOARD_N, idx % BOARD_N)
    referee_direction = DIRECTIONS[direction]
    if kind == MOVE:
        return MoveAction(coord, referee_direction)
    if kind == EAT:
        return EatAction(coord, referee_direction)
    return CascadeAction(coord, referee_direction)


def color_to_int(color: PlayerColor | int) -> int:
    return color if isinstance(color, int) else color.value


def int_to_player_color(color: int) -> PlayerColor:
    return PlayerColor.RED if color == RED else PlayerColor.BLUE


def board_from_rows(rows: Iterable[tuple[int, int, int]]) -> dict[tuple[int, int], CellState]:
    board: dict[tuple[int, int], CellState] = {}
    for idx, color, height in rows:
        board[divmod(idx, BOARD_N)] = CellState(int_to_player_color(color), height)
    return board
