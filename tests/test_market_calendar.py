"""Tests for market calendar helpers."""

from __future__ import annotations

from datetime import date

from src.market_calendar import next_trading_day


class TestNextTradingDay:
    def test_skips_weekend(self) -> None:
        # Friday 2024-01-05 -> Monday 2024-01-08
        assert next_trading_day(date(2024, 1, 5)) == date(2024, 1, 8)

    def test_weekday_advances_one_session(self) -> None:
        assert next_trading_day(date(2024, 1, 3)) == date(2024, 1, 4)

    def test_skips_new_years_observance(self) -> None:
        # 2023-12-29 (Fri) -> 2024-01-02 (Tue) skipping weekend + New Year
        assert next_trading_day(date(2023, 12, 29)) == date(2024, 1, 2)
