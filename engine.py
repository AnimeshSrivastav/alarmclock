from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional
from zoneinfo import ZoneInfo

from models import Alarm, RecurrenceType
from storage import ALARMS_FILE, save_alarms

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(tz=IST).replace(second=0, microsecond=0)


class AlarmEngine:
    def __init__(
        self,
        get_alarms: Callable[[], List[Alarm]],
        on_fire: Callable[[Alarm], None],
        reload_alarms: Optional[Callable[[], List[Alarm]]] = None,
    ) -> None:
        self._get_alarms = get_alarms
        self._on_fire = on_fire
        self._reload_alarms = reload_alarms
        self._fired_ids: set[str] = set()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_mtime: float = 0.0
        self._reload_lock = threading.Lock()

    def start(self) -> None:
        self._stop_event.clear()
        self._last_mtime = self._get_file_mtime()
        self._thread = threading.Thread(target=self._run, daemon=True, name="alarm-engine")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    @staticmethod
    def _get_file_mtime() -> float:
        try:
            return os.path.getmtime(ALARMS_FILE)
        except FileNotFoundError:
            return 0.0

    def _check_hot_reload(self) -> None:
        if not self._reload_alarms:
            return
        current_mtime = self._get_file_mtime()
        if current_mtime != self._last_mtime:
            with self._reload_lock:
                if current_mtime != self._last_mtime:
                    self._last_mtime = current_mtime
                    self._reload_alarms()

    def _run(self) -> None:
        tick = 0
        while not self._stop_event.is_set():
            now = now_ist()
            if tick % 3 == 0:
                self._check_hot_reload()
            alarms = self._get_alarms()
            for alarm in alarms:
                if not alarm.enabled:
                    continue
                self._check_alarm(alarm, now)
            tick += 1
            time.sleep(1)

    def _check_alarm(self, alarm: Alarm, now: datetime) -> None:
        h, m = map(int, alarm.alarm_time.split(":"))
        fire_key: Optional[str] = None

        if alarm.recurrence == RecurrenceType.ONE_TIME:
            if not alarm.one_time_date:
                return
            target = datetime(
                *map(int, alarm.one_time_date.split("-")),
                h, m, 0, tzinfo=IST,
            )
            if now == target:
                fire_key = f"{alarm.id}:{target.isoformat()}"

        elif alarm.recurrence == RecurrenceType.DAILY:
            if now.hour == h and now.minute == m:
                fire_key = f"{alarm.id}:{now.strftime('%Y-%m-%d %H:%M')}"

        elif alarm.recurrence == RecurrenceType.WEEKDAYS:
            if now.weekday() in alarm.weekdays and now.hour == h and now.minute == m:
                fire_key = f"{alarm.id}:{now.strftime('%Y-%m-%d %H:%M')}"

        elif alarm.recurrence == RecurrenceType.INTERVAL:
            if alarm.interval_minutes <= 0:
                return
            base = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now < base:
                return
            elapsed_minutes = int((now - base).total_seconds() / 60)
            if elapsed_minutes % alarm.interval_minutes == 0:
                fire_key = f"{alarm.id}:{now.strftime('%Y-%m-%d %H:%M')}"

        if fire_key and fire_key not in self._fired_ids:
            with self._lock:
                if fire_key not in self._fired_ids:
                    self._fired_ids.add(fire_key)
                    alarm.last_triggered = now.isoformat()
                    if alarm.recurrence == RecurrenceType.ONE_TIME:
                        alarm.enabled = False
                    self._on_fire(alarm)

    def reset_fired(self) -> None:
        with self._lock:
            self._fired_ids.clear()

    def apply_snooze(
        self,
        alarm: Alarm,
        save_fn: Callable[[List[Alarm]], None],
        all_alarms: List[Alarm],
    ) -> None:
        snooze_time = datetime.now(tz=IST) + timedelta(minutes=alarm.snooze_minutes)
        alarm.alarm_time = snooze_time.strftime("%H:%M")
        if alarm.recurrence == RecurrenceType.ONE_TIME:
            alarm.one_time_date = snooze_time.strftime("%Y-%m-%d")
            alarm.enabled = True
        save_fn(all_alarms)
