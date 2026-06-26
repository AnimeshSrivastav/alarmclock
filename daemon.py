from __future__ import annotations

import logging
import os
import queue
import signal
import sys
import threading
import time
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "daemon.log"
LOCK_FILE = BASE_DIR / "daemon.lock"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("alarm-daemon")

sys.path.insert(0, str(BASE_DIR))

from engine import AlarmEngine, now_ist
from models import Alarm
from notifications import send_desktop_notification
from storage import load_alarms, save_alarms, ALARMS_FILE


_alarms: List[Alarm] = []
_alarms_lock = threading.Lock()
_fired_queue: queue.Queue[Alarm] = queue.Queue()


def _get_alarms() -> List[Alarm]:
    with _alarms_lock:
        return list(_alarms)


def _reload_from_disk() -> List[Alarm]:
    global _alarms
    fresh = load_alarms()
    with _alarms_lock:
        _alarms[:] = fresh
    log.info("Hot-reloaded %d alarms from disk.", len(fresh))
    return fresh


def _ring_bell() -> None:
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass


def _on_alarm_fired(alarm: Alarm) -> None:
    log.info("FIRED: %s (id=%s)", alarm.name, alarm.short_id)
    _ring_bell()
    send_desktop_notification(
        title=f"Alarm: {alarm.name}",
        message=alarm.note or f"Priority: {alarm.priority.value}",
    )
    _fired_queue.put(alarm)


def _show_snooze_dialog(alarm: Alarm) -> None:
    import tkinter as tk
    from tkinter import font as tkfont

    result = {"action": "dismiss"}

    def _snooze():
        result["action"] = "snooze"
        root.destroy()

    def _dismiss():
        result["action"] = "dismiss"
        root.destroy()

    root = tk.Tk()
    root.title("Alarm!")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(bg="#1a1a2e")

    w, h = 420, 230
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    title_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
    body_font = tkfont.Font(family="Segoe UI", size=10)
    btn_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")

    tk.Label(root, text="*** ALARM FIRED ***", bg="#1a1a2e", fg="#e94560",
             font=title_font).pack(pady=(18, 4))
    tk.Label(root, text=alarm.name, bg="#1a1a2e", fg="#ffffff",
             font=tkfont.Font(family="Segoe UI", size=12, weight="bold")).pack()

    if alarm.note:
        tk.Label(root, text=alarm.note, bg="#1a1a2e", fg="#a0a0c0",
                 font=body_font, wraplength=380).pack(pady=4)

    tk.Label(
        root,
        text=f"Priority: {alarm.priority.value.upper()}  |  "
             f"Time: {alarm.alarm_time} IST",
        bg="#1a1a2e", fg="#888888", font=body_font,
    ).pack(pady=(2, 14))

    btn_frame = tk.Frame(root, bg="#1a1a2e")
    btn_frame.pack()

    tk.Button(
        btn_frame,
        text=f"Snooze ({alarm.snooze_minutes} min)",
        command=_snooze,
        bg="#0f3460", fg="#e2e2e2", font=btn_font,
        relief="flat", padx=18, pady=8, cursor="hand2",
    ).pack(side="left", padx=10)

    tk.Button(
        btn_frame,
        text="Dismiss",
        command=_dismiss,
        bg="#e94560", fg="#ffffff", font=btn_font,
        relief="flat", padx=18, pady=8, cursor="hand2",
    ).pack(side="left", padx=10)

    root.after(60000, _dismiss)
    root.mainloop()

    if result["action"] == "snooze":
        with _alarms_lock:
            engine.apply_snooze(alarm, save_alarms, _alarms)
        log.info("SNOOZED: %s for %d min", alarm.name, alarm.snooze_minutes)
    else:
        save_alarms(_alarms)
        log.info("DISMISSED: %s", alarm.name)


def _dialog_worker() -> None:
    while True:
        try:
            alarm = _fired_queue.get(timeout=1)
            _show_snooze_dialog(alarm)
        except queue.Empty:
            continue
        except Exception as exc:
            log.exception("Dialog error for alarm: %s", exc)


def _acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            import psutil
            if psutil.pid_exists(pid):
                log.warning("Daemon already running (PID %d). Exiting.", pid)
                return False
        except Exception:
            pass
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _handle_signal(signum, frame) -> None:
    log.info("Signal %d received. Shutting down.", signum)
    engine.stop()
    _release_lock()
    sys.exit(0)


engine = AlarmEngine(
    get_alarms=_get_alarms,
    on_fire=_on_alarm_fired,
    reload_alarms=_reload_from_disk,
)


def main() -> None:
    global _alarms

    try:
        import psutil
    except ImportError:
        pass

    if not _acquire_lock():
        sys.exit(1)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info("Alarm daemon starting. PID=%d", os.getpid())
    log.info("Watching: %s", ALARMS_FILE)

    with _alarms_lock:
        _alarms = load_alarms()

    log.info("Loaded %d alarms.", len(_alarms))

    engine.start()
    log.info("Engine running (IST / Asia:Kolkata). Hot-reload active.")

    dialog_thread = threading.Thread(
        target=_dialog_worker, daemon=True, name="dialog-worker"
    )
    dialog_thread.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        _release_lock()
        log.info("Alarm daemon stopped.")


if __name__ == "__main__":
    main()
