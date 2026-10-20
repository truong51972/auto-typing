"""Pure text conversion and typing-plan construction (no OS or Qt dependency)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum


class TypingMode(str, Enum):
    PASTE = "paste"
    UNICODE = "unicode"
    PHYSICAL = "physical"
    TELEX = "telex"


_TONE_MARKS = {
    "\u0301": "s",  # acute
    "\u0300": "f",  # grave
    "\u0309": "r",  # hook above
    "\u0303": "x",  # tilde
    "\u0323": "j",  # dot below
}
_VOWEL_MARKS = {
    "\u0302": {"a": "aa", "e": "ee", "o": "oo"},  # circumflex
    "\u0306": {"a": "aw"},  # breve
    "\u031b": {"o": "ow", "u": "uw"},  # horn
}


def _to_telex_word(word: str) -> str:
    result: list[str] = []
    tone: str | None = None

    for char in word:
        if char == "đ":
            result.append("dd")
            continue
        if char == "Đ":
            result.append("Dd")
            continue

        decomposed = unicodedata.normalize("NFD", char)
        base, marks = decomposed[0], decomposed[1:]
        if not (base.isascii() and base.isalpha()):
            raise ValueError(f"Cannot convert {char!r} to Telex; use Unicode/Paste mode")

        typed = base
        for mark in marks:
            if mark in _TONE_MARKS:
                if tone is not None:
                    raise ValueError(f"Multiple Vietnamese tone marks in {word!r}")
                tone = _TONE_MARKS[mark]
            elif mark in _VOWEL_MARKS and base.lower() in _VOWEL_MARKS[mark]:
                expanded = _VOWEL_MARKS[mark][base.lower()]
                typed = expanded.capitalize() if base.isupper() else expanded
            else:
                raise ValueError(f"Unsupported mark in {char!r}; use Unicode/Paste mode")
        result.append(typed)

    return "".join(result) + (tone or "")


def to_telex(text: str) -> str:
    """Convert Vietnamese words to Telex keystroke text, placing tone at word end.

    The result is a best-effort IME input sequence, not a universally reversible encoding.
    """
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    word: list[str] = []

    def flush_word() -> None:
        if word:
            out.append(_to_telex_word("".join(word)))
            word.clear()

    for char in text:
        if char.isalpha():
            word.append(char)
        else:
            flush_word()
            out.append(char)

    flush_word()
    return "".join(out)



# Explicit, opt-in cleanup for characters commonly introduced by copy/paste.
# These changes are deliberately conservative: unsupported letters/emoji remain
# untouched so the UI can offer Unicode mode instead of silently dropping data.
_SPACE_TRANSLATION = str.maketrans({
    "\u00a0": " ",  # non-breaking space
    "\u2007": " ",  # figure space
    "\u202f": " ",  # narrow no-break space
    "\u200b": "",   # zero-width space
    "\ufeff": "",   # byte-order mark within pasted text
})
_ASCII_PUNCTUATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2026": "...",
})


def normalize_source_text(text: str, mode: TypingMode) -> str:
    """Prepare pasted text for a typing mode without transliterating or losing letters.

    The user must explicitly request this transformation in the UI.
    Characters that cannot be represented by Physical/Telex (e.g., emoji and
    foreign-language diacritics) remain intact for proper validation.
    """
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    if mode == TypingMode.PASTE:
        return normalized
    normalized = normalized.translate(_SPACE_TRANSLATION).replace("\t", "    ")
    if mode in (TypingMode.PHYSICAL, TypingMode.TELEX):
        normalized = unicodedata.normalize("NFKC", normalized)
        normalized = normalized.translate(_ASCII_PUNCTUATION)
    return normalized


class TypingActionKind(str, Enum):
    """Backend input method for one action, independent of the selected UI mode."""

    PHYSICAL = "physical"
    UNICODE = "unicode"
    PASTE = "paste"


@dataclass(frozen=True)
class TypingAction:
    kind: TypingActionKind
    value: str


@dataclass(frozen=True)
class TypingPlan:
    mode: TypingMode
    original_text: str
    payload: str
    actions: tuple[TypingAction, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        """Compatibility accessor for the flattened stream of intended key values."""
        return () if self.mode == TypingMode.PASTE else tuple(self.payload)

    @property
    def count(self) -> int:
        return len(self.actions)


def _hybrid_actions(text: str) -> tuple[TypingAction, ...]:
    """Convert accented Vietnamese words to Telex keys; bypass IME for English.

    ASCII words and unsupported foreign-language words use VK_PACKET/Unicode,
    so 'as', 'aw', or 'dd' are never sent to UniKey as Telex commands.
    Separators use physical keys where possible to delimit IME compositions.
    """
    actions: list[TypingAction] = []
    word: list[str] = []

    def flush_word() -> None:
        if not word:
            return
        original = "".join(word)
        word.clear()
        if original.isascii():
            kind, output = TypingActionKind.UNICODE, original
        else:
            try:
                output = _to_telex_word(original)
                kind = TypingActionKind.PHYSICAL
            except ValueError:
                # Never transliterate foreign words or silently drop characters.
                kind, output = TypingActionKind.UNICODE, original
        actions.extend(TypingAction(kind, char) for char in output)

    for char in unicodedata.normalize("NFC", text):
        if char.isalpha():
            word.append(char)
            continue

        flush_word()
        if char == "\n" or (" " <= char <= "~"):
            actions.append(TypingAction(TypingActionKind.PHYSICAL, char))
        else:
            actions.append(TypingAction(TypingActionKind.UNICODE, char))
    flush_word()
    return tuple(actions)


def build_plan(text: str, mode: TypingMode) -> TypingPlan:
    """Validate and freeze the input actions before switching destination focus."""
    if not text:
        raise ValueError("Enter some text before starting")

    clean_text = text.replace("\r\n", "\n").replace("\r", "\n")

    if mode == TypingMode.PASTE:
        return TypingPlan(
            mode=mode,
            original_text=clean_text,
            payload=clean_text,
            actions=(TypingAction(TypingActionKind.PASTE, ""),),
        )

    for char in clean_text:
        if char == "\n":
            continue
        if char in ("\x00", "\t") or unicodedata.category(char).startswith("C"):
            raise ValueError("Control characters and tabs are unsupported in typing modes")
        if mode == TypingMode.PHYSICAL and not (" " <= char <= "~"):
            raise ValueError(
                f"Physical mode cannot type {char!r}; use Unicode/Hybrid/Paste mode"
            )

    if mode == TypingMode.TELEX:
        actions = _hybrid_actions(clean_text)
    else:
        kind = (
            TypingActionKind.PHYSICAL
            if mode == TypingMode.PHYSICAL
            else TypingActionKind.UNICODE
        )
        actions = tuple(TypingAction(kind, char) for char in clean_text)

    payload = "".join(action.value for action in actions)
    return TypingPlan(
        mode=mode, original_text=clean_text, payload=payload, actions=actions
    )


def format_action_preview(plan: TypingPlan, max_chars: int = 240) -> str:
    """Preview actual input methods in the mixed plan without leaking markup."""
    if plan.mode == TypingMode.PASTE:
        return "(Clipboard paste: original Unicode text)"
    if plan.mode != TypingMode.TELEX:
        return plan.payload[:max_chars] + ("…" if len(plan.payload) > max_chars else "")

    groups: list[tuple[TypingActionKind, str]] = []
    for action in plan.actions:
        visible = action.value.replace("\n", "↵")
        if groups and groups[-1][0] == action.kind:
            previous_kind, previous_text = groups[-1]
            groups[-1] = (previous_kind, previous_text + visible)
        else:
            groups.append((action.kind, visible))

    labels = {
        TypingActionKind.PHYSICAL: "Keys",
        TypingActionKind.UNICODE: "Unicode",
        TypingActionKind.PASTE: "Paste",
    }
    result = "  |  ".join(f"[{labels[kind]}] {value}" for kind, value in groups)
    return result[:max_chars] + ("…" if len(result) > max_chars else "")
