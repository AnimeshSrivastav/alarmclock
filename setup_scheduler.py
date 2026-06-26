from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TASK_NAME = "AlarmClockCLI"
BASE_DIR = Path(__file__).resolve().parent
DAEMON_SCRIPT = BASE_DIR / "daemon.py"
LOCK_FILE = BASE_DIR / "daemon.lock"
LOG_FILE = BASE_DIR / "daemon.log"


def _find_pythonw() -> Path:
    exe = Path(sys.executable)
    candidates = [
        exe.parent / "pythonw.exe",
        exe.parent / "Scripts" / "pythonw.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / exe.parent.name / "pythonw.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "pythonw.exe not found. Make sure Python is installed with the windowed interpreter."
    )


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
    )


def install() -> None:
    try:
        pythonw = _find_pythonw()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    action = f'"{pythonw}" "{DAEMON_SCRIPT}"'

    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", action,
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",
        "/DELAY", "0001:00",
        "/F",
    ]

    try:
        result = _run(cmd)
        print(f"[OK] Task '{TASK_NAME}' registered in Windows Task Scheduler.")
        print(f"     Runs at every login using: {pythonw.name}")
        print(f"     Script : {DAEMON_SCRIPT}")
        print(f"     Log    : {LOG_FILE}")
        print()
        print("     To start the daemon NOW without rebooting, run:")
        print(f'       schtasks /Run /TN "{TASK_NAME}"')
        print()
        print("     Or launch directly (no window):")
        print(f'       start "" "{pythonw}" "{DAEMON_SCRIPT}"')
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Failed to create task:\n{exc.stderr}")
        print()
        print("TIP: Run this script as Administrator if you see access denied errors.")
        sys.exit(1)


def remove() -> None:
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    try:
        _run(cmd)
        print(f"[OK] Task '{TASK_NAME}' removed from Task Scheduler.")
    except subprocess.CalledProcessError as exc:
        if "cannot find" in exc.stderr.lower() or "does not exist" in exc.stderr.lower():
            print(f"[INFO] Task '{TASK_NAME}' was not registered.")
        else:
            print(f"[ERROR] {exc.stderr}")
            sys.exit(1)

    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            _run(["taskkill", "/PID", str(pid), "/F"], check=False)
            print(f"[OK] Daemon process (PID {pid}) stopped.")
        except Exception:
            pass
        LOCK_FILE.unlink(missing_ok=True)


def status() -> None:
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"]
    result = _run(cmd, check=False)

    if result.returncode != 0:
        print(f"[INFO] Task '{TASK_NAME}' is NOT registered in Task Scheduler.")
    else:
        print(f"[Task Scheduler]\n{result.stdout.strip()}")

    print()
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            check = _run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"], check=False)
            if str(pid) in check.stdout:
                print(f"[Daemon] RUNNING  (PID {pid})")
            else:
                print(f"[Daemon] STALE lock file found (PID {pid} not running).")
                print("         Delete daemon.lock and re-install if needed.")
        except Exception:
            print("[Daemon] Lock file exists but could not read PID.")
    else:
        print("[Daemon] NOT running (no lock file found).")

    print()
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        recent = lines[-15:] if len(lines) > 15 else lines
        print(f"[Last {len(recent)} log lines from {LOG_FILE.name}]")
        for line in recent:
            print(f"  {line}")
    else:
        print(f"[Log] No log file yet at {LOG_FILE}")


def start_now() -> None:
    try:
        pythonw = _find_pythonw()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            check = _run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"], check=False)
            if str(pid) in check.stdout:
                print(f"[INFO] Daemon already running (PID {pid}). Nothing to do.")
                return
        except Exception:
            pass

    subprocess.Popen(
        [str(pythonw), str(DAEMON_SCRIPT)],
        creationflags=0x00000008,
        close_fds=True,
    )
    print("[OK] Daemon launched in background (no window).")
    print(f"     Tail the log: Get-Content '{LOG_FILE}' -Wait")


def stop_now() -> None:
    if not LOCK_FILE.exists():
        print("[INFO] Daemon does not appear to be running (no lock file).")
        return
    try:
        pid = int(LOCK_FILE.read_text().strip())
        _run(["taskkill", "/PID", str(pid), "/F"], check=False)
        LOCK_FILE.unlink(missing_ok=True)
        print(f"[OK] Daemon (PID {pid}) stopped.")
    except Exception as exc:
        print(f"[ERROR] Could not stop daemon: {exc}")


USAGE = """
Alarm Clock CLI — Daemon Setup
================================
Commands:
  python setup_scheduler.py install    Register daemon to run at every login (Task Scheduler)
  python setup_scheduler.py remove     Unregister from Task Scheduler and kill running daemon
  python setup_scheduler.py status     Show scheduler status, daemon PID, and recent log
  python setup_scheduler.py start      Launch the daemon right now (no reboot needed)
  python setup_scheduler.py stop       Kill the running daemon process

Notes:
  - 'install' requires Administrator privileges for Task Scheduler.
  - The daemon runs silently via pythonw.exe (no terminal window).
  - Alarm popups appear as desktop notifications + a small tkinter dialog.
  - Alarms are managed via: python alarm.py [add|list|edit|delete|toggle]
""".strip()

COMMANDS = {
    "install": install,
    "remove": remove,
    "status": status,
    "start": start_now,
    "stop": stop_now,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(USAGE)
        sys.exit(0)
    COMMANDS[sys.argv[1]]()
