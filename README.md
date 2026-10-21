# Auto Typing

A local-first Windows desktop typing utility built with Python + PySide6. Its dark, two-column workspace separates source text from typing settings, with a live keystroke preview and progress feedback.

> **Windows acceptance testing required:** The Win32 `SendInput` ABI-size bug that caused error 87 has been fixed, but real UniKey and target-application behavior still need manual verification. Test in Notepad with harmless sample text first.

## Modes

- **Clipboard Paste** — writes the source text to the system clipboard and sends Ctrl+V (one action).
- **Unicode Typing** — sends each Unicode code unit via `SendInput(KEYEVENTF_UNICODE)`; no UniKey required. A newline sends Enter.
- **Physical Typing** — sends per-key virtual-key press/release events; supports ASCII printable characters and newline.
- **Hybrid Typing (UniKey)** — for mixed English/Vietnamese: sends plain ASCII words as Unicode events (bypassing Telex shortcuts like `as`, `aw`, `dd`) and accented Vietnamese words as physical Telex keystrokes. Physical spaces, punctuation, and Enter separate word compositions. Other unsupported characters use Unicode events. Requires UniKey in Vietnamese/Telex mode, Unicode encoding, and Caps Lock off.

Examples: `Chào bạn` → physical Telex `Chaof banj`; `as` → Unicode `as` (not `á`); `Xin chào, I work as a developer.` → Unicode for `Xin`, `I work as a developer` and physical Telex for `chào`. Preview labels the actual **Keys** and **Unicode** action runs.

**Keyboard implementation:** Physical and Telex typing use `VkKeyScanExW` to map each ASCII character through the destination window's Windows keyboard layout. This avoids a brittle hardcoded mapping table or an additional PyAutoGUI dependency. Unicode typing uses native UTF-16 `SendInput` events (which PyAutoGUI's `write()` cannot replace). The `INPUT` union includes all Win32 variants to preserve the required 40-byte x64 / 28-byte x86 ABI size.

**Limitations:** The Hybrid planner chooses Telex for accented words it can convert and Unicode for plain ASCII/unsupported words. This is not language detection: some foreign words with overlapping accents (e.g. `café`) may be classified as Telex. Physical-only mode cannot inject emoji or arbitrary Unicode; Hybrid and Unicode Typing can attempt this with `KEYEVENTF_UNICODE`. Some target applications and IMEs handle `VK_PACKET`, composition boundaries or mixed keyboard/Unicode events differently, so **verify the output in Notepad with UniKey enabled before relying on mixed typing**. Character mapping depends on the Windows keyboard layout and application. Elevated applications can reject input injected from a normal-permission process. Windows is currently the only supported injection backend.

## Download Windows v1.0.0

Download **AutoTyping-v1.0.0-windows-x64.exe** from the [latest GitHub Release](https://github.com/truong51972/auto-typing/releases/latest), then launch it on Windows 10/11 (x64). This is a portable executable: **Python, uv and an installer are not required**.

The release includes `SHA256SUMS.txt` for verifying the download. The binary is **not code-signed**, so SmartScreen may show a warning. Check its source and integrity before running it. Because automated smoke tests cannot validate real UniKey interactions, test the typing modes in Notepad before using the application elsewhere.

### Building and publishing a new version

Pull requests and pushes to `main` build a Windows executable using `windows-latest`, PyInstaller `--onefile --windowed`, and an offscreen GUI smoke test. Build artifacts are retained in GitHub Actions for 14 days.

After merging a version bump into `main`, the workflow automatically publishes the corresponding `vX.Y.Z` GitHub Release (creating the matching tag if necessary) and attaches the EXE and its SHA-256 checksum. Existing releases are not overwritten. Alternatively, pushing a version-matched `vX.Y.Z` tag will build and publish that version.

For local Windows packaging:

```powershell
uv sync --no-dev --group build
uv run --no-dev --group build pyinstaller --noconfirm --clean --onefile --windowed --name AutoTyping --paths src scripts/auto_typing_entry.py
```

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

1. Enter your text, select a mode, and inspect the **Hybrid action preview** when applicable. It shows which spans are sent as physical **Keys** versus **Unicode**. Invalid input is explained inline and **Start** is disabled until the selected mode can represent it.
   - Choose **Normalize text** if the source contains decomposed accents, copy/pasted spacing, tabs, or smart punctuation incompatible with Physical/Telex typing. Changes are opt-in and can be undone in the editor.
   - Choose **Use Unicode** from **Physical Typing** when a character cannot be represented with physical keys. **Hybrid Typing** automatically falls back to Unicode for unsupported words, symbols, and emoji; no characters are intentionally dropped.
   - Normalization uses Unicode NFC, and NFKC for physical/Telex compatibility where appropriate; review the updated text because compatibility normalization can change typographic presentation.
2. Choose the start delay, interval (time between key starts), and key-hold duration. The **Typing settings** panel scrolls vertically when the window is small, keeping **Start** and **Stop** visible.
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
  core.py         # typing modes, validation, Unicode/Telex action-based typing plans
  win_keyboard.py # Windows SendInput and target-window guard
  worker.py       # cancellable Qt worker, pacing and progress
  ui.py           # PySide6 main window
  main.py         # desktop entry point
tests/
  test_core.py          # pure converter/plan tests
  test_win_keyboard.py  # INPUT ABI and synthetic-event tests
  test_ui.py            # UI validation, normalization and responsive layout tests
  test_worker.py        # fake-keyboard hybrid dispatch and progress tests
```

## Next steps

Real-Windows acceptance testing with UniKey, automated integration testing, robust hotkey registration and clipboard restoration, application-level focus safeguards, Linux backends, and VNI conversion are follow-up work.
