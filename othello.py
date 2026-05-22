from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from models import normalize_color

BOARD_SIZE = 8
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


def opponent(color: str) -> str:
    normalized = normalize_color(color)
    if normalized == "black":
        return "white"
    if normalized == "white":
        return "black"
    raise ValueError(f"invalid color: {color}")


def coord_to_index(coord: str) -> int:
    move = coord.strip().lower()
    if len(move) != 2:
        raise ValueError(f"invalid coord: {coord}")
    file_char, rank_char = move[0], move[1]
    if file_char < "a" or file_char > "h":
        raise ValueError(f"invalid coord file: {coord}")
    if rank_char < "1" or rank_char > "8":
        raise ValueError(f"invalid coord rank: {coord}")
    x = ord(file_char) - ord("a")
    y = ord(rank_char) - ord("1")
    return y * BOARD_SIZE + x


def index_to_coord(index: int) -> str:
    y, x = divmod(index, BOARD_SIZE)
    return f"{chr(ord('a') + x)}{y + 1}"


def _normalize_cell(cell: str) -> str:
    if cell in {"X", "x", "*"}:
        return "X"
    if cell in {"O", "o"}:
        return "O"
    if cell in {"-", "."}:
        return "-"
    raise ValueError(f"invalid board cell: {cell}")


def make_standard_initial_board_64() -> str:
    board = ["-"] * 64
    board[coord_to_index("d4")] = "O"
    board[coord_to_index("e5")] = "O"
    board[coord_to_index("e4")] = "X"
    board[coord_to_index("d5")] = "X"
    return "".join(board)


@dataclass(slots=True)
class SimulationResult:
    is_valid: bool
    is_terminal: bool
    terminated_by: str | None
    reason: str | None
    final_board_64: str
    final_black_count: int
    final_white_count: int
    result_from_board: str


class OthelloBoard:
    def __init__(self, board: Iterable[str]) -> None:
        items = list(board)
        if len(items) != 64:
            raise ValueError("board length must be 64")
        self._cells = [_normalize_cell(cell) for cell in items]

    @classmethod
    def from_board_64(cls, board_64: str) -> "OthelloBoard":
        if len(board_64) != 64:
            raise ValueError("board_64 length must be 64")
        return cls(board_64)

    @classmethod
    def standard_initial(cls) -> "OthelloBoard":
        return cls.from_board_64(make_standard_initial_board_64())

    def clone(self) -> "OthelloBoard":
        return OthelloBoard(self._cells[:])

    def to_board_64(self) -> str:
        return "".join(self._cells)

    def get(self, coord: str) -> str:
        return self._cells[coord_to_index(coord)]

    def counts(self) -> tuple[int, int]:
        black = sum(1 for cell in self._cells if cell == "X")
        white = sum(1 for cell in self._cells if cell == "O")
        return black, white

    def is_full(self) -> bool:
        return all(cell != "-" for cell in self._cells)

    def legal_moves(self, color: str) -> set[str]:
        normalized = normalize_color(color)
        if not normalized:
            raise ValueError(f"invalid color: {color}")
        target = "X" if normalized == "black" else "O"
        opponent_cell = "O" if target == "X" else "X"
        result: set[str] = set()
        for index, cell in enumerate(self._cells):
            if cell != "-":
                continue
            if self._captures(index, target, opponent_cell):
                result.add(index_to_coord(index))
        return result

    def can_move(self, color: str) -> bool:
        return bool(self.legal_moves(color))

    def apply_move(self, color: str, move: str) -> None:
        normalized = normalize_color(color)
        if not normalized:
            raise ValueError(f"invalid color: {color}")
        target = "X" if normalized == "black" else "O"
        opponent_cell = "O" if target == "X" else "X"
        index = coord_to_index(move)
        if self._cells[index] != "-":
            raise ValueError(f"occupied square: {move}")
        flips = self._captures(index, target, opponent_cell)
        if not flips:
            raise ValueError(f"illegal move: {move}")
        self._cells[index] = target
        for flip_index in flips:
            self._cells[flip_index] = target

    def _captures(self, index: int, own: str, other: str) -> list[int]:
        y, x = divmod(index, BOARD_SIZE)
        all_flips: list[int] = []
        for dx, dy in DIRECTIONS:
            nx, ny = x + dx, y + dy
            chain: list[int] = []
            while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                n_index = ny * BOARD_SIZE + nx
                cell = self._cells[n_index]
                if cell == other:
                    chain.append(n_index)
                    nx += dx
                    ny += dy
                    continue
                if cell == own and chain:
                    all_flips.extend(chain)
                break
        return all_flips


def _board_result_string(black: int, white: int) -> str:
    diff = black - white
    if diff > 0:
        return f"B+{diff}"
    if diff < 0:
        return f"W+{abs(diff)}"
    return "D"


def _is_terminal_position(board: OthelloBoard) -> tuple[bool, str | None]:
    if board.is_full():
        return True, "board_full"
    if not board.can_move("black") and not board.can_move("white"):
        return True, "no_legal_moves"
    return False, None


def simulate_game(
    initial_board_64: str,
    initial_turn: str,
    moves: list[str],
) -> SimulationResult:
    board = OthelloBoard.from_board_64(initial_board_64)
    to_move = normalize_color(initial_turn)
    if not to_move:
        raise ValueError(f"invalid initial turn: {initial_turn}")

    consecutive_passes = 0
    for ply_index, raw_move in enumerate(moves, start=1):
        if board.is_full() or consecutive_passes >= 2:
            black, white = board.counts()
            return SimulationResult(
                is_valid=False,
                is_terminal=True,
                terminated_by="board_full" if board.is_full() else "double_pass",
                reason=f"extra move after terminal at ply {ply_index}: {raw_move}",
                final_board_64=board.to_board_64(),
                final_black_count=black,
                final_white_count=white,
                result_from_board=_board_result_string(black, white),
            )

        move = raw_move.lower().strip()
        legal = board.legal_moves(to_move)
        if move == "pass":
            if legal:
                black, white = board.counts()
                return SimulationResult(
                    is_valid=False,
                    is_terminal=False,
                    terminated_by=None,
                    reason=f"illegal pass at ply {ply_index}",
                    final_board_64=board.to_board_64(),
                    final_black_count=black,
                    final_white_count=white,
                    result_from_board=_board_result_string(black, white),
                )
            consecutive_passes += 1
        else:
            if move not in legal:
                black, white = board.counts()
                return SimulationResult(
                    is_valid=False,
                    is_terminal=False,
                    terminated_by=None,
                    reason=f"illegal move at ply {ply_index}: {move}",
                    final_board_64=board.to_board_64(),
                    final_black_count=black,
                    final_white_count=white,
                    result_from_board=_board_result_string(black, white),
                )
            board.apply_move(to_move, move)
            consecutive_passes = 0

        to_move = opponent(to_move)

    terminal, terminal_reason = _is_terminal_position(board)
    if consecutive_passes >= 2:
        terminal = True
        terminal_reason = "double_pass"

    black, white = board.counts()
    return SimulationResult(
        is_valid=True,
        is_terminal=terminal,
        terminated_by=terminal_reason,
        reason=None if terminal else "game not finished",
        final_board_64=board.to_board_64(),
        final_black_count=black,
        final_white_count=white,
        result_from_board=_board_result_string(black, white),
    )
