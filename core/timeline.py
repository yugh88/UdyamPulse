"""Month-index helpers. The synthetic panel uses month 1..24; month 1 = panel_start."""

from __future__ import annotations

import calendar
from datetime import date

from core.settings import get_settings


def month_start(m: int) -> date:
    start = get_settings().panel_start
    total = start.year * 12 + (start.month - 1) + (m - 1)
    return date(total // 12, total % 12 + 1, 1)


def month_end(m: int) -> date:
    s = month_start(m)
    return date(s.year, s.month, calendar.monthrange(s.year, s.month)[1])


def month_label(m: int) -> str:
    return month_start(m).strftime("%Y-%m")


def last_visible_month(as_of: date) -> int:
    """Latest month whose data is complete (month end <= as_of). 0 if none."""
    n = get_settings().n_months
    visible = [m for m in range(1, n + 1) if month_end(m) <= as_of]
    return max(visible) if visible else 0
