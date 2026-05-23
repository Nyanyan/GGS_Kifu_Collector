from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from ggs_othello_collector import Collector
from models import MatchState


class RecordingClient:
    def __init__(self) -> None:
        self.commands: list[str] = []

    async def send_command(self, command: str) -> None:
        self.commands.append(command)


def _make_collector(tmp_path: Path, *, once: bool = False) -> Collector:
    args = SimpleNamespace(
        host="example.invalid",
        port=5000,
        username="user",
        password="pass",
        out_dir=str(tmp_path / "records"),
        raw_log_dir=str(tmp_path / "raw_logs"),
        poll_interval=30.0,
        max_watches=200,
        once=once,
        dry_run=False,
        verbose=False,
    )
    collector = Collector(args)
    collector.errors_dir = tmp_path / "errors"
    return collector


def _close_collector(collector: Collector) -> None:
    collector.compact_batch_writer.close()
    collector.raw_logger.close()


def test_disconnect_marks_watches_for_resume_without_dropping(tmp_path: Path) -> None:
    asyncio.run(_test_disconnect_marks_watches_for_resume_without_dropping(tmp_path))


async def _test_disconnect_marks_watches_for_resume_without_dropping(tmp_path: Path) -> None:
    collector = _make_collector(tmp_path)
    try:
        state = MatchState(match_id="123")
        state.watching = True
        collector.matches["123"] = state
        collector.watching_ids.add("123")
        collector.requested_watch_ids.add("456")
        collector.current_context_match_id = "123"
        collector.match_window_deadline = datetime.now(timezone.utc) + timedelta(seconds=6)
        collector.board_buffers["123"] = {1: "--------"}
        collector.join_capture_needs_initial.add("123")

        await collector._on_disconnected("OSError: [WinError 121] timeout")

        assert collector.watching_ids == set()
        assert collector.requested_watch_ids == set()
        assert collector.pending_resume_watch_ids == {"123", "456"}
        assert collector.current_context_match_id is None
        assert collector.match_window_deadline is None
        assert collector.board_buffers == {}
        assert not state.finalised
        assert not state.watching
        assert state.parser_warnings == ["connection_lost: OSError: [WinError 121] timeout"]
        assert not collector.errors_dir.exists()
    finally:
        _close_collector(collector)


def test_reconnect_resumes_watches_and_polls_immediately(tmp_path: Path) -> None:
    asyncio.run(_test_reconnect_resumes_watches_and_polls_immediately(tmp_path))


async def _test_reconnect_resumes_watches_and_polls_immediately(tmp_path: Path) -> None:
    collector = _make_collector(tmp_path)
    try:
        client = RecordingClient()
        collector.client = client  # type: ignore[assignment]
        collector.matches["123"] = MatchState(match_id="123")
        collector.pending_resume_watch_ids.add("123")

        await collector._on_connected()

        assert client.commands == [
            "t /os vt100 -",
            "t /os client -",
            "t /os watch + .123",
            "t /os moves .123",
            "t /os match",
        ]
        assert collector.pending_resume_watch_ids == set()
        assert collector.watching_ids == {"123"}
        assert collector.requested_watch_ids == {"123"}
        assert collector.match_window_deadline is not None
    finally:
        _close_collector(collector)
