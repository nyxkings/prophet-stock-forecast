"""Settings and constants for portfolio optimisation."""
from datetime import datetime

# Risk parameters
MINIMUM_ALLOCATION = 0.05  # Minimum allocation per asset (5%)
MAXIMUM_ALLOCATION = 1
RISK_AVERSION = 5

# Date defaults
START_DATE = "2024-01-01"  # Default start date for historical data
END_DATE = datetime.now().strftime("%Y-%m-%d")

# Stock Allocation
PORTFOLIO_TICKERS = [
    "AMD",
    "MSFT",
    "AAPL",
    "TSLA",
    "AMZN",
    "NVDA",
    "META",
    "GOOG",
    "TSM",
    "JPM",
    "NFLX",
    "PLTR",
]

# Fixed colours per ticker — 12 visually distinct hues (no shared colour)
TICKER_COLORS: dict[str, str] = {
    "AMD": "#E41A1C",   # red
    "MSFT": "#377EB8",  # blue
    "AAPL": "#4DAF4A",  # green
    "TSLA": "#984EA3",  # purple
    "AMZN": "#FF7F00",  # orange
    "NVDA": "#A65628",  # brown
    "META": "#F781BF",  # pink
    "GOOG": "#999999",  # grey
    "TSM": "#66C2A5",   # teal
    "JPM": "#FC8D62",   # coral
    "NFLX": "#8DA0CB",  # periwinkle
    "PLTR": "#E6AB02",  # gold
}

if len(set(TICKER_COLORS.values())) != len(TICKER_COLORS):
    raise ValueError("TICKER_COLORS must assign a unique colour to each ticker")

# Fallback palette for unexpected tickers (also unique vs each other)
_FALLBACK_TICKER_PALETTE = [
    "#1B9E77",
    "#D95F02",
    "#7570B3",
    "#E7298A",
    "#66A61E",
    "#E6AB02",
    "#A6761D",
    "#666666",
    "#1F78B4",
    "#B2DF8A",
    "#FB9A99",
    "#CAB2D6",
]


def ticker_color(ticker: str) -> str:
    """Return the shared dashboard colour for a ticker symbol."""
    key = str(ticker).upper()
    if key in TICKER_COLORS:
        return TICKER_COLORS[key]
    # Prefer fallback colours that are not already used by the portfolio palette
    used = {colour.lower() for colour in TICKER_COLORS.values()}
    unused = [c for c in _FALLBACK_TICKER_PALETTE if c.lower() not in used]
    palette = unused or _FALLBACK_TICKER_PALETTE
    return palette[hash(key) % len(palette)]


def ticker_color_map(tickers: list[str] | tuple[str, ...] | None = None) -> dict[str, str]:
    """Build a colour map for the given tickers (defaults to full portfolio)."""
    symbols = list(tickers) if tickers is not None else list(PORTFOLIO_TICKERS)
    mapping = {symbol: ticker_color(symbol) for symbol in symbols}
    # Guarantee uniqueness even if unexpected tickers collide on fallback hashing
    seen: dict[str, str] = {}
    for symbol, colour in mapping.items():
        if colour.lower() not in {c.lower() for c in seen.values()}:
            seen[symbol] = colour
            continue
        used = {c.lower() for c in seen.values()} | {c.lower() for c in TICKER_COLORS.values()}
        for candidate in _FALLBACK_TICKER_PALETTE:
            if candidate.lower() not in used:
                seen[symbol] = candidate
                break
        else:
            seen[symbol] = colour
    return seen

# Database
SUPABASE_TABLE_NAME = "stock_optimisation_store"

# Holiday name mapping for Prophet model
HOLIDAY_NAME_MAP = {
    "New Year's Day": "new_years",
    "Dr. Martin Luther King Jr. Day": "mlk_day",
    "Good Friday": "good_friday",
    "Memorial Day": "memorial_day",
    "July 4th": "independence_day",
    "Labor Day": "labor_day",
    "Thanksgiving": "thanksgiving",
    "Election Day": "election_day",
    "Veteran Day": "veterans_day",
    "Columbus Day": "columbus_day",
    "Christmas": "christmas",
    "Christmas Day": "christmas",
}

# Prophet model parameters
PROPHET_PARAMS = {
    "yearly_seasonality": True,
    "weekly_seasonality": True,
    "daily_seasonality": False,
}
