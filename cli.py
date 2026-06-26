from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import List, Optional

from rich.console import Console

from models import Alarm, Priority, RecurrenceType, WEEKDAY_MAP, WEEKDAY_NAMES
from storage import load_alarms, save_alarms
from ui import list_alarms_table

console = Console()


def _resolve_alarm(alarms: List[Alarm], alarm_id: str) -> Optional[Alarm]:
    matches = [a for a in alarms if a.id.startswith(alarm_id)]
    if not matches:
        console.print(f"[red]No alarm found with ID '{alarm_id}'.[/red]")
        return None
    if len(matches) > 1:
        console.print(f"[yellow]Ambiguous ID '{alarm_id}' — {len(matches)} matches. Be more specific.[/yellow]")
        return None
    return matches[0]


def _validate_time(value: str) -> str:
    try:
        datetime.strptime(value, "%H:%M")
        return value
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid time '{value}'. Use HH:MM (24-hour).")


def _validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Use YYYY-MM-DD.")


def _validate_priority(value: str) -> Priority:
    try:
        return Priority(value.lower())
    except ValueError:
        raise argparse.ArgumentTypeError(f"Priority must be low, medium, or high. Got: '{value}'")


def _validate_recurrence(value: str) -> RecurrenceType:
    mapping = {
        "one_time": RecurrenceType.ONE_TIME,
        "daily": RecurrenceType.DAILY,
        "weekdays": RecurrenceType.WEEKDAYS,
        "interval": RecurrenceType.INTERVAL,
    }
    if value.lower() not in mapping:
        raise argparse.ArgumentTypeError(
            f"Recurrence must be one of: {', '.join(mapping)}. Got: '{value}'"
        )
    return mapping[value.lower()]


