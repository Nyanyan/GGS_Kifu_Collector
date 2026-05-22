from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    path.write_text(content, encoding="utf-8", newline="\n")


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

