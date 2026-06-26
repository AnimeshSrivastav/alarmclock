from __future__ import annotations

import sys
from datetime import datetime
from typing import List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from models import Alarm, Priority, RecurrenceType, WEEKDAY_NAMES, WEEKDAY_MAP

console = Console()


PRIORITY_COLOR = {
    Priority.LOW: "cyan",
    Priority.MEDIUM: "yellow",
    Priority.HIGH: "red bold",
}

RECURRENCE_LABEL = {
    RecurrenceType.ONE_TIME: "One-time",
    RecurrenceType.DAILY: "Daily",
    RecurrenceType.WEEKDAYS: "Weekdays",
    RecurrenceType.INTERVAL: "Interval",
}


def clear() -> None:
    console.clear()


def print_header() -> None:
    from zoneinfo import ZoneInfo
    now = datetime.now(tz=ZoneInfo("Asia/Kolkata")).strftime("%A, %B %d %Y  |  %H:%M:%S IST")
    console.print(
        Panel(
            f"[bold cyan]  ALARM CLOCK CLI[/bold cyan]\n[dim]{now}[/dim]",
            border_style="bright_blue",
            padding=(0, 4),
        )
    )


def main_menu() -> str:
    console.print("\n[bold white]MAIN MENU[/bold white]")
    options = [
        ("1", "List / View Alarms"),
        ("2", "Add Alarm"),
        ("3", "Edit Alarm"),
        ("4", "Delete Alarm"),
        ("5", "Enable / Disable Alarm"),
        ("6", "Filter Alarms"),
        ("7", "Settings"),
        ("0", "Quit"),
    ]
    for key, label in options:
        console.print(f"  [bold cyan]{key}[/bold cyan]  {label}")
    return Prompt.ask("\n[bold yellow]>[/bold yellow] Choose", default="1")


def list_alarms_table(alarms: List[Alarm], title: str = "All Alarms") -> None:
    now = datetime.now()
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold bright_blue",
        border_style="bright_blue",
        row_styles=["", "dim"],
        expand=True,
    )
    table.add_column("ID", style="dim", width=8)
    table.add_column("Name", min_width=14)
    table.add_column("Time", justify="center", width=7)
    table.add_column("Recurrence", width=12)
    table.add_column("Days / Interval", width=16)
    table.add_column("Tags", width=16)
    table.add_column("Priority", justify="center", width=8)
    table.add_column("Status", justify="center", width=8)
    table.add_column("Next Trigger", justify="right", width=11)

    if not alarms:
        console.print(Panel("[dim]No alarms found.[/dim]", border_style="dim"))
        return

    sorted_alarms = sorted(
        alarms,
        key=lambda a: a.get_next_trigger(now) or datetime.max,
    )

    for alarm in sorted_alarms:
        status_text = "[green]* Active[/green]" if alarm.enabled else "[dim]- Off[/dim]"
        priority_color = PRIORITY_COLOR[alarm.priority]
        prio_text = f"[{priority_color}]{alarm.priority.value.upper()}[/{priority_color}]"
        tags_str = ", ".join(alarm.tags) if alarm.tags else "[dim]-[/dim]"
        recur_label = RECURRENCE_LABEL[alarm.recurrence]

        extra = ""
        if alarm.recurrence == RecurrenceType.WEEKDAYS and alarm.weekdays:
            extra = ", ".join(WEEKDAY_NAMES[d] for d in sorted(alarm.weekdays))
        elif alarm.recurrence == RecurrenceType.INTERVAL:
            extra = f"every {alarm.interval_minutes}m"
        elif alarm.recurrence == RecurrenceType.ONE_TIME and alarm.one_time_date:
            extra = alarm.one_time_date

        row_style = ""
        if not alarm.enabled:
            row_style = "dim"
        elif alarm.priority == Priority.HIGH:
            row_style = "red"

        table.add_row(
            alarm.short_id,
            alarm.name,
            alarm.alarm_time,
            recur_label,
            extra or "[dim]-[/dim]",
            tags_str,
            prio_text,
            status_text,
            alarm.format_next_trigger(now),
            style=row_style,
        )

    console.print(table)


def _ask_time(prompt: str, default: str = "") -> str:
    while True:
        val = Prompt.ask(f"[cyan]{prompt}[/cyan]", default=default).strip()
        try:
            datetime.strptime(val, "%H:%M")
            return val
        except ValueError:
            console.print("[red]Invalid time. Use HH:MM (24-hour format).[/red]")


def _ask_date(prompt: str, default: str = "") -> str:
    while True:
        val = Prompt.ask(f"[cyan]{prompt}[/cyan]", default=default).strip()
        try:
            datetime.strptime(val, "%Y-%m-%d")
            return val
        except ValueError:
            console.print("[red]Invalid date. Use YYYY-MM-DD.[/red]")


