# Alarm Clock CLI

A fully interactive, menu-driven alarm clock built in Python. Features a rich Terminal User Interface (TUI), direct CLI command administration, a background daemon running silently, and native system alerts (desktop notifications + motherboard audio bell beep).

---

## Features
* **Interactive Menu:** Run the full TUI with colors, panels, and tables.
* **CLI Management:** Add, edit, delete, list, toggle, or snooze alarms directly from the command line.
* **Background Daemon:** Runs silently in the background (no window) with hot-reload support when alarm settings change.
* **Timezone Safety:** Fully locked to Indian Standard Time (IST / Asia:Kolkata).

---

## Installation & Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Global Installation (Optional):**
   Install the package to use the `alarm` command globally:
   ```bash
   pip install -e .
   ```
   *(Note: On Windows, make sure to restart your terminal after installation to refresh the environment PATH variable).*

---

## Usage Guide

### 1. Interactive Menu (TUI)
To launch the interactive console interface:
```bash
alarm
```

### 2. CLI Commands
Use the direct CLI interface for quick management:

#### Add a new alarm
```bash
alarm add "Wakeup" 07:30 --schedule daily
alarm add "Meeting" 14:00 --schedule one_time --date 2026-07-01 --notes "Quarterly review"
alarm add "Gym" 06:30 --schedule weekdays --days Mon,Wed,Fri --disabled
```

#### List alarms
```bash
alarm list
alarm list --filter active
alarm list --filter tag:work
```

#### Edit an existing alarm
```bash
alarm edit --id <id> --time 08:00 --name "Morning Run"
```

#### Toggle an alarm on/off
```bash
alarm toggle --id <id>
alarm toggle --id <id> --enable
alarm toggle --id <id> --disable
```

#### Delete an alarm
```bash
alarm delete --id <id>
alarm delete --id <id> --yes
```

---

## Background Daemon Management

Manage the background engine process via [setup_scheduler.py](file:///c:/Users/ASUS/OneDrive/Desktop/clock/setup_scheduler.py):

* **Install/Register background task:**
  ```bash
  python setup_scheduler.py install
  ```
  *(Requires administrator privileges).*

* **Check daemon status:**
  ```bash
  python setup_scheduler.py status
  ```

* **Launch the daemon now:**
  ```bash
  python setup_scheduler.py start
  ```

* **Stop the daemon:**
  ```bash
  python setup_scheduler.py stop
  ```
