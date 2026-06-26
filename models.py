from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(tz=IST)


class RecurrenceType(str, Enum):
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    INTERVAL = "interval"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_MAP = {name: idx for idx, name in enumerate(WEEKDAY_NAMES)}


@dataclass
class Alarm:
    name: str
    alarm_time: str
    recurrence: RecurrenceType
    tags: List[str] = field(default_factory=list)
    note: str = ""
    priority: Priority = Priority.MEDIUM
    enabled: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    weekdays: List[int] = field(default_factory=list)
    interval_minutes: int = 0
    one_time_date: Optional[str] = None
    snooze_minutes: int = 5
    last_triggered: Optional[str] = None
    interval_start: Optional[str] = None

    @property
    def short_id(self) -> str:
        return self.id[:8]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "alarm_time": self.alarm_time,
            "recurrence": self.recurrence.value,
            "tags": self.tags,
            "note": self.note,
            "priority": self.priority.value,
            "enabled": self.enabled,
            "weekdays": self.weekdays,
            "interval_minutes": self.interval_minutes,
            "one_time_date": self.one_time_date,
            "snooze_minutes": self.snooze_minutes,
            "last_triggered": self.last_triggered,
            "interval_start": self.interval_start,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alarm":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data["name"],
            alarm_time=data["alarm_time"],
            recurrence=RecurrenceType(data["recurrence"]),
            tags=data.get("tags", []),
            note=data.get("note", ""),
            priority=Priority(data.get("priority", "medium")),
            enabled=data.get("enabled", True),
            weekdays=data.get("weekdays", []),
            interval_minutes=data.get("interval_minutes", 0),
            one_time_date=data.get("one_time_date"),
            snooze_minutes=data.get("snooze_minutes", 5),
            last_triggered=data.get("last_triggered"),
            interval_start=data.get("interval_start"),
        )

    def _ist_time(self, date_str: str, time_str: str) -> datetime:
        y, mo, d = map(int, date_str.split("-"))
        h, m = map(int, time_str.split(":"))
        return datetime(y, mo, d, h, m, 0, tzinfo=IST)

    def get_next_trigger(self, now: Optional[datetime] = None) -> Optional[datetime]:
        now = now or now_ist()
        if now.tzinfo is None:
            now = now.replace(tzinfo=IST)
        h, m = map(int, self.alarm_time.split(":"))

        if self.recurrence == RecurrenceType.ONE_TIME:
            if not self.one_time_date:
                return None
            target = self._ist_time(self.one_time_date, self.alarm_time)
            return target if target > now else None

        if self.recurrence == RecurrenceType.DAILY:
            candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        if self.recurrence == RecurrenceType.WEEKDAYS:
            if not self.weekdays:
                return None
            for offset in range(8):
                candidate = (now + timedelta(days=offset)).replace(
                    hour=h, minute=m, second=0, microsecond=0
                )
                if candidate <= now:
                    continue
                if candidate.weekday() in self.weekdays:
                    return candidate
            return None

        if self.recurrence == RecurrenceType.INTERVAL:
            if self.interval_minutes <= 0:
                return None
            base = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if base <= now:
                elapsed = (now - base).total_seconds() / 60
                cycles = int(elapsed / self.interval_minutes) + 1
                return base + timedelta(minutes=cycles * self.interval_minutes)
            return base

        return None

    def format_next_trigger(self, now: Optional[datetime] = None) -> str:
        now = now or now_ist()
        if now.tzinfo is None:
            now = now.replace(tzinfo=IST)
        nxt = self.get_next_trigger(now)
        if not nxt:
            return "[dim]-[/dim]"
        delta = nxt - now
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        if total_seconds < 3600:
            return f"{total_seconds // 60}m"
        hr = total_seconds // 3600
        mn = (total_seconds % 3600) // 60
        return f"{hr}h {mn}m"
