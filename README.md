# Auto Typing

A small local-first Windows desktop typing utility built with Python + PySide6.

> **Prototype / Phase 0:** Synthetic Win32 input has not yet been verified against a real UniKey installation. Test in Notepad with harmless sample text before using other applications.

## Modes

- **Clipboard Paste** — writes the source text to the system clipboard and sends Ctrl+V (one action).
- **Unicode Typing** — sends each Unicode code unit via `SendInput(KEYEVENTF_UNICODE)`; no UniKey required. A newline sends Enter.
- **Physical Typing** — sends per-key virtual-key press/release events; supports ASCII printable characters and newline.
- **Telex Typing (UniKey)** — converts Vietnamese Unicode to Telex keystrokes, then uses Physical Typing. Requires UniKey in Vietnamese/Telex mode, Unicode encoding, and Caps Lock off.

Examples: `Chào bạn` → `Chaof banj`, `Tiếng Việt` → `Tieengs Vieetj`, `Đường` → `Dduwowngf`.

**Limitations:** Telex is an input method, not a lossless character encoding. Latin-language words, URLs and code can be interpreted as Telex commands by the destination IME; mixed-language text is not guaranteed. Physical/Telex modes cannot inject emoji or arbitrary Unicode; use Unicode Typing or Clipboard Paste instead. Character mapping depends on the Windows keyboard layout and application. Elevated applications can reject input injected from a normal-permission process. Windows is currently the only supported injection backend.

## Run

Requires Windows 10/11 and Python 3.11+.

```powershell
uv sync
uv run auto-typing
```

Install dependencies and run tests (tests work on non-Windows systems because core logic is platform-independent):

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
```

## Usage

1. Enter your text, select a mode, and inspect the Telex preview when applicable.
2. Choose the start delay, interval (time between key starts), and key-hold duration.
3. Click **Start**, then focus the **destination window** before the countdown finishes.
4. Press **F8** while the utility is typing to request an emergency stop. The physical F8 keystroke may also reach the destination application. Alternatively return to the utility and press **Stop**.

### Safety and data handling

- Never use this utility to paste passwords or other secrets into an unintended window.
- The utility checks the target window before every keystroke and stops when foreground focus changes. This is best-effort, not an atomic operating-system security boundary.
- Newlines in keystroke modes send **Enter**, which may submit a chat message or form; the UI requests confirmation before proceeding.
- Clipboard Paste **overwrites the current clipboard** and does not automatically restore it in this prototype.
- Start, Stop and progress are managed on a worker thread so the desktop UI stays responsive. Stop is cooperative and currently checked between or during short waits.
- No text history, network synchronization, background listener or analytics service is included.

## Architecture

```text
src/auto_typing/
  core.py         # typing modes, validation, Unicode→Telex, immutable typing plans
  win_keyboard.py # Windows SendInput and target-window guard
  worker.py       # cancellable Qt worker, pacing and progress
  ui.py           # PySide6 main window
  main.py         # desktop entry point
tests/
  test_core.py    # pure converter/plan tests
```

## Next steps

Real-Windows acceptance testing with UniKey, automated integration testing, robust hotkey registration and clipboard restoration, application-level focus safeguards, Linux backends, and VNI conversion are follow-up work.
