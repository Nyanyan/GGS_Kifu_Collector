from __future__ import annotations

from othello import OthelloBoard, make_standard_initial_board_64, simulate_game


def test_standard_initial_legal_moves_and_flip() -> None:
    board = OthelloBoard.standard_initial()
    assert board.legal_moves("black") == {"c4", "d3", "e6", "f5"}

    board.apply_move("black", "f5")
    assert board.get("f5") == "X"
    assert board.get("e5") == "X"
    assert "d6" in board.legal_moves("white")


def test_pass_is_legal_only_when_no_moves() -> None:
    board_64 = (
        "OOOOOOOO"
        "OOOOOOOO"
        "OOOOOOOO"
        "OO-XOOOO"
        "OOOOOOOO"
        "OOOOOOOO"
        "OOOOOOOO"
        "OOOOOOOO"
    )
    result = simulate_game(board_64, "black", ["pass", "c4"])
    assert result.is_valid
    assert result.is_terminal
    assert result.terminated_by == "board_full"

    illegal_pass = simulate_game(make_standard_initial_board_64(), "black", ["pass"])
    assert not illegal_pass.is_valid
    assert illegal_pass.reason and "illegal pass" in illegal_pass.reason


def test_double_pass_terminal() -> None:
    board_64 = (
        "O-XXXXXX"
        "XXXXXXXX"
        "XXXXXXXX"
        "XXXXXXXX"
        "XXXXXXXX"
        "XXXXXXXX"
        "XXXXXXXX"
        "XXXXXXXX"
    )
    result = simulate_game(board_64, "black", ["pass", "pass"])
    assert result.is_valid
    assert result.is_terminal
    assert result.terminated_by == "double_pass"


def test_illegal_move_rejected() -> None:
    result = simulate_game(make_standard_initial_board_64(), "black", ["a1"])
    assert not result.is_valid
    assert result.reason and "illegal move" in result.reason

