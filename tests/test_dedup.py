from __future__ import annotations

from models import MatchState, MoveEvent


def test_duplicate_move_not_double_registered() -> None:
    state = MatchState(match_id="99999")
    assert state.append_live_move(MoveEvent(move="f5", color="black", ply=1))
    assert not state.append_live_move(MoveEvent(move="f5", color="black", ply=1))
    assert [move.move for move in state.move_events] == ["f5"]

    state.merge_snapshot_moves(
        [
            MoveEvent(move="f5", color="black", ply=1),
            MoveEvent(move="d6", color="white", ply=2),
        ]
    )
    assert [move.move for move in state.move_events] == ["f5", "d6"]
