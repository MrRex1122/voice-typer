import sys
import os
import time
import threading
import logging
import traceback
import winsound
from pathlib import Path

import numpy as np
import sounddevice as sd
import keyboard
from pynput import keyboard as pkb
from pynput.keyboard import Controller
from faster_whisper import WhisperModel
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw


SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_DURATION_S = 0.1
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION_S)
MODEL_SIZE = "tiny"
TOGGLE_SCAN_CODES = (82, 88)
DEBOUNCE_S = 0.3
MIN_AUDIO_S = 0.3
APP_NAME = "VoiceTyper"
AUTOSTART_REG = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_VALUE = "VoiceTyper"
LOG_PATH = Path.home() / "voice_typer.log"
MIC_HINT = "ugreen"


def log(msg):
    logging.info(msg)


def log_error(msg):
    logging.error(msg)
    logging.error(traceback.format_exc())


logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

try:
    import msvcrt
    _lock_path = Path.home() / ".voice_typer.lock"
    _lock_fd = open(_lock_path, "w")
    try:
        msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        log("another instance already running, exiting")
        _lock_fd.close()
        sys.exit(0)
except Exception as exc:
    log_error(f"single-instance lock failed: {exc}")

try:
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
except Exception:
    log_error("failed to load whisper model")
    raise

controller = Controller()

state = {
    "recording": False,
    "chunks": [],
    "stream": None,
    "last_toggle_at": 0.0,
    "enabled": True,
}

icon_ref = {"icon": None}
listener_ref = {"listener": None}


def find_input_device():
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        name = dev["name"].lower()
        if MIC_HINT in name and dev["max_input_channels"] > 0:
            return idx, dev["name"]
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            return idx, dev["name"]
    raise RuntimeError("no input audio device found")


def start_recording():
    state["chunks"] = []
    chunks_ref = state["chunks"]

    def callback(indata, frames, time_info, status):
        if status:
            log(f"audio status: {status}")
        chunks_ref.append(bytes(indata))

    try:
        idx, name = find_input_device()
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            callback=callback,
            device=idx,
        )
    except Exception as exc:
        log_error(f"mic open failed: {exc}")
        return
    stream.start()
    state["stream"] = stream
    state["recording"] = True
    log(f"recording started: {name}")
    beep_start()
    refresh_icon()


def stop_recording_and_type():
    stream = state["stream"]
    state["recording"] = False
    if stream is not None:
        stream.stop()
        stream.close()
        state["stream"] = None
    beep_stop()

    if not state["chunks"]:
        log("no audio captured")
        refresh_icon()
        return

    audio_bytes = b"".join(state["chunks"])
    state["chunks"] = []
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    if audio.size < SAMPLE_RATE * MIN_AUDIO_S:
        log("audio too short")
        refresh_icon()
        return

    def worker():
        try:
            segments, info = model.transcribe(
                audio,
                language=None,
                beam_size=1,
                vad_filter=True,
            )
            log(f"lang={info.language} prob={info.language_probability:.2f}")
            text = "".join(seg.text for seg in segments).strip()
            if text:
                log(f"text: {text}")
                controller.type(text)
            else:
                log("empty transcription")
        except Exception as exc:
            log_error(f"transcribe error: {exc}")
        refresh_icon()

    threading.Thread(target=worker, daemon=True).start()


def _on_key_event(key):
    vk = getattr(key, "vk", None)
    name = getattr(key, "name", None)
    if vk == 96 or name == "f12":
        log(f"hotkey detected (vk={vk} name={name})")
        toggle_recording()
    return True


def toggle_recording():
    if not state["enabled"]:
        log("toggle ignored: disabled")
        return
    now = time.monotonic()
    if now - state["last_toggle_at"] < DEBOUNCE_S:
        log("toggle ignored: debounce")
        return
    state["last_toggle_at"] = now
    if state["recording"]:
        stop_recording_and_type()
    else:
        start_recording()


