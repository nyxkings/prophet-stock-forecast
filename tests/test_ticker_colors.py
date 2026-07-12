"""Tests for shared ticker colour mapping."""

from __future__ import annotations

from src.settings import PORTFOLIO_TICKERS, TICKER_COLORS, ticker_color, ticker_color_map


class TestTickerColors:
    def test_all_portfolio_tickers_have_colours(self) -> None:
        for ticker in PORTFOLIO_TICKERS:
            assert ticker in TICKER_COLORS

    def test_portfolio_colours_are_unique(self) -> None:
        colours = [c.lower() for c in TICKER_COLORS.values()]
        assert len(colours) == len(set(colours))

    def test_color_map_returns_unique_colours(self) -> None:
        mapping = ticker_color_map(PORTFOLIO_TICKERS)
        assert len(mapping) == len(PORTFOLIO_TICKERS)
        assert len({c.lower() for c in mapping.values()}) == len(PORTFOLIO_TICKERS)

    def test_ticker_color_is_stable(self) -> None:
        assert ticker_color("AMD") == ticker_color("amd")
        assert ticker_color("NVDA") == TICKER_COLORS["NVDA"]
