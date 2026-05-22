from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from models import MatchState
from othello import SimulationResult
from storage import save_completed_game


def _simulation_stub(final_board_64: str) -> SimulationResult:
    black = sum(1 for c in final_board_64 if c == "X")
    white = sum(1 for c in final_board_64 if c == "O")
    diff = black - white
    if diff > 0:
        result = f"B+{diff}"
    elif diff < 0:
        result = f"W+{abs(diff)}"
    else:
        result = "D"
    return SimulationResult(
        is_valid=True,
        is_terminal=True,
        terminated_by="board_full",
        reason=None,
        final_board_64=final_board_64,
        final_black_count=black,
        final_white_count=white,
        result_from_board=result,
    )


def _build_board(x_count: int, o_count: int) -> str:
    if x_count + o_count > 64:
        raise ValueError("too many stones")
    return "X" * x_count + "O" * o_count + "-" * (64 - x_count - o_count)


def test_saved_into_stones_04_and_atomic_rename(tmp_path: Path) -> None:
    out_dir = tmp_path / "records"
    state = MatchState(
        match_id="11111",
        black_player="alice",
        white_player="bob",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        initial_board_64=(
            "--------"
            "--------"
            "--------"
            "---OX---"
            "---XO---"
            "--------"
            "--------"
            "--------"
        ),
        initial_turn="black",
    )
    state.merge_snapshot_moves([])
    simulation = _simulation_stub(_build_board(32, 32))
    saved = save_completed_game(
        state=state,
        simulation=simulation,
        out_dir=out_dir,
        raw_log_file=tmp_path / "session.log",
        dry_run=False,
    )
    assert saved is not None
    assert saved.parent.name == "stones_04"
    assert (saved / "record.txt").exists()
    assert (saved / "metadata.json").exists()
    assert (saved / "raw.txt").exists()
    assert not list(out_dir.rglob("*.tmp"))


def test_saved_into_stones_14(tmp_path: Path) -> None:
    out_dir = tmp_path / "records"
    state = MatchState(
        match_id="22222",
        black_player="alice",
        white_player="bob",
        initial_board_64=_build_board(7, 7),
        initial_turn="white",
    )
    simulation = _simulation_stub(_build_board(20, 44))
    saved = save_completed_game(
        state=state,
        simulation=simulation,
        out_dir=out_dir,
        raw_log_file=tmp_path / "session.log",
        dry_run=False,
    )
    assert saved is not None
    assert saved.parent.name == "stones_14"

