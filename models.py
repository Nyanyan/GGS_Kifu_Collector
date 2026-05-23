from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_color(color: Optional[str]) -> Optional[str]:
    if color is None:
        return None
    value = color.strip().lower()
    if value in {"b", "black"}:
        return "black"
    if value in {"w", "white"}:
        return "white"
    return None


@dataclass
class MoveEvent:
    move: str
    color: Optional[str] = None
    source: str = "stream"
    raw: str = ""
    ply: Optional[int] = None

    def normalized(self) -> "MoveEvent":
        return MoveEvent(
            move=self.move.lower(),
            color=normalize_color(self.color),
            source=self.source,
            raw=self.raw,
            ply=self.ply,
        )


@dataclass
class ParsedResult:
    raw: str
    margin: Optional[int] = None
    flags: set[str] = field(default_factory=set)

    @property
    def is_disqualifying(self) -> bool:
        bad = {
            "r",
            "t",
            "s",
            "resign",
            "timeout",
            "mutual",
            "stored",
            "abort",
            "break",
        }
        return bool(self.flags & bad)


@dataclass
class MatchListing:
    match_id: str
    black_player: Optional[str] = None
    white_player: Optional[str] = None
    game_type: Optional[str] = None


@dataclass
class MatchState:
    match_id: str
    black_player: Optional[str] = None
    white_player: Optional[str] = None
    game_type: Optional[str] = None
    start_time: datetime = field(default_factory=utc_now)
    end_time: Optional[datetime] = None
    initial_board_64: Optional[str] = None
    initial_turn: Optional[str] = None
    move_events: list[MoveEvent] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)
    result_from_ggs: Optional[str] = None
    parsed_result: Optional[ParsedResult] = None
    terminal_notified: bool = False
    watching: bool = False
    finalised: bool = False

    @property
    def match_id_with_dot(self) -> str:
        return f".{self.match_id}" if not self.match_id.startswith(".") else self.match_id

    @property
    def initial_turn_or_default(self) -> str:
        turn = normalize_color(self.initial_turn)
        return turn or "black"

    @property
    def moves(self) -> list[str]:
        with_ply = all(event.ply is not None for event in self.move_events)
        if with_ply:
            ordered = sorted(self.move_events, key=lambda event: event.ply or 0)
            return [event.move for event in ordered]
        return [event.move for event in self.move_events]

    @property
    def moves_compact(self) -> str:
        return "".join(move for move in self.moves if move != "pass")

    def add_warning(self, message: str) -> None:
        self.parser_warnings.append(message)

    def append_raw(self, line: str) -> None:
        self.raw_lines.append(line)

    def update_identity(
        self,
        black_player: Optional[str] = None,
        white_player: Optional[str] = None,
        game_type: Optional[str] = None,
    ) -> None:
        if black_player and not self.black_player:
            self.black_player = black_player
        if white_player and not self.white_player:
            self.white_player = white_player
        if game_type and not self.game_type:
            self.game_type = game_type

    def set_initial_position(self, board_64: str, turn: Optional[str]) -> None:
        if not self.initial_board_64:
            self.initial_board_64 = board_64
        if turn:
            normalized = normalize_color(turn)
            if normalized:
                self.initial_turn = normalized

    def append_live_move(self, event: MoveEvent) -> bool:
        normalized = event.normalized()
        if normalized.ply is not None:
            for existing in self.move_events:
                if existing.ply != normalized.ply:
                    continue
                existing_norm = existing.normalized()
                same_color = (
                    existing_norm.color == normalized.color
                    or existing_norm.color is None
                    or normalized.color is None
                )
                if existing_norm.move == normalized.move and same_color:
                    return False
                self.add_warning(
                    f"conflicting move at ply {normalized.ply}: "
                    f"existing={existing_norm.move} incoming={normalized.move}"
                )
                return False
        if self.move_events:
            prev = self.move_events[-1].normalized()
            if prev.move == normalized.move and prev.color == normalized.color:
                return False
        self.move_events.append(normalized)
        return True

    def merge_snapshot_moves(self, events: list[MoveEvent]) -> None:
        if not events:
            return
        normalized = [event.normalized() for event in events]
        if not self.move_events:
            self.move_events.extend(normalized)
            return

        prefix = 0
        while prefix < len(self.move_events) and prefix < len(normalized):
            existing = self.move_events[prefix].normalized()
            incoming = normalized[prefix]
            if existing.move != incoming.move:
                break
            if existing.color and incoming.color and existing.color != incoming.color:
                break
            prefix += 1

        if prefix < len(self.move_events) and prefix < len(normalized):
            self.add_warning(
                f"moves snapshot diverged at ply {prefix + 1}; kept existing sequence"
            )
            return

        for event in normalized[prefix:]:
            self.append_live_move(event)

    def mark_terminal(self, result: Optional[ParsedResult]) -> None:
        self.terminal_notified = True
        self.end_time = utc_now()
        if result:
            self.parsed_result = result
            self.result_from_ggs = result.raw
