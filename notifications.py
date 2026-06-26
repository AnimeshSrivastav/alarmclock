from __future__ import annotations

import sys

try:
    from plyer import notification as _plyer_notification
    _PLYER_AVAILABLE = True
except Exception:
    _PLYER_AVAILABLE = False


def ring_bell() -> None:
    sys.stdout.write("\a")
    sys.stdout.flush()


def send_desktop_notification(title: str, message: str) -> None:
    if not _PLYER_AVAILABLE:
        return
    try:
        _plyer_notification.notify(
            title=title,
            message=message,
            app_name="Alarm Clock CLI",
            timeout=10,
        )
    except Exception:
        pass
