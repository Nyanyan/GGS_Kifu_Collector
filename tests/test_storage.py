from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from models import MatchState, MoveEvent
from othello import SimulationResult
from storage import CompactBatchWriter, save_completed_game


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


def test_compact_batch_writer_and_rotation(tmp_path: Path) -> None:
    writer = CompactBatchWriter(tmp_path / "compact_batches", max_records_per_file=2)

    state1 = MatchState(
        match_id="1",
        initial_board_64=_build_board(7, 7),
        initial_turn="black",
    )
    state1.append_live_move(MoveEvent(move="b4", color="black", ply=1))
    state1.append_live_move(MoveEvent(move="d7", color="white", ply=2))

    state2 = MatchState(
        match_id="2",
        initial_board_64=_build_board(8, 6),
        initial_turn="white",
    )
    state2.append_live_move(MoveEvent(move="c7", color="white", ply=1))

    state3 = MatchState(
        match_id="3",
        initial_board_64=_build_board(9, 5),
        initial_turn="black",
    )
    state3.append_live_move(MoveEvent(move="a1", color="black", ply=1))

    file_a = writer.append_record(state1)
    file_b = writer.append_record(state2)
    file_c = writer.append_record(state3)
    writer.close()

    assert file_a == file_b
    assert file_c != file_a

    lines_a = file_a.read_text(encoding="utf-8").splitlines()
    lines_c = file_c.read_text(encoding="utf-8").splitlines()

    assert len(lines_a) == 2
    assert len(lines_c) == 1
    assert lines_a[0].endswith(" X b4d7")
    assert lines_a[1].endswith(" O c7")
    assert lines_c[0].endswith(" X a1")
