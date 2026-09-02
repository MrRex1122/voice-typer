from pynput import keyboard
import time
import queue
import threading
import sys
import traceback

LOG = r"C:\Users\evgen\OpenCode\voice-typer\diagnose.log"
ERR = r"C:\Users\evgen\OpenCode\voice-typer\diagnose.err"
events = queue.Queue()
stop_flag = threading.Event()


def clear_log():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"=== diagnose start {time.strftime('%H:%M:%S')} ===\n")


def write_err(prefix, exc):
    with open(ERR, "a", encoding="utf-8") as f:
        f.write(f"{prefix}\n{traceback.format_exc()}\n")


def on_press(key):
    try:
        vk = getattr(key, "vk", None)
        name = getattr(key, "char", None) or getattr(key, "name", None) or str(key)
        events.put(("DOWN", vk, name))
    except Exception as exc:
        write_err("on_press crash", exc)


def on_release(key):
    try:
        vk = getattr(key, "vk", None)
        name = getattr(key, "char", None) or getattr(key, "name", None) or str(key)
        events.put(("UP", vk, name))
    except Exception as exc:
        write_err("on_release crash", exc)


def writer():
    end = time.time() + 30
    while not stop_flag.is_set():
        try:
            ev = events.get(timeout=0.5)
        except queue.Empty:
            if time.time() > end:
                break
            continue
        kind, vk, name = ev
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{kind} vk={vk} name={name!r}\n")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"=== diagnose end {time.strftime('%H:%M:%S')} ===\n")


if __name__ == "__main__":
    clear_log()
    open(ERR, "w").close()
    threading.Thread(target=writer, daemon=True).start()
    try:
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        listener.join()
    except Exception:
        write_err("listener crash", sys.exc_info()[1])
    stop_flag.set()