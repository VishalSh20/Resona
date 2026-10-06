"""Deterministic quote check (spec §5.1)."""

from __future__ import annotations

from voiceeval.judging.evidence.quote_check import (
    normalize,
    quote_in_transcript,
    validate_item,
)


def test_normalize_strips_punctuation_and_case():
    assert normalize("Hello,   World!!") == "hello world"


def test_quote_in_transcript_latin():
    transcript = "I need to change my booking date."
    assert quote_in_transcript("change my booking", transcript)
    assert not quote_in_transcript("cancel my booking", transcript)


def test_quote_in_transcript_devanagari():
    transcript = "मुझे अपनी बुकिंग बदलनी है"
    assert quote_in_transcript("अपनी बुकिंग", transcript)
    assert not quote_in_transcript("मेरा नाम", transcript)


def test_validate_item_flags_missing_and_unknowns():
    ok, reason = validate_item(
        quote="", turn_ids=[1], transcript="x", known_turn_ids={1}
    )
    assert not ok and reason == "missing_quote"

    ok, reason = validate_item(
        quote="x", turn_ids=[9], transcript="x", known_turn_ids={1}
    )
    assert not ok and reason == "unknown_turn_id"

    ok, reason = validate_item(
        quote="hello", turn_ids=[1], transcript="say hello now", known_turn_ids={1}
    )
    assert ok and reason is None
