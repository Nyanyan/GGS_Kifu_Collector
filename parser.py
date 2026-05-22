from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from models import MatchListing, MoveEvent, ParsedResult, normalize_color

MATCH_ID_RE = re.compile(r"\.(\d{3,})")
GGF_TOKEN_RE = re.compile(r"([A-Z]{1,2})\[([^\]]*)\]")
COORD_RE = re.compile(r"^[A-Ha-h][1-8]$")
SIDE_TO_MOVE_RE = re.compile(
    r"\b(?:to move|turn|side to move)\s*[:=]?\s*(black|white|b|w)\b",
    re.IGNORECASE,
)
PLAYER_PAIR_PATTERNS = (
    re.compile(
        r"(?P<black>[A-Za-z0-9_+\-]+)\s+vs\.?\s+(?P<white>[A-Za-z0-9_+\-]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<black>[A-Za-z0-9_+\-]+)\s*-\s*(?P<white>[A-Za-z0-9_+\-]+)",
        re.IGNORECASE,
    ),
)
GAME_TYPE_RE = re.compile(r"\b([a-z][a-z0-9]*\d+(?:r\d+)?)\b", re.IGNORECASE)
PLAIN_RESULT_KEYWORDS = {
    "resign": {"r", "resign"},
    "resigned": {"r", "resign"},
    "timeout": {"t", "timeout"},
    "time out": {"t", "timeout"},
    "mutual score": {"s", "mutual"},
    "stored": {"stored"},
    "abort": {"abort"},
    "break": {"break"},
}


@dataclass(slots=True)
class ParsedLine:
    match_ids: set[str] = field(default_factory=set)
    listings: list[MatchListing] = field(default_factory=list)
    game_type: Optional[str] = None
    initial_board_64: Optional[str] = None
    initial_turn: Optional[str] = None
    moves: list[MoveEvent] = field(default_factory=list)
    result: Optional[ParsedResult] = None
    warnings: list[str] = field(default_factory=list)
    snapshot_like: bool = False


def normalize_match_id(match_id: str) -> str:
    value = match_id.strip()
    if value.startswith("."):
        value = value[1:]
    return value


def extract_match_ids(text: str) -> set[str]:
    return {normalize_match_id(match_id) for match_id in MATCH_ID_RE.findall(text)}


def _normalize_board_token(content: str) -> Optional[str]:
    stones = []
    for char in content:
        if char in {"X", "x", "*"}:
            stones.append("X")
        elif char in {"O", "o"}:
            stones.append("O")
        elif char in {"-", "."}:
            stones.append("-")
    if len(stones) < 64:
        return None
    return "".join(stones[:64])


def _parse_result_token(content: str) -> ParsedResult:
    raw = content.strip()
    parts = raw.split(":")
    main = parts[0].strip()
    flags: set[str] = set()
    margin: Optional[int] = None

    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", main):
        margin = int(round(float(main)))

    for part in parts[1:]:
        token = part.strip().lower()
        if not token:
            continue
        if all(char in {"r", "t", "s", ",", ";", "/"} for char in token):
            flags.update({char for char in token if char in {"r", "t", "s"}})
        if "resign" in token:
            flags.add("resign")
            flags.add("r")
        if token == "r":
            flags.add("r")
        if "timeout" in token:
            flags.add("timeout")
            flags.add("t")
        if token == "t":
            flags.add("t")
        if "mutual" in token:
            flags.add("mutual")
            flags.add("s")
        if token == "s":
            flags.add("s")
        if "stored" in token:
            flags.add("stored")
        if "abort" in token:
            flags.add("abort")
        if "break" in token:
            flags.add("break")

    return ParsedResult(raw=raw, margin=margin, flags=flags)


def _move_from_token(tag: str, content: str) -> Optional[MoveEvent]:
    first = content.split("/", 1)[0].strip()
    color = "black" if tag == "B" else "white"
    if first.lower() == "pass":
        return MoveEvent(move="pass", color=color, source="ggf")
    if COORD_RE.fullmatch(first):
        return MoveEvent(move=first.lower(), color=color, source="ggf")
    return None


def _extract_game_type(text: str) -> Optional[str]:
    for match in GAME_TYPE_RE.findall(text):
        token = match.lower()
        if COORD_RE.fullmatch(token):
            continue
        return token
    return None


def _extract_players(text: str) -> tuple[Optional[str], Optional[str]]:
    for pattern in PLAYER_PAIR_PATTERNS:
        found = pattern.search(text)
        if found:
            return found.group("black"), found.group("white")
    return None, None


def parse_stream_line(line: str) -> ParsedLine:
    parsed = ParsedLine()
    parsed.match_ids = extract_match_ids(line)
    parsed.game_type = _extract_game_type(line)

    side = SIDE_TO_MOVE_RE.search(line)
    if side:
        parsed.initial_turn = normalize_color(side.group(1))

    black_player, white_player = _extract_players(line)
    if parsed.match_ids and (black_player or white_player or parsed.game_type):
        for match_id in parsed.match_ids:
            parsed.listings.append(
                MatchListing(
                    match_id=match_id,
                    black_player=black_player,
                    white_player=white_player,
                    game_type=parsed.game_type,
                )
            )

    tokens = GGF_TOKEN_RE.findall(line)
    if tokens:
        if len(tokens) > 1:
            parsed.snapshot_like = True
        for tag, content in tokens:
            if tag == "BO":
                board = _normalize_board_token(content)
                if board:
                    parsed.initial_board_64 = board
                else:
                    parsed.warnings.append("invalid BO token length")
            elif tag in {"B", "W"}:
                move = _move_from_token(tag, content)
                if move:
                    parsed.moves.append(move)
                else:
                    parsed.warnings.append(f"invalid {tag}[...] move token: {content}")
            elif tag == "RE":
                parsed.result = _parse_result_token(content)
            elif tag == "PL":
                parsed.initial_turn = normalize_color(content)
            elif tag in {"PB", "PW"}:
                # Placeholders: player names are often also in non-GGF lines.
                continue

    if not parsed.result:
        lower = line.lower()
        result_flags: set[str] = set()
        for keyword, flags in PLAIN_RESULT_KEYWORDS.items():
            if keyword in lower:
                result_flags.update(flags)
        if result_flags:
            parsed.result = ParsedResult(raw=line.strip(), flags=result_flags)

    return parsed


def is_random_game_type(game_type: Optional[str]) -> bool:
    if not game_type:
        return False
    token = game_type.lower()
    match = re.search(r"r(\d+)", token)
    if not match:
        return False
    stones = int(match.group(1))
    return stones not in {0, 4}


def is_standard_like_game_type(game_type: Optional[str]) -> bool:
    if not game_type:
        return False
    return not is_random_game_type(game_type)
