"""US equity market calendar helpers."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pandas_market_calendars as mcal


def next_trading_day(after: date, calendar_name: str = "XNYS") -> date:
    """Return the first exchange trading session strictly after ``after``."""
    calendar = mcal.get_calendar(calendar_name)
    start = pd.Timestamp(after) + pd.Timedelta(days=1)
    end = start + pd.Timedelta(days=30)
    valid = calendar.valid_days(start_date=start, end_date=end)
    if len(valid) == 0:
        return (start + pd.Timedelta(days=1)).date()
    return pd.Timestamp(valid[0]).date()
