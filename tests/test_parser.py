from __future__ import annotations

from parser import parse_stream_line


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

