from __future__ import annotations

import queue
import sys
import threading
from typing import List

from rich.console import Console

from engine import AlarmEngine
from models import Alarm
from notifications import ring_bell, send_desktop_notification
from storage import load_alarms, save_alarms
from ui import (
    clear,
    confirm_delete,
    list_alarms_table,
    main_menu,
    print_header,
    prompt_add_alarm,
    prompt_edit_alarm,
    prompt_filter_menu,
    prompt_snooze_or_dismiss,
    prompt_tag_filter,
    select_alarm_by_id,
    show_alarm_fired,
    show_settings_menu,
    console,
)

_alarms: List[Alarm] = []
_alarms_lock = threading.Lock()
_fired_queue: queue.Queue[Alarm] = queue.Queue()
_default_snooze = 5


def _get_alarms() -> List[Alarm]:
    with _alarms_lock:
        return list(_alarms)


def _on_alarm_fired(alarm: Alarm) -> None:
    ring_bell()
    send_desktop_notification(
        title=f"⏰ {alarm.name}",
        message=alarm.note or f"Priority: {alarm.priority.value}",
    )
    _fired_queue.put(alarm)


def _handle_fired_alarms() -> None:
    while not _fired_queue.empty():
        try:
            alarm = _fired_queue.get_nowait()
        except queue.Empty:
            break
        show_alarm_fired(alarm)
        with _alarms_lock:
            alarms_snapshot = list(_alarms)
        action = prompt_snooze_or_dismiss(alarm)
        if action == "s":
            with _alarms_lock:
                engine.apply_snooze(alarm, save_alarms, _alarms)
            console.print(f"[green]Snoozed for {alarm.snooze_minutes} minutes.[/green]")
        else:
            save_alarms(_alarms)
            console.print("[dim]Alarm dismissed.[/dim]")


def handle_list(alarms: List[Alarm]) -> None:
    list_alarms_table(alarms)
    console.input("\n[dim]Press Enter to return...[/dim]")


def handle_add() -> None:
    new_alarm = prompt_add_alarm()
    if new_alarm:
        with _alarms_lock:
            _alarms.append(new_alarm)
            save_alarms(_alarms)
        console.print(f"[green]Alarm '[bold]{new_alarm.name}[/bold]' added (ID: {new_alarm.short_id}).[/green]")
        console.input("\n[dim]Press Enter to continue...[/dim]")


def handle_edit() -> None:
    with _alarms_lock:
        alarms_snapshot = list(_alarms)
    if not alarms_snapshot:
        console.print("[yellow]No alarms to edit.[/yellow]")
        console.input("\n[dim]Press Enter...[/dim]")
        return
    list_alarms_table(alarms_snapshot, title="Select Alarm to Edit")
    alarm = select_alarm_by_id(alarms_snapshot, "Enter alarm ID to edit")
    if not alarm:
        console.input("\n[dim]Press Enter...[/dim]")
        return
    updated = prompt_edit_alarm(alarm)
    with _alarms_lock:
        for i, a in enumerate(_alarms):
            if a.id == updated.id:
                _alarms[i] = updated
                break
        save_alarms(_alarms)
    console.print(f"[green]Alarm '[bold]{updated.name}[/bold]' updated.[/green]")
    console.input("\n[dim]Press Enter to continue...[/dim]")


def handle_delete() -> None:
    with _alarms_lock:
        alarms_snapshot = list(_alarms)
    if not alarms_snapshot:
        console.print("[yellow]No alarms to delete.[/yellow]")
        console.input("\n[dim]Press Enter...[/dim]")
        return
    list_alarms_table(alarms_snapshot, title="Select Alarm to Delete")
    alarm = select_alarm_by_id(alarms_snapshot, "Enter alarm ID to delete")
    if not alarm:
        console.input("\n[dim]Press Enter...[/dim]")
        return
    if confirm_delete(alarm):
        with _alarms_lock:
            _alarms[:] = [a for a in _alarms if a.id != alarm.id]
            save_alarms(_alarms)
        console.print(f"[red]Alarm '[bold]{alarm.name}[/bold]' deleted.[/red]")
    else:
        console.print("[dim]Cancelled.[/dim]")
    console.input("\n[dim]Press Enter to continue...[/dim]")