def _ask_recurrence(default: RecurrenceType = RecurrenceType.ONE_TIME) -> RecurrenceType:
    console.print("\n[cyan]Recurrence:[/cyan]")
    mapping = {
        "1": RecurrenceType.ONE_TIME,
        "2": RecurrenceType.DAILY,
        "3": RecurrenceType.WEEKDAYS,
        "4": RecurrenceType.INTERVAL,
    }
    for k, v in mapping.items():
        marker = "[bold yellow]*[/bold yellow] " if v == default else "  "
        console.print(f"  {marker}[bold cyan]{k}[/bold cyan]  {RECURRENCE_LABEL[v]}")
    default_key = next(k for k, v in mapping.items() if v == default)
    choice = Prompt.ask("  Choice", default=default_key)
    return mapping.get(choice, default)


def _ask_weekdays(existing: List[int]) -> List[int]:
    existing_names = [WEEKDAY_NAMES[d] for d in existing]
    console.print(f"[dim]Days: Mon Tue Wed Thu Fri Sat Sun[/dim]")
    raw = Prompt.ask(
        "[cyan]Select days (comma-separated, e.g. Mon,Wed,Fri)[/cyan]",
        default=",".join(existing_names) if existing_names else "Mon,Fri",
    )
    result = []
    for part in raw.split(","):
        part = part.strip().capitalize()
        if part in WEEKDAY_MAP:
            result.append(WEEKDAY_MAP[part])
    return sorted(set(result))


def _ask_priority(default: Priority = Priority.MEDIUM) -> Priority:
    mapping = {"l": Priority.LOW, "m": Priority.MEDIUM, "h": Priority.HIGH}
    default_key = next(k for k, v in mapping.items() if v == default)
    console.print("[cyan]Priority:[/cyan] [l]ow / [m]edium / [h]igh")
    raw = Prompt.ask("  Choice", default=default_key).strip().lower()
    return mapping.get(raw, default)


def prompt_add_alarm() -> Optional[Alarm]:
    console.print(Panel("[bold cyan]Add New Alarm[/bold cyan]", border_style="cyan"))

    name = Prompt.ask("[cyan]Name[/cyan]").strip()
    if not name:
        console.print("[red]Name cannot be empty.[/red]")
        return None

    alarm_time = _ask_time("Alarm time (HH:MM)")
    recurrence = _ask_recurrence()

    weekdays: List[int] = []
    one_time_date: Optional[str] = None
    interval_minutes = 0

    if recurrence == RecurrenceType.ONE_TIME:
        one_time_date = _ask_date("Date (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"))
    elif recurrence == RecurrenceType.WEEKDAYS:
        weekdays = _ask_weekdays([])
    elif recurrence == RecurrenceType.INTERVAL:
        while True:
            raw = Prompt.ask("[cyan]Repeat every N minutes[/cyan]", default="30")
            try:
                interval_minutes = int(raw)
                if interval_minutes > 0:
                    break
            except ValueError:
                pass
            console.print("[red]Enter a positive integer.[/red]")

    tags_raw = Prompt.ask("[cyan]Tags (comma-separated, optional)[/cyan]", default="")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    note = Prompt.ask("[cyan]Note (optional)[/cyan]", default="")
    priority = _ask_priority()
    snooze_minutes = 5
    raw_snooze = Prompt.ask("[cyan]Snooze duration (minutes)[/cyan]", default="5")
    try:
        snooze_minutes = max(1, int(raw_snooze))
    except ValueError:
        pass

    return Alarm(
        name=name,
        alarm_time=alarm_time,
        recurrence=recurrence,
        tags=tags,
        note=note,
        priority=priority,
        weekdays=weekdays,
        one_time_date=one_time_date,
        interval_minutes=interval_minutes,
        snooze_minutes=snooze_minutes,
    )