def beep_start():
    try:
        winsound.Beep(880, 150)
    except Exception:
        pass


def beep_stop():
    try:
        winsound.Beep(440, 150)
    except Exception:
        pass


def autostart_command():
    pyexe = Path(sys.executable)
    pyw = pyexe.with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else pyexe)
    script = str(Path(__file__).resolve())
    return f'"{exe}" "{script}"'


def is_autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG) as key:
            try:
                winreg.QueryValueEx(key, AUTOSTART_VALUE)
                return True
            except FileNotFoundError:
                return False
    except Exception as exc:
        log_error(f"autostart query error: {exc}")
        return False


def set_autostart(enabled):
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTOSTART_REG,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, AUTOSTART_VALUE, 0, winreg.REG_SZ, autostart_command()
                )
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_VALUE)
                except FileNotFoundError:
                    pass
    except Exception as exc:
        log_error(f"autostart set error: {exc}")


def make_icon_image():
    if state["recording"]:
        bg, dot = (180, 30, 30), (255, 255, 255)
    elif state["enabled"]:
        bg, dot = (30, 130, 60), (255, 255, 255)
    else:
        bg, dot = (90, 90, 90), (200, 200, 200)
    img = Image.new("RGB", (64, 64), color=bg)
    draw = ImageDraw.Draw(img)
    draw.ellipse((16, 16, 48, 48), fill=dot)
    draw.rectangle((28, 28, 36, 40), fill=bg)
    return img


def refresh_icon():
    icon = icon_ref["icon"]
    if icon is not None:
        try:
            icon.icon = make_icon_image()
        except Exception:
            pass


def on_toggle_enabled(_icon, _item):
    state["enabled"] = not state["enabled"]
    log(f"enabled={state['enabled']}")
    refresh_icon()


def on_toggle_autostart(_icon, _item):
    new_val = not is_autostart_enabled()
    set_autostart(new_val)
    log(f"autostart set to {new_val}")


def on_quit(_icon, _item):
    if state["stream"] is not None:
        try:
            state["stream"].stop()
            state["stream"].close()
        except Exception:
            pass
    log("quit requested")
    listener = listener_ref["listener"]
    if listener is not None:
        try:
            listener.stop()
        except Exception:
            pass
    icon = icon_ref["icon"]
    if icon is not None:
        icon.stop()


def build_menu():
    return Menu(
        MenuItem(
            "Включен",
            on_toggle_enabled,
            checked=lambda _item: state["enabled"],
        ),
        MenuItem(
            "Автозапуск (Windows)",
            on_toggle_autostart,
            checked=lambda _item: is_autostart_enabled(),
        ),
        MenuItem("Выход", on_quit),
    )


def main():
    log("=== voice typer start ===")
    try:
        idx, name = find_input_device()
        log(f"mic selected: {name} (idx={idx})")
    except Exception as exc:
        log_error(f"mic init error: {exc}")

    ic = None
    try:
        menu = build_menu()
        ic = Icon(APP_NAME, make_icon_image(), APP_NAME, menu)
        icon_ref["icon"] = ic
        log("tray icon created")
    except Exception as exc:
        log_error(f"tray icon error: {exc}")
        return

    try:
        for sc in TOGGLE_SCAN_CODES:
            keyboard.block_key(sc)
        log(f"blocked scan_codes: {TOGGLE_SCAN_CODES}")
    except Exception as exc:
        log_error(f"block_key failed: {exc}")

    try:
        listener = pkb.Listener(on_press=_on_key_event, suppress=False)
        listener.start()
        listener_ref["listener"] = listener
        log("pynput listener started, F12 + numpad 0 handled via callback")
    except Exception as exc:
        log_error(f"listener error: {exc}")
        return

    log("entering tray message loop on main thread")
    try:
        ic.run()
    except Exception as exc:
        log_error(f"tray run error: {exc}")
    log("tray loop exited")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_error("fatal in main")
        raise