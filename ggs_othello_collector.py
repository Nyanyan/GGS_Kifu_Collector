from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
from datetime import datetime, timedelta, timezone
from getpass import getpass
from pathlib import Path
from typing import Optional

from ggs_client import GGSClient
from models import MatchState
from othello import make_standard_initial_board_64, simulate_game
from parser import is_standard_like_game_type, parse_stream_line
from storage import save_completed_game, save_error_report

LOGGER = logging.getLogger("ggs_othello_collector")


class SessionRawLogger:
    def __init__(self, raw_log_dir: Path) -> None:
        raw_log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.path = raw_log_dir / f"session_{ts}.log"
        self._fh = self.path.open("a", encoding="utf-8", newline="\n")

    def write(self, direction: str, payload: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        text = payload.replace("\r", "\\r").replace("\n", "\\n")
        self._fh.write(f"[{timestamp}] {direction} {text}\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()


class Collector:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.out_dir = Path(args.out_dir)
        self.errors_dir = Path("errors")
        self.raw_logger = SessionRawLogger(Path(args.raw_log_dir))

        self.matches: dict[str, MatchState] = {}
        self.watching_ids: set[str] = set()
        self.requested_watch_ids: set[str] = set()
        self.current_context_match_id: Optional[str] = None
        self.board_buffers: dict[str, dict[int, str]] = {}
        self.join_capture_needs_initial: set[str] = set()
        self.join_capture_saw_move_row: set[str] = set()

        self.stop_event = asyncio.Event()
        self.first_match_poll_done = False
        self.match_window_deadline: Optional[datetime] = None

        self.client = GGSClient(
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
            logger=LOGGER,
            raw_sink=self.raw_logger.write,
        )

    async def run(self) -> None:
        await self.client.start()
        tasks = [
            asyncio.create_task(self._line_loop(), name="collector-lines"),
            asyncio.create_task(self._status_loop(), name="collector-status"),
            asyncio.create_task(self._poll_loop(), name="collector-poll"),
        ]
        try:
            await self.stop_event.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self._shutdown_active_matches()
            await self.client.stop()
            self.raw_logger.close()

    async def _status_loop(self) -> None:
        while not self.stop_event.is_set():
            status, detail = await self.client.status_queue.get()
            try:
                if status == "connected":
                    await self._on_connected()
                elif status == "disconnected":
                    LOGGER.warning("disconnected: %s", detail)
                    await self._on_disconnected(detail)
                elif status == "stopped":
                    return
            except Exception:
                LOGGER.exception("status handler failed for status=%s detail=%s", status, detail)

    async def _on_connected(self) -> None:
        await self.client.send_command("t /os vt100 -")
        await self.client.send_command("t /os client -")
        if self.args.once and not self.first_match_poll_done:
            await self._poll_match_once()

    async def _on_disconnected(self, reason: str) -> None:
        for match_id in list(self.watching_ids):
            state = self.matches.get(match_id)
            if not state or state.finalised:
                continue
            await self._drop_match(state, f"connection_lost: {reason}")
        self.watching_ids.clear()
        self.requested_watch_ids.clear()

    async def _poll_loop(self) -> None:
        if self.args.once:
            # onceモードは接続時に1回だけpollする。
            while not self.stop_event.is_set():
                await asyncio.sleep(0.5)
                if self.first_match_poll_done and not self.watching_ids:
                    self.stop_event.set()
                    return
            return

        while not self.stop_event.is_set():
            if self.client.connected_event.is_set():
                try:
                    await self._send_match_command()
                except Exception:
                    LOGGER.exception("failed to poll /os match")
            await asyncio.sleep(self.args.poll_interval)

    async def _poll_match_once(self) -> None:
        await self._send_match_command()
        self.first_match_poll_done = True

    async def _send_match_command(self) -> None:
        await self.client.send_command("t /os match")
        self.match_window_deadline = datetime.now(timezone.utc) + timedelta(seconds=6)

    def _in_match_window(self) -> bool:
        if not self.match_window_deadline:
            return False
        return datetime.now(timezone.utc) <= self.match_window_deadline

    def _get_or_create_match(self, match_id: str) -> MatchState:
        state = self.matches.get(match_id)
        if state is None:
            state = MatchState(match_id=match_id)
            self.matches[match_id] = state
        return state

    async def _line_loop(self) -> None:
        while not self.stop_event.is_set():
            line = await self.client.incoming_queue.get()
            try:
                await self._handle_line(line)
            except Exception:
                LOGGER.exception("line handler crashed; line=%r", line)

    async def _handle_line(self, line: str) -> None:
        parsed = parse_stream_line(line)
        if parsed.context_match_id:
            self.current_context_match_id = parsed.context_match_id
            if parsed.context_kind == "join":
                self.join_capture_needs_initial.add(parsed.context_match_id)
                self.join_capture_saw_move_row.discard(parsed.context_match_id)
                self.board_buffers.pop(parsed.context_match_id, None)

        for listing in parsed.listings:
            state = self._get_or_create_match(listing.match_id)
            state.update_identity(
                black_player=listing.black_player,
                white_player=listing.white_player,
                game_type=listing.game_type,
            )

        if self._in_match_window():
            for match_id in parsed.match_ids:
                await self._watch_match_if_needed(match_id)

        target_ids = set(parsed.match_ids)
        if parsed.context_match_id:
            target_ids.add(parsed.context_match_id)

        has_context_sensitive_payload = any(
            [
                bool(parsed.moves),
                bool(parsed.initial_board_64),
                bool(parsed.initial_turn),
                parsed.board_row_index is not None,
                parsed.move_count_hint is not None,
            ]
        )
        if not target_ids and has_context_sensitive_payload and self.current_context_match_id:
            target_ids.add(self.current_context_match_id)
        if not target_ids and (parsed.moves or parsed.initial_board_64) and len(self.watching_ids) == 1:
            only = next(iter(self.watching_ids))
            target_ids.add(only)

        for match_id in target_ids:
            state = self._get_or_create_match(match_id)
            state.append_raw(line)
            if parsed.game_type and not state.game_type:
                state.game_type = parsed.game_type
            if parsed.initial_board_64:
                state.set_initial_position(parsed.initial_board_64, parsed.initial_turn)
            elif parsed.initial_turn and not state.initial_turn:
                state.initial_turn = parsed.initial_turn

            if parsed.player_name and parsed.player_color:
                if parsed.player_color == "black":
                    state.black_player = parsed.player_name
                elif parsed.player_color == "white":
                    state.white_player = parsed.player_name

            if parsed.board_row_index is not None and parsed.board_row_8 is not None:
                rows = self.board_buffers.setdefault(match_id, {})
                rows[parsed.board_row_index] = parsed.board_row_8
                if len(rows) == 8:
                    board64 = "".join(rows[row_no] for row_no in range(1, 9))
                    should_capture_initial = (
                        match_id in self.join_capture_needs_initial
                        and match_id not in self.join_capture_saw_move_row
                        and not state.initial_board_64
                    )
                    if should_capture_initial:
                        state.set_initial_position(board64, state.initial_turn or parsed.initial_turn)
                        self.join_capture_needs_initial.discard(match_id)
                        self.join_capture_saw_move_row.discard(match_id)
                    self.board_buffers.pop(match_id, None)

            if parsed.warnings:
                for warning in parsed.warnings:
                    state.add_warning(warning)

            if parsed.moves:
                if parsed.snapshot_like:
                    state.merge_snapshot_moves(parsed.moves)
                else:
                    for move in parsed.moves:
                        if move.ply is not None and move.ply > 0 and match_id in self.join_capture_needs_initial:
                            self.join_capture_saw_move_row.add(match_id)
                        state.append_live_move(move)

            if parsed.result:
                state.mark_terminal(parsed.result)
                await self._finalise_match(state)

        if parsed.closed_match_id:
            await self._unwatch(parsed.closed_match_id)

    @staticmethod
    def _watch_root_id(match_id: str) -> str:
        return match_id.split(".", 1)[0]

    def _clear_capture_state(self, match_id: str) -> None:
        self.board_buffers.pop(match_id, None)
        self.join_capture_needs_initial.discard(match_id)
        self.join_capture_saw_move_row.discard(match_id)

    async def _watch_match_if_needed(self, match_id: str) -> None:
        watch_id = self._watch_root_id(match_id)
        if watch_id in self.requested_watch_ids or watch_id in self.watching_ids:
            return
        if len(self.watching_ids) >= self.args.max_watches:
            LOGGER.warning("max watches reached (%s), skip match %s", self.args.max_watches, match_id)
            return
        self.requested_watch_ids.add(watch_id)
        state = self._get_or_create_match(watch_id)
        try:
            await self.client.send_command(f"t /os watch + .{watch_id}")
            state.append_raw(f"SEND t /os watch + .{watch_id}")
            await self.client.send_command(f"t /os moves .{watch_id}")
            state.append_raw(f"SEND t /os moves .{watch_id}")
            state.watching = True
            self.watching_ids.add(watch_id)
            LOGGER.info("watching match .%s", watch_id)
        except Exception:
            self.requested_watch_ids.discard(watch_id)
            LOGGER.exception("failed to start watching .%s", watch_id)

    async def _unwatch(self, match_id: str) -> None:
        watch_id = self._watch_root_id(match_id)
        if watch_id not in self.requested_watch_ids and watch_id not in self.watching_ids:
            return
        if self.client.connected_event.is_set():
            try:
                await self.client.send_command(f"t /os watch - .{watch_id}")
            except Exception as exc:
                LOGGER.warning("failed to unwatch .%s: %s", watch_id, exc)
        self.watching_ids.discard(watch_id)
        self.requested_watch_ids.discard(watch_id)

    async def _finalise_match(self, state: MatchState) -> None:
        if state.finalised:
            return
        state.finalised = True

        disqualifying_reason = self._detect_disqualifying_result(state)
        if disqualifying_reason:
            await self._drop_match(state, disqualifying_reason)
            return

        if not state.initial_board_64:
            if is_standard_like_game_type(state.game_type):
                state.initial_board_64 = make_standard_initial_board_64()
                if not state.initial_turn:
                    state.initial_turn = "black"
            else:
                await self._drop_match(state, "initial_board_missing")
                return

        if not state.initial_turn:
            state.initial_turn = "black"

        simulation = simulate_game(
            initial_board_64=state.initial_board_64,
            initial_turn=state.initial_turn_or_default,
            moves=state.moves,
        )
        if not simulation.is_valid:
            await self._drop_match(state, simulation.reason or "invalid_moves")
            return
        if not simulation.is_terminal:
            await self._drop_match(state, "not_terminal_by_rules")
            return

        if state.parsed_result and state.parsed_result.margin is not None:
            board_diff = simulation.final_black_count - simulation.final_white_count
            margin = state.parsed_result.margin
            # GGSの表示はフォーマットにより「黒基準」または「先手名基準」の揺れがあるため、
            # ここでは石差の絶対値整合を最低条件にする。
            if abs(board_diff) != abs(margin):
                await self._drop_match(
                    state,
                    f"result_mismatch board_diff={board_diff} ggs={margin}",
                )
                return

        saved = save_completed_game(
            state=state,
            simulation=simulation,
            out_dir=self.out_dir,
            raw_log_file=self.raw_logger.path,
            dry_run=self.args.dry_run,
        )
        LOGGER.info("saved match .%s -> %s", state.match_id, saved if saved else "(dry-run)")
        self._clear_capture_state(state.match_id)
        if "." not in state.match_id:
            await self._unwatch(state.match_id)

    def _detect_disqualifying_result(self, state: MatchState) -> Optional[str]:
        result = state.parsed_result
        if not result:
            return None
        if result.is_disqualifying:
            return f"disqualifying_result_flags={sorted(result.flags)}"
        return None

    async def _drop_match(self, state: MatchState, reason: str) -> None:
        LOGGER.warning("drop match .%s: %s", state.match_id, reason)
        save_error_report(
            errors_dir=self.errors_dir,
            state=state,
            reason=reason,
            dry_run=self.args.dry_run,
        )
        self._clear_capture_state(state.match_id)
        if "." not in state.match_id:
            await self._unwatch(state.match_id)

    async def _shutdown_active_matches(self) -> None:
        for match_id in list(self.watching_ids):
            state = self.matches.get(match_id)
            if state and not state.finalised:
                save_error_report(
                    errors_dir=self.errors_dir,
                    state=state,
                    reason="shutdown_before_terminal",
                    dry_run=self.args.dry_run,
                )
            await self._unwatch(match_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect live Othello game records from GGS /os by watching running matches."
    )
    parser.add_argument("--host", default="skatgame.net")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password")
    parser.add_argument("--out-dir", default="records")
    parser.add_argument("--raw-log-dir", default="raw_logs")
    parser.add_argument("--poll-interval", type=float, default=30.0)
    parser.add_argument("--max-watches", type=int, default=200)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def resolve_password(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    env_password = os.environ.get("GGS_PASSWORD")
    if env_password:
        return env_password
    return getpass("GGS password: ")


async def async_main() -> None:
    args = parse_args()
    args.password = resolve_password(args)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    collector = Collector(args)
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        LOGGER.info("shutdown signal received")
        collector.stop_event.set()

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            # Windowsのイベントループでは未対応の場合がある。
            pass

    await collector.run()


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