def prompt_edit_alarm(alarm: Alarm) -> Alarm:
    console.print(Panel(f"[bold cyan]Edit Alarm - {alarm.name}[/bold cyan]", border_style="cyan"))

    name = Prompt.ask("[cyan]Name[/cyan]", default=alarm.name).strip() or alarm.name
    alarm_time = _ask_time("Alarm time (HH:MM)", default=alarm.alarm_time)
    recurrence = _ask_recurrence(default=alarm.recurrence)

    weekdays = alarm.weekdays[:]
    one_time_date = alarm.one_time_date
    interval_minutes = alarm.interval_minutes

    if recurrence == RecurrenceType.ONE_TIME:
        one_time_date = _ask_date(
            "Date (YYYY-MM-DD)",
            default=alarm.one_time_date or datetime.now().strftime("%Y-%m-%d"),
        )
        weekdays = []
        interval_minutes = 0
    elif recurrence == RecurrenceType.WEEKDAYS:
        weekdays = _ask_weekdays(alarm.weekdays)
        one_time_date = None
        interval_minutes = 0
    elif recurrence == RecurrenceType.INTERVAL:
        while True:
            raw = Prompt.ask("[cyan]Repeat every N minutes[/cyan]", default=str(alarm.interval_minutes or 30))
            try:
                interval_minutes = int(raw)
                if interval_minutes > 0:
                    break
            except ValueError:
                pass
            console.print("[red]Enter a positive integer.[/red]")
        one_time_date = None
        weekdays = []
    else:
        one_time_date = None
        weekdays = []
        interval_minutes = 0

    tags_raw = Prompt.ask(
        "[cyan]Tags (comma-separated)[/cyan]",
        default=",".join(alarm.tags),
    )
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    note = Prompt.ask("[cyan]Note[/cyan]", default=alarm.note)
    priority = _ask_priority(default=alarm.priority)

    raw_snooze = Prompt.ask("[cyan]Snooze duration (minutes)[/cyan]", default=str(alarm.snooze_minutes))
    try:
        snooze_minutes = max(1, int(raw_snooze))
    except ValueError:
        snooze_minutes = alarm.snooze_minutes

    alarm.name = name
    alarm.alarm_time = alarm_time
    alarm.recurrence = recurrence
    alarm.weekdays = weekdays
    alarm.one_time_date = one_time_date
    alarm.interval_minutes = interval_minutes
    alarm.tags = tags
    alarm.note = note
    alarm.priority = priority
    alarm.snooze_minutes = snooze_minutes

    return alarm


def select_alarm_by_id(alarms: List[Alarm], prompt_text: str = "Enter alarm ID") -> Optional[Alarm]:
    alarm_id = Prompt.ask(f"[cyan]{prompt_text}[/cyan]").strip()
    matches = [a for a in alarms if a.id.startswith(alarm_id)]
    if not matches:
        console.print(f"[red]No alarm found with ID starting with '{alarm_id}'.[/red]")
        return None
    if len(matches) > 1:
        console.print("[yellow]Multiple matches. Be more specific.[/yellow]")
        return None
    return matches[0]


def confirm_delete(alarm: Alarm) -> bool:
    return Confirm.ask(
        f"[red]Delete alarm '[bold]{alarm.name}[/bold]' ({alarm.short_id})?[/red]"
    )


def prompt_filter_menu() -> str:
    console.print("\n[bold white]FILTER BY[/bold white]")
    options = [
        ("1", "All"),
        ("2", "Active only"),
        ("3", "Disabled only"),
        ("4", "Tag"),
    ]
    for k, v in options:
        console.print(f"  [bold cyan]{k}[/bold cyan]  {v}")
    return Prompt.ask("\n[bold yellow]>[/bold yellow] Filter", default="1")


def prompt_tag_filter() -> str:
    return Prompt.ask("[cyan]Enter tag to filter by[/cyan]").strip().lower()


def show_alarm_fired(alarm: Alarm) -> None:
    priority_color = PRIORITY_COLOR[alarm.priority]
    note_line = f"\n[dim]Note:[/dim] {alarm.note}" if alarm.note else ""
    tags_line = f"\n[dim]Tags:[/dim] {', '.join(alarm.tags)}" if alarm.tags else ""
    console.print(
        Panel(
            f"[bold red]*** ALARM FIRED! ***[/bold red]\n\n"
            f"[bold white]{alarm.name}[/bold white]  [{priority_color}]({alarm.priority.value.upper()})[/{priority_color}]"
            f"{note_line}{tags_line}",
            title="[red bold] Wake Up! [/red bold]",
            border_style="red bold",
            padding=(1, 4),
        )
    )


def prompt_snooze_or_dismiss(alarm: Alarm) -> str:
    console.print(
        f"[yellow]  [s] Snooze {alarm.snooze_minutes} min   [d] Dismiss[/yellow]"
    )
    choice = Prompt.ask("  Action", default="s", choices=["s", "d"])
    return choice


def show_settings_menu(snooze_default: int) -> int:
    console.print(Panel("[bold cyan]Settings[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Current default snooze:[/dim] [bold]{snooze_default}[/bold] minutes")
    raw = Prompt.ask("[cyan]New default snooze (minutes)[/cyan]", default=str(snooze_default))
    try:
        return max(1, int(raw))
    except ValueError:
        return snooze_default