def handle_toggle() -> None:
    with _alarms_lock:
        alarms_snapshot = list(_alarms)
    if not alarms_snapshot:
        console.print("[yellow]No alarms.[/yellow]")
        console.input("\n[dim]Press Enter...[/dim]")
        return
    list_alarms_table(alarms_snapshot, title="Enable / Disable Alarm")
    alarm = select_alarm_by_id(alarms_snapshot, "Enter alarm ID to toggle")
    if not alarm:
        console.input("\n[dim]Press Enter...[/dim]")
        return
    with _alarms_lock:
        for a in _alarms:
            if a.id == alarm.id:
                a.enabled = not a.enabled
                state = "enabled" if a.enabled else "disabled"
                console.print(f"[green]Alarm '[bold]{a.name}[/bold]' {state}.[/green]")
                break
        save_alarms(_alarms)
    console.input("\n[dim]Press Enter to continue...[/dim]")


def handle_filter() -> None:
    choice = prompt_filter_menu()
    with _alarms_lock:
        alarms_snapshot = list(_alarms)

    if choice == "1":
        list_alarms_table(alarms_snapshot, title="All Alarms")
    elif choice == "2":
        filtered = [a for a in alarms_snapshot if a.enabled]
        list_alarms_table(filtered, title="Active Alarms")
    elif choice == "3":
        filtered = [a for a in alarms_snapshot if not a.enabled]
        list_alarms_table(filtered, title="Disabled Alarms")
    elif choice == "4":
        tag = prompt_tag_filter()
        filtered = [a for a in alarms_snapshot if tag in [t.lower() for t in a.tags]]
        list_alarms_table(filtered, title=f"Alarms tagged: {tag}")
    else:
        list_alarms_table(alarms_snapshot)

    console.input("\n[dim]Press Enter to return...[/dim]")


def handle_settings() -> None:
    global _default_snooze
    _default_snooze = show_settings_menu(_default_snooze)
    console.print(f"[green]Default snooze set to {_default_snooze} minutes.[/green]")
    console.input("\n[dim]Press Enter to continue...[/dim]")



def _reload_from_disk() -> List[Alarm]:
    global _alarms
    fresh = load_alarms()
    with _alarms_lock:
        _alarms[:] = fresh
    return fresh


engine = AlarmEngine(
    get_alarms=_get_alarms,
    on_fire=_on_alarm_fired,
    reload_alarms=_reload_from_disk,
)

MENU_HANDLERS = {
    "1": lambda: handle_list(_get_alarms()),
    "2": handle_add,
    "3": handle_edit,
    "4": handle_delete,
    "5": handle_toggle,
    "6": handle_filter,
    "7": handle_settings,
}


def main() -> None:
    global _alarms
    with _alarms_lock:
        _alarms = load_alarms()

    engine.start()
    console.print("[dim]Alarm engine started (IST / Asia:Kolkata). Hot-reload active.[/dim]")

    try:
        while True:
            _handle_fired_alarms()
            clear()
            print_header()
            choice = main_menu()

            if choice == "0":
                break

            handler = MENU_HANDLERS.get(choice)
            if handler:
                _handle_fired_alarms()
                handler()
            else:
                console.print("[red]Invalid option.[/red]")
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        console.print("\n[dim]Goodbye.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    _CLI_COMMANDS = {"add", "list", "edit", "delete", "toggle", "snooze", "--help", "-h"}
    if len(sys.argv) > 1 and (sys.argv[1] in _CLI_COMMANDS or sys.argv[1].startswith("-")):
        from cli import run_cli
        sys.exit(run_cli(sys.argv[1:]))
    main()
