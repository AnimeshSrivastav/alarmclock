from __future__ import annotations

import json
import os
from typing import List

from models import Alarm

ALARMS_FILE = os.path.join(os.path.dirname(__file__), "alarms.json")


def load_alarms() -> List[Alarm]:
    if not os.path.exists(ALARMS_FILE):
        return []
    try:
        with open(ALARMS_FILE, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return [Alarm.from_dict(item) for item in raw]
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


def save_alarms(alarms: List[Alarm]) -> None:
    with open(ALARMS_FILE, "w", encoding="utf-8") as fh:
        json.dump([a.to_dict() for a in alarms], fh, indent=2)
