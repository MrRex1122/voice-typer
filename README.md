# Voice Typer

Local voice dictation into the active window using faster-whisper (Whisper `base`). No cloud, no telemetry.

## Features

- F12 or Numpad 0 as toggle hotkey (both blocked at the OS level so they do not leak into the focused app)
- Local inference with faster-whisper `base` (~140 MB download on first run)
- Auto-selects the Ugreen microphone by name, falls back to the default input device
- System tray icon: enable, autostart on Windows login, quit
- Audio feedback: high beep on record start, low beep on record stop
- Single-instance lock — duplicate launches exit silently
- Logs to `%USERPROFILE%\voice_typer.log`

## Requirements

- Windows 10 / 11
- Python 3.10+ (tested on 3.12)
- A microphone

## Install and run

Double-click `run.bat` (or run it from cmd). It will:

1. Create a `.venv` if missing
2. Install dependencies from `requirements.txt`
3. Launch the app with `pythonw.exe` (no console window)

The first run downloads the `base` Whisper model (~140 MB) into the Hugging Face cache.

## Usage

1. Place the cursor in any text field
2. Press **F12** — high beep, recording starts
3. Speak
4. Press **F12** again — low beep, recognized text is typed into the active window

Numpad 0 works as an alternative.

## Tray menu

Right-click the tray icon (bottom-right of the taskbar; on Windows 11 it may be hidden behind the `˄` overflow button):

- **Enabled** — toggle reaction to the hotkey
- **Autostart (Windows)** — add or remove from Windows startup
- **Quit**

## Logs

`%USERPROFILE%\voice_typer.log`

## Troubleshooting

If the hotkey does not respond:

1. Open `diagnose.py` (run it manually from the venv) and press the key — it will log the raw event to `diagnose.log` with its `vk` and `name`. This tells you whether events reach the hook and what identifiers pynput exposes for that key on your keyboard.

## Configuration

In `voice_typer.py`:

- `MODEL_SIZE` — `"tiny"` (faster) or `"base"` (more accurate, slower)
- `MIC_HINT` — substring used to pick the right input device
- `TOGGLE_SCAN_CODES` — scan codes of the blocked/detected hotkeys
- `DEBOUNCE_S` — minimum delay between two toggle presses

## License

MIT
