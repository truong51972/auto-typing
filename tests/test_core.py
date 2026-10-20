"""Tests for the platform-independent converter and typing planner."""

import pytest

from auto_typing.core import TypingMode, build_plan, normalize_source_text, to_telex


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("Chào bạn", "Chaof banj"),
        ("Tiếng Việt", "Tieengs Vieetj"),
        ("Đường", "Dduwowngf"),
        ("Việt Nam", "Vieetj Nam"),
        ("Xin chào", "Xin chaof"),
        ("Quốc gia", "Quoocs gia"),
        ("Áo", "Aos"),
        ("Tôi", "Tooi"),
        ("Tôi yêu Việt Nam.", "Tooi yeeu Vieetj Nam."),
        ("", ""),
    ],
)
def test_telex_examples(original: str, expected: str) -> None:
    assert to_telex(original) == expected


def test_telex_nfd_equivalence() -> None:
    import unicodedata

    assert to_telex(unicodedata.normalize("NFD", "Đường")) == "Dduwowngf"


def test_telex_does_not_drop_spacing_and_newlines() -> None:
    assert to_telex("Chào,\nbạn!") == "Chaof,\nbanj!"


def test_unsupported_diacritic_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="Unsupported mark"):
        to_telex("naïve")


def test_foreign_words_can_collide_with_telex() -> None:
    # "é" is a valid Vietnamese accented e, but not necessarily Vietnamese text.
    assert to_telex("café") == "cafes"


def test_multiple_tone_marks_in_one_word_fails() -> None:
    with pytest.raises(ValueError, match="Multiple"):
        to_telex("ấằ")


def test_plan_is_frozen_and_counts_telex_keys() -> None:
    plan = build_plan("Chào bạn", TypingMode.TELEX)
    assert plan.keys == tuple("Chaof banj")
    assert plan.count == 10
    assert plan.original_text == "Chào bạn"


def test_paste_preserves_unicode_and_has_one_action() -> None:
    plan = build_plan("Chào 😊", TypingMode.PASTE)
    assert plan.payload == "Chào 😊"
    assert plan.keys == ()
    assert plan.count == 1


def test_unicode_mode_supports_emoji() -> None:
    plan = build_plan("Chào 😊", TypingMode.UNICODE)
    assert plan.keys[-1] == "😊"


@pytest.mark.parametrize("mode", [TypingMode.PHYSICAL, TypingMode.TELEX])
def test_keystroke_modes_reject_emoji(mode: TypingMode) -> None:
    with pytest.raises(ValueError, match="cannot type"):
        build_plan("Hi 😊", mode)


@pytest.mark.parametrize("mode", list(TypingMode))
def test_empty_input_is_rejected(mode: TypingMode) -> None:
    with pytest.raises(ValueError, match="Enter some text"):
        build_plan("", mode)


def test_newlines_are_normalized() -> None:
    assert build_plan("A\r\nB\rC", TypingMode.PHYSICAL).keys == tuple("A\nB\nC")


def test_tab_is_rejected_in_keystroke_modes() -> None:
    with pytest.raises(ValueError, match="Control characters"):
        build_plan("A\tB", TypingMode.UNICODE)


@pytest.mark.parametrize(
    ("source", "mode", "expected"),
    [
        ("Cha\u0300o ba\u0323n", TypingMode.TELEX, "Chào bạn"),
        ("Chào\u00a0bạn", TypingMode.TELEX, "Chào bạn"),
        ("Chào\u200bbạn", TypingMode.TELEX, "Chàobạn"),
        ("Hello\tworld", TypingMode.UNICODE, "Hello    world"),
        ("“Hello” — world…", TypingMode.PHYSICAL, '"Hello" - world...'),
        ("ＡＢＣ１２３", TypingMode.PHYSICAL, "ABC123"),
        ("Hi 😊", TypingMode.TELEX, "Hi 😊"),
        ("“Hello” — world…", TypingMode.UNICODE, "“Hello” — world…"),
        ("Hello\tworld", TypingMode.PASTE, "Hello\tworld"),
    ],
)
def test_normalize_source_text(source: str, mode: TypingMode, expected: str) -> None:
    assert normalize_source_text(source, mode) == expected


def test_normalization_is_idempotent() -> None:
    source = "“Chào\u00a0bạn” …"
    first = normalize_source_text(source, TypingMode.TELEX)
    assert normalize_source_text(first, TypingMode.TELEX) == first
    assert build_plan(first, TypingMode.TELEX).payload == '"Chaof banj" ...'


def test_unsupported_letters_are_not_silently_transliterated() -> None:
    normalized = normalize_source_text("Zażółć 😊", TypingMode.TELEX)
    assert normalized == "Zażółć 😊"
    with pytest.raises(ValueError):
        build_plan(normalized, TypingMode.TELEX)
    assert build_plan(normalized, TypingMode.UNICODE).original_text == normalized
