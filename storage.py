from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TextIO

from models import MatchState
from othello import SimulationResult


def _safe_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return sanitized.strip("_") or "unknown"


def _timestamp_for_path(moment: Optional[datetime]) -> str:
    dt = moment.astimezone(timezone.utc) if moment else datetime.now(timezone.utc)
    return dt.strftime("%Y%m%d_%H%M%S")


def _initial_stone_count(board_64: str) -> int:
    return sum(1 for cell in board_64 if cell in {"X", "O"})


def _write_text(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _turn_marker(turn: str) -> str:
    return "X" if turn == "black" else "O"


def save_completed_game(
    *,
    state: MatchState,
    simulation: SimulationResult,
    out_dir: Path,
    raw_log_file: Path,
    dry_run: bool,
) -> Optional[Path]:
    if dry_run:
        return None
    if not state.initial_board_64:
        raise ValueError("state.initial_board_64 is required")

    out_dir.mkdir(parents=True, exist_ok=True)
    stones = _initial_stone_count(state.initial_board_64)
    stones_dir = out_dir / f"stones_{stones:02d}"
    stones_dir.mkdir(parents=True, exist_ok=True)

    timestamp = _timestamp_for_path(state.end_time or state.start_time)
    black = _safe_name(state.black_player or "black")
    white = _safe_name(state.white_player or "white")
    base_name = f"{timestamp}_{state.match_id}_{black}_vs_{white}"

    final_dir = stones_dir / base_name
    suffix = 1
    while final_dir.exists():
        final_dir = stones_dir / f"{base_name}_{suffix}"
        suffix += 1

    temp_dir = final_dir.with_name(final_dir.name + ".tmp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=False)

    moves = state.moves
    compact = "".join(move for move in moves if move != "pass")
    safe_line = " ".join(moves)

    record_txt = "\n".join(
        [
            state.initial_board_64,
            state.initial_turn_or_default,
            compact,
            safe_line,
        ]
    ) + "\n"
    _write_text(temp_dir / "record.txt", record_txt)

    metadata = {
        "match_id": state.match_id,
        "black_player": state.black_player,
        "white_player": state.white_player,
        "game_type": state.game_type,
        "start_time": (state.start_time or datetime.now(timezone.utc)).isoformat(),
        "end_time": (state.end_time or datetime.now(timezone.utc)).isoformat(),
        "initial_stone_count": stones,
        "initial_board_64": state.initial_board_64,
        "initial_turn": state.initial_turn_or_default,
        "moves": moves,
        "moves_compact": compact,
        "final_board_64": simulation.final_board_64,
        "final_black_count": simulation.final_black_count,
        "final_white_count": simulation.final_white_count,
        "result_from_board": simulation.result_from_board,
        "result_from_ggs": state.result_from_ggs,
        "source": "GGS live watch",
        "raw_log_file": str(raw_log_file),
        "parser_warnings": state.parser_warnings,
    }
    _write_text(
        temp_dir / "metadata.json",
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    )

    raw_content = "\n".join(state.raw_lines) + ("\n" if state.raw_lines else "")
    _write_text(temp_dir / "raw.txt", raw_content)

    # 同一ファイルシステム上のrenameで原子的に公開する。
    os.replace(temp_dir, final_dir)
    return final_dir


class CompactBatchWriter:
    def __init__(self, out_dir: Path, max_records_per_file: int = 10000) -> None:
        if max_records_per_file <= 0:
            raise ValueError("max_records_per_file must be > 0")
        self.out_dir = out_dir
        self.max_records_per_file = max_records_per_file
        self._path: Optional[Path] = None
        self._fh: Optional[TextIO] = None
        self._count = 0
        self.out_dir.mkdir(parents=True, exist_ok=True)

    @property
    def current_path(self) -> Optional[Path]:
        return self._path

    def append_record(self, state: MatchState) -> Path:
        if not state.initial_board_64:
            raise ValueError("state.initial_board_64 is required")
        if self._fh is None or self._count >= self.max_records_per_file:
            self._open_new_file()

        marker = _turn_marker(state.initial_turn_or_default)
        compact = "".join(move for move in state.moves if move != "pass")
        line = f"{state.initial_board_64} {marker} {compact}\n"

        assert self._fh is not None
        self._fh.write(line)
        self._fh.flush()
        self._count += 1

        assert self._path is not None
        return self._path

    def close(self) -> None:
        if self._fh:
            self._fh.flush()
            self._fh.close()
        self._fh = None
        self._path = None
        self._count = 0

    def _open_new_file(self) -> None:
        if self._fh:
            self._fh.flush()
            self._fh.close()
        self._path = self._new_path()
        self._fh = self._path.open("a", encoding="utf-8", newline="\n")
        self._count = 0

    def _new_path(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = self.out_dir / f"{timestamp}.txt"
        if not base.exists():
            return base

        suffix = 1
        while True:
            candidate = self.out_dir / f"{timestamp}_{suffix:02d}.txt"
            if not candidate.exists():
                return candidate
            suffix += 1


def save_error_report(
    *,
    errors_dir: Path,
    state: MatchState,
    reason: str,
    dry_run: bool,
) -> Optional[Path]:
    if dry_run:
        return None
    errors_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp_for_path(datetime.now(timezone.utc))
    filename = f"{timestamp}_{state.match_id}.json"
    path = errors_dir / filename

    payload = {
        "match_id": state.match_id,
        "reason": reason,
        "black_player": state.black_player,
        "white_player": state.white_player,
        "game_type": state.game_type,
        "initial_board_64": state.initial_board_64,
        "initial_turn": state.initial_turn,
        "moves": state.moves,
        "result_from_ggs": state.result_from_ggs,
        "parser_warnings": state.parser_warnings,
        "raw_log": state.raw_lines,
    }
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path
