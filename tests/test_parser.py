from __future__ import annotations

from ggs_parser import parse_stream_line


def test_ggf_tokens_parse() -> None:
    line = (
        ".78665 GGF BO[---------------------------OX------XO---------------------------] "
        "B[F5//1.23] W[D6/0.5/0.1] B[pass//0.68] RE[+2.00]"
    )
    parsed = parse_stream_line(line)
    assert "78665" in parsed.match_ids
    assert parsed.initial_board_64 is not None
    assert len(parsed.initial_board_64) == 64
    assert [move.move for move in parsed.moves] == ["f5", "d6", "pass"]
    assert [move.color for move in parsed.moves] == ["black", "white", "black"]
    assert parsed.result is not None
    assert parsed.result.margin == 2
    assert not parsed.result.is_disqualifying


def test_resign_result_is_disqualifying() -> None:
    parsed = parse_stream_line(".90000 RE[-64.00:r]")
    assert parsed.result is not None
    assert parsed.result.is_disqualifying
    assert "r" in parsed.result.flags


def test_match_row_parsing_single_digit_id() -> None:
    line = "|  .2 2664 nyanyan  2562 egrcd       s8r14  R 0"
    parsed = parse_stream_line(line)
    assert "2" in parsed.match_ids
    assert parsed.listings
    listing = parsed.listings[0]
    assert listing.match_id == "2"
    assert listing.black_player == "nyanyan"
    assert listing.white_player == "egrcd"
    assert listing.game_type == "s8r14"


def test_update_end_and_board_parsing() -> None:
    update = parse_stream_line("/os: update .31.0 s8r14 K?")
    assert update.context_match_id == "31.0"
    assert update.context_kind == "update"
    assert "31.0" in update.match_ids
    assert update.game_type == "s8r14"

    joined = parse_stream_line("/os: join .31.0 s8r14 K?")
    assert joined.context_match_id == "31.0"
    assert joined.context_kind == "join"

    move_line = parse_stream_line("| 49: PA/-2.00")
    assert len(move_line.moves) == 1
    assert move_line.moves[0].move == "pass"
    assert move_line.moves[0].ply == 49

    board = parse_stream_line("| 3 - * - * * * - - 3 ")
    assert board.board_row_index == 3
    assert board.board_row_8 == "-X-XXX--"

    to_move = parse_stream_line("|* to move")
    assert to_move.initial_turn == "black"

    player = parse_stream_line("|egrcd    (2556.5 *) 00:02,25:0//00:00,25:0")
    assert player.player_name == "egrcd"
    assert player.player_color == "black"

    ended = parse_stream_line("/os: end .31.1 ( nyanyan vs. egrcd ) +2.00")
    assert ended.context_match_id == "31.1"
    assert ended.context_kind == "end"
    assert ended.result is not None
    assert ended.result.margin == 2