def _validate_weekdays(value: str) -> List[int]:
    result = []
    for part in value.split(","):
        part = part.strip().capitalize()
        if part not in WEEKDAY_MAP:
            raise argparse.ArgumentTypeError(
                f"Unknown day '{part}'. Valid: {', '.join(WEEKDAY_NAMES)}"
            )
        result.append(WEEKDAY_MAP[part])
    return sorted(set(result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python alarm.py",
        description="Alarm Clock CLI — manage alarms from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python alarm.py add --name "Wakeup" --time 07:00
  python alarm.py add --name "Stand-up" --time 09:30 --recurrence daily --priority high --tags work,scrum
  python alarm.py add --name "Meeting" --time 14:00 --recurrence one_time --date 2026-07-01 --notes "Quarterly review"
  python alarm.py add --name "Hydrate" --time 09:00 --recurrence interval --interval 30 --tags health
  python alarm.py add --name "Gym" --time 06:30 --recurrence weekdays --days Mon,Wed,Fri
  python alarm.py list
  python alarm.py list --filter active
  python alarm.py list --filter tag:work
  python alarm.py delete --id 887407b3
  python alarm.py edit --id 887407b3 --time 08:00 --name "Morning Run"
  python alarm.py toggle --id 887407b3
  python alarm.py snooze --id 887407b3 --minutes 10
        """,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    _build_add_parser(subparsers)
    _build_list_parser(subparsers)
    _build_edit_parser(subparsers)
    _build_delete_parser(subparsers)
    _build_toggle_parser(subparsers)
    _build_snooze_parser(subparsers)

    return parser


def _build_add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("add", help="Add a new alarm")
    p.add_argument("name_pos", nargs="?", metavar="name", help="Alarm name / label")
    p.add_argument("time_pos", nargs="?", metavar="time", type=_validate_time, help="Alarm time HH:MM (24-hour)")
    p.add_argument("--name", help="Alarm name / label")
    p.add_argument("--time", type=_validate_time, dest="alarm_time", help="Alarm time HH:MM (24-hour)")
    p.add_argument(
        "--recurrence",
        "--schedule",
        type=_validate_recurrence,
        default=RecurrenceType.DAILY,
        dest="recurrence",
        help="one_time | daily | weekdays | interval  (default: daily)",
    )
    p.add_argument("--date", type=_validate_date, help="Date for one_time alarms (YYYY-MM-DD)")
    p.add_argument("--days", help="Weekday alarms — comma-separated e.g. Mon,Wed,Fri")
    p.add_argument("--interval", type=int, help="Interval alarms — repeat every N minutes")
    p.add_argument("--tags", help="Comma-separated tags e.g. work,health")
    p.add_argument("--notes", default="", help="Optional free-text note")
    p.add_argument(
        "--priority",
        type=_validate_priority,
        default=Priority.MEDIUM,
        help="low | medium | high  (default: medium)",
    )
    p.add_argument("--snooze", type=int, default=5, dest="snooze_minutes", help="Snooze duration in minutes (default: 5)")
    p.add_argument("--disabled", action="store_true", help="Add alarm in disabled state")


def _build_list_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("list", help="List all alarms")
    p.add_argument(
        "--filter",
        default="all",
        metavar="FILTER",
        help="all | active | disabled | tag:<tagname>  (default: all)",
    )


def _build_edit_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("edit", help="Edit an existing alarm (only supply fields to change)")
    p.add_argument("--id", required=True, dest="alarm_id", help="Alarm ID (or unique prefix)")
    p.add_argument("--name", help="New name")
    p.add_argument("--time", type=_validate_time, dest="alarm_time", help="New time HH:MM")
    p.add_argument("--recurrence", "--schedule", type=_validate_recurrence, dest="recurrence", help="New recurrence type")
    p.add_argument("--date", type=_validate_date, help="New date for one_time")
    p.add_argument("--days", help="New weekdays e.g. Mon,Wed,Fri")
    p.add_argument("--interval", type=int, help="New interval in minutes")
    p.add_argument("--tags", help="New comma-separated tags (replaces existing)")
    p.add_argument("--notes", help="New note")
    p.add_argument("--priority", type=_validate_priority, help="New priority")
    p.add_argument("--snooze", type=int, dest="snooze_minutes", help="New snooze duration in minutes")


def _build_delete_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("delete", help="Delete an alarm by ID")
    p.add_argument("--id", required=True, dest="alarm_id", help="Alarm ID (or unique prefix)")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")


def _build_toggle_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("toggle", help="Enable or disable an alarm")
    p.add_argument("--id", required=True, dest="alarm_id", help="Alarm ID (or unique prefix)")
    p.add_argument("--enable", action="store_true", help="Force enable")
    p.add_argument("--disable", action="store_true", help="Force disable")


def _build_snooze_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("snooze", help="Update snooze duration for an alarm")
    p.add_argument("--id", required=True, dest="alarm_id", help="Alarm ID (or unique prefix)")
    p.add_argument("--minutes", type=int, required=True, help="New snooze duration in minutes")


def cmd_add(args: argparse.Namespace) -> int:
    alarms = load_alarms()

    name = args.name or args.name_pos
    alarm_time = args.alarm_time or args.time_pos

    if not name:
        console.print("[red]Alarm name is required. Provide it as a positional argument or via --name[/red]")
        return 1
    if not alarm_time:
        console.print("[red]Alarm time is required. Provide it as a positional argument or via --time[/red]")
        return 1

    recurrence: RecurrenceType = args.recurrence
    weekdays: List[int] = []
    one_time_date: Optional[str] = None
    interval_minutes = 0

    if recurrence == RecurrenceType.ONE_TIME:
        one_time_date = args.date or datetime.now().strftime("%Y-%m-%d")
    elif recurrence == RecurrenceType.WEEKDAYS:
        if not args.days:
            console.print("[red]--days is required for weekdays recurrence (e.g. --days Mon,Wed,Fri)[/red]")
            return 1
        try:
            weekdays = _validate_weekdays(args.days)
        except argparse.ArgumentTypeError as exc:
            console.print(f"[red]{exc}[/red]")
            return 1
    elif recurrence == RecurrenceType.INTERVAL:
        if not args.interval or args.interval <= 0:
            console.print("[red]--interval N (positive integer) is required for interval recurrence.[/red]")
            return 1
        interval_minutes = args.interval

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    alarm = Alarm(
        name=name,
        alarm_time=alarm_time,
        recurrence=recurrence,
        tags=tags,
        note=args.notes,
        priority=args.priority,
        enabled=not args.disabled,
        weekdays=weekdays,
        one_time_date=one_time_date,
        interval_minutes=interval_minutes,
        snooze_minutes=max(1, args.snooze_minutes),
    )

    alarms.append(alarm)
    save_alarms(alarms)

    state = "[dim](disabled)[/dim]" if not alarm.enabled else ""
    console.print(
        f"[green]Added[/green] ID: [bold cyan]{alarm.short_id}[/bold cyan]  "
        f"Name: [bold]{alarm.name}[/bold]  Time: [yellow]{alarm.alarm_time}[/yellow]  "
        f"Recurrence: [cyan]{alarm.recurrence.value}[/cyan]  "
        f"Priority: [magenta]{alarm.priority.value}[/magenta] {state}"
    )
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    filt = args.filter.lower()

    if filt == "all":
        filtered = alarms
        title = "All Alarms"
    elif filt == "active":
        filtered = [a for a in alarms if a.enabled]
        title = "Active Alarms"
    elif filt == "disabled":
        filtered = [a for a in alarms if not a.enabled]
        title = "Disabled Alarms"
    elif filt.startswith("tag:"):
        tag = filt[4:].strip()
        filtered = [a for a in alarms if tag in [t.lower() for t in a.tags]]
        title = f"Alarms tagged: {tag}"
    else:
        console.print(f"[red]Unknown filter '{args.filter}'. Use: all | active | disabled | tag:<name>[/red]")
        return 1

    list_alarms_table(filtered, title=title)
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    alarm = _resolve_alarm(alarms, args.alarm_id)
    if not alarm:
        return 1

    changed: List[str] = []

    if args.name:
        alarm.name = args.name
        changed.append("name")
    if args.alarm_time:
        alarm.alarm_time = args.alarm_time
        changed.append("time")
    if args.recurrence:
        alarm.recurrence = args.recurrence
        changed.append("recurrence")
        if args.recurrence == RecurrenceType.ONE_TIME:
            alarm.weekdays = []
            alarm.interval_minutes = 0
        elif args.recurrence == RecurrenceType.WEEKDAYS:
            alarm.one_time_date = None
            alarm.interval_minutes = 0
        elif args.recurrence == RecurrenceType.INTERVAL:
            alarm.one_time_date = None
            alarm.weekdays = []
        else:
            alarm.one_time_date = None
            alarm.weekdays = []
            alarm.interval_minutes = 0
    if args.date:
        alarm.one_time_date = args.date
        changed.append("date")
    if args.days:
        try:
            alarm.weekdays = _validate_weekdays(args.days)
            changed.append("days")
        except argparse.ArgumentTypeError as exc:
            console.print(f"[red]{exc}[/red]")
            return 1
    if args.interval is not None:
        if args.interval <= 0:
            console.print("[red]--interval must be a positive integer.[/red]")
            return 1
        alarm.interval_minutes = args.interval
        changed.append("interval")
    if args.tags is not None:
        alarm.tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        changed.append("tags")
    if args.notes is not None:
        alarm.note = args.notes
        changed.append("notes")
    if args.priority:
        alarm.priority = args.priority
        changed.append("priority")
    if args.snooze_minutes is not None:
        alarm.snooze_minutes = max(1, args.snooze_minutes)
        changed.append("snooze")

    if not changed:
        console.print("[yellow]Nothing to change — supply at least one field to update.[/yellow]")
        return 0

    save_alarms(alarms)
    console.print(
        f"[green]Updated[/green] alarm [bold]{alarm.short_id}[/bold] — "
        f"fields changed: [cyan]{', '.join(changed)}[/cyan]"
    )
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    alarm = _resolve_alarm(alarms, args.alarm_id)
    if not alarm:
        return 1

    if not args.yes:
        console.print(
            f"[yellow]Delete alarm '[bold]{alarm.name}[/bold]' ({alarm.short_id})? "
            f"[/yellow][[bold]y[/bold]/n] ",
            end="",
        )
        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer not in ("y", "yes", ""):
            console.print("[dim]Cancelled.[/dim]")
            return 0

    alarms = [a for a in alarms if a.id != alarm.id]
    save_alarms(alarms)
    console.print(f"[red]Deleted[/red] alarm '[bold]{alarm.name}[/bold]' ({alarm.short_id}).")
    return 0


def cmd_toggle(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    alarm = _resolve_alarm(alarms, args.alarm_id)
    if not alarm:
        return 1

    if args.enable and args.disable:
        console.print("[red]Cannot use --enable and --disable together.[/red]")
        return 1

    if args.enable:
        alarm.enabled = True
    elif args.disable:
        alarm.enabled = False
    else:
        alarm.enabled = not alarm.enabled

    state = "[green]enabled[/green]" if alarm.enabled else "[dim]disabled[/dim]"
    save_alarms(alarms)
    console.print(f"Alarm '[bold]{alarm.name}[/bold]' ({alarm.short_id}) is now {state}.")
    return 0


def cmd_snooze(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    alarm = _resolve_alarm(alarms, args.alarm_id)
    if not alarm:
        return 1

    if args.minutes <= 0:
        console.print("[red]--minutes must be a positive integer.[/red]")
        return 1

    alarm.snooze_minutes = args.minutes
    save_alarms(alarms)
    console.print(
        f"[green]Snooze updated[/green] — '[bold]{alarm.name}[/bold]' set to "
        f"[bold]{alarm.snooze_minutes}[/bold] minutes."
    )
    return 0


COMMAND_MAP = {
    "add": cmd_add,
    "list": cmd_list,
    "edit": cmd_edit,
    "delete": cmd_delete,
    "toggle": cmd_toggle,
    "snooze": cmd_snooze,
}


def run_cli(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    handler = COMMAND_MAP.get(args.command)
    if not handler:
        console.print(f"[red]Unknown command: {args.command}[/red]")
        return 1

    return handler(args)
