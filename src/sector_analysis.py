"""Sector analysis and concentration metrics for portfolios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


# Global sector mapping for common stocks
TICKER_SECTOR_MAP = {
    # Technology
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOG": "Technology",
    "GOOGL": "Technology",
    "META": "Technology",
    "NVDA": "Technology",
    "TSLA": "Consumer Discretionary",  # Often grouped here
    "AMD": "Technology",
    "TSM": "Technology",
    "NFLX": "Communication Services",
    "PLTR": "Technology",
    # Financials
    "JPM": "Financials",
    "BAC": "Financials",
    "WFC": "Financials",
    "GS": "Financials",
    # Consumer
    "WMT": "Consumer Staples",
    "KO": "Consumer Staples",
    "MCD": "Consumer Discretionary",
    "AMZN": "Consumer Discretionary",
    # Healthcare
    "JNJ": "Healthcare",
    "PFE": "Healthcare",
    "UNH": "Healthcare",
    # Industrials
    "BA": "Industrials",
    "CAT": "Industrials",
    # Energy
    "XOM": "Energy",
    "CVX": "Energy",
    # Utilities
    "NEE": "Utilities",
    "DUK": "Utilities",
    # Real Estate
    "PLD": "Real Estate",
    # Materials
    "NEM": "Materials",
}


@dataclass
class SectorMetrics:
    """Metrics for a single sector."""

    sector: str
    allocation: float  # Total weight in portfolio
    number_of_holdings: int  # Number of assets in sector
    assets: list[str]  # Ticker symbols in sector
    individual_weights: dict[str, float]  # Weight of each asset
    volatility: float  # Sector volatility
    expected_return: float  # Sector expected return
    contribution_to_portfolio_return: float  # Sector contribution
    contribution_to_portfolio_risk: float  # Sector contribution
    diversification_ratio: float  # Within-sector diversification

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sector": self.sector,
            "allocation": self.allocation,
            "number_of_holdings": self.number_of_holdings,
            "assets": self.assets,
            "individual_weights": self.individual_weights,
            "volatility": self.volatility,
            "expected_return": self.expected_return,
            "contribution_to_portfolio_return": self.contribution_to_portfolio_return,
            "contribution_to_portfolio_risk": self.contribution_to_portfolio_risk,
            "diversification_ratio": self.diversification_ratio,
        }


@dataclass
class PortfolioSectorAnalysis:
    """Complete sector analysis for a portfolio."""

    total_sectors: int
    sector_weights: dict[str, float]  # Sector name -> total weight
    sector_metrics: dict[str, SectorMetrics]  # Sector name -> detailed metrics
    herfindahl_index: float  # HHI for sector concentration
    effective_number_of_sectors: float  # Shannon entropy based
    largest_sector: str  # Most concentrated sector
    largest_sector_weight: float  # Weight of largest sector
    sector_concentration_level: str  # "Low", "Medium", "High"
    most_diversified_sector: str  # Most diversified sector
    least_diversified_sector: str  # Least diversified sector

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_sectors": self.total_sectors,
            "sector_weights": self.sector_weights,
            "sector_metrics": {k: v.to_dict() for k, v in self.sector_metrics.items()},
            "herfindahl_index": self.herfindahl_index,
            "effective_number_of_sectors": self.effective_number_of_sectors,
            "largest_sector": self.largest_sector,
            "largest_sector_weight": self.largest_sector_weight,
            "sector_concentration_level": self.sector_concentration_level,
            "most_diversified_sector": self.most_diversified_sector,
            "least_diversified_sector": self.least_diversified_sector,
        }


class SectorAnalyzer:
    """Analyze sector concentration and diversification."""

    @staticmethod
    def get_ticker_sector(
        ticker: str,
        custom_map: dict[str, str] | None = None,
    ) -> str:
        """
        Get sector for a ticker.

        Args:
            ticker: Stock ticker symbol
            custom_map: Optional custom sector mapping

        Returns:
            Sector name

        Raises:
            ValueError: If ticker not found in any mapping
        """
        sector_map = custom_map or TICKER_SECTOR_MAP

        if ticker in sector_map:
            return sector_map[ticker]

        raise ValueError(f"Ticker {ticker} not found in sector mapping")

    @staticmethod
    def group_portfolio_by_sector(
        weights: dict[str, float],
        custom_map: dict[str, str] | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Group portfolio holdings by sector.

        Args:
            weights: Dictionary mapping ticker to weight
            custom_map: Optional custom sector mapping

        Returns:
            Dictionary mapping sector to {ticker: weight} for assets in that sector

        Raises:
            ValueError: If any ticker not found in sector mapping
        """
        sector_groups: dict[str, dict[str, float]] = {}

        for ticker, weight in weights.items():
            sector = SectorAnalyzer.get_ticker_sector(ticker, custom_map)

            if sector not in sector_groups:
                sector_groups[sector] = {}

            sector_groups[sector][ticker] = weight

        return sector_groups

    @staticmethod
    def calculate_sector_weights(
        weights: dict[str, float],
        custom_map: dict[str, str] | None = None,
    ) -> dict[str, float]:
        """
        Calculate total weight for each sector.

        Args:
            weights: Dictionary mapping ticker to weight
            custom_map: Optional custom sector mapping

        Returns:
            Dictionary mapping sector to total weight
        """
        sector_groups = SectorAnalyzer.group_portfolio_by_sector(weights, custom_map)

        sector_weights = {}
        for sector, tickers in sector_groups.items():
            sector_weights[sector] = sum(tickers.values())

        return sector_weights

    @staticmethod
    def calculate_sector_concentration(
        sector_weights: dict[str, float],
    ) -> tuple[float, float]:
        """
        Calculate sector concentration metrics.

        Args:
            sector_weights: Dictionary mapping sector to total weight

        Returns:
            Tuple of (herfindahl_index, effective_number_of_sectors)
        """
        weights = np.array(list(sector_weights.values()))

        # Herfindahl-Hirschman Index for sectors
        hhi = float(np.sum(weights**2))

        # Effective number of sectors using Shannon entropy
        # ENS = exp(-entropy) where entropy = -sum(p * ln(p))
        weights_norm = weights / np.sum(weights)
        entropy = -np.sum(weights_norm * np.log(weights_norm + 1e-10))
        effective_sectors = float(np.exp(entropy))

        return hhi, effective_sectors

    @staticmethod
    def classify_concentration_level(hhi: float) -> str:
        """
        Classify sector concentration level based on HHI.

        Args:
            hhi: Herfindahl-Hirschman Index

        Returns:
            Classification: "Low", "Medium", or "High"
        """
        # HHI ranges: 0 (no concentration) to 1 (complete concentration)
        if hhi < 0.25:
            return "Low"
        elif hhi < 0.50:
            return "Medium"
        else:
            return "High"

    @staticmethod
    def calculate_sector_metrics(
        weights: dict[str, float],
        returns_data: dict[str, pd.DataFrame] | None = None,
        expected_returns: dict[str, float] | None = None,
        custom_map: dict[str, str] | None = None,
    ) -> dict[str, SectorMetrics]:
        """
        Calculate detailed metrics for each sector.

        Args:
            weights: Dictionary mapping ticker to weight
            returns_data: Optional dictionary mapping ticker to DataFrame with Returns column
            expected_returns: Optional dictionary of expected returns by ticker
            custom_map: Optional custom sector mapping

        Returns:
            Dictionary mapping sector to SectorMetrics
        """
        if returns_data is None:
            returns_data = {}
        sector_groups = SectorAnalyzer.group_portfolio_by_sector(weights, custom_map)
        sector_metrics_dict: dict[str, SectorMetrics] = {}

        for sector, sector_weights in sector_groups.items():
            assets = list(sector_weights.keys())
            sector_weight = sum(sector_weights.values())

            # Calculate sector volatility (weighted average of asset volatilities)
            sector_volatility = 0.0
            sector_expected_return = 0.0

            for ticker, weight in sector_weights.items():
                if ticker in returns_data:
                    returns = returns_data[ticker]["Returns"].values
                    ticker_vol = float(np.std(returns) * np.sqrt(252))
                    sector_volatility += weight * ticker_vol

                if expected_returns and ticker in expected_returns:
                    sector_expected_return += weight * expected_returns[ticker]

            # Calculate diversification ratio within sector
            sector_diversification = 0.0
            if len(assets) > 1:
                for ticker, weight in sector_weights.items():
                    if ticker in returns_data:
                        returns = returns_data[ticker]["Returns"].values
                        ticker_vol = float(np.std(returns) * np.sqrt(252))
                        sector_diversification += weight * ticker_vol

                # Diversification ratio = weighted avg volatility / portfolio volatility
                if sector_volatility > 0:
                    sector_diversification = sector_diversification / sector_volatility
                else:
                    sector_diversification = 1.0
            else:
                sector_diversification = 1.0

            # Contribution to portfolio
            portfolio_return_contribution = sector_weight * sector_expected_return
            portfolio_risk_contribution = sector_weight * sector_volatility

            sector_metrics_dict[sector] = SectorMetrics(
                sector=sector,
                allocation=sector_weight,
                number_of_holdings=len(assets),
                assets=assets,
                individual_weights=sector_weights,
                volatility=sector_volatility,
                expected_return=sector_expected_return,
                contribution_to_portfolio_return=portfolio_return_contribution,
                contribution_to_portfolio_risk=portfolio_risk_contribution,
                diversification_ratio=sector_diversification,
            )

        return sector_metrics_dict

    @staticmethod
    def analyze_portfolio_sectors(
        weights: dict[str, float],
        returns_data: dict[str, pd.DataFrame] | None = None,
        expected_returns: dict[str, float] | None = None,
        custom_map: dict[str, str] | None = None,
    ) -> PortfolioSectorAnalysis:
        """
        Perform comprehensive sector analysis on portfolio.

        Args:
            weights: Dictionary mapping ticker to weight
            returns_data: Optional dictionary mapping ticker to DataFrame with Returns
            expected_returns: Optional dictionary of expected returns by ticker
            custom_map: Optional custom sector mapping

        Returns:
            PortfolioSectorAnalysis object with complete sector metrics
        """
        # Group by sector and calculate weights
        sector_weights = SectorAnalyzer.calculate_sector_weights(weights, custom_map)

        # Calculate concentration metrics
        hhi, effective_sectors = SectorAnalyzer.calculate_sector_concentration(
            sector_weights
        )

        # Calculate sector metrics if data provided
        if returns_data:
            sector_metrics = SectorAnalyzer.calculate_sector_metrics(
                weights, returns_data, expected_returns, custom_map
            )
        else:
            # Create minimal metrics without data
            sector_metrics = {}
            for sector, sector_weight in sector_weights.items():
                sector_groups = SectorAnalyzer.group_portfolio_by_sector(
                    weights, custom_map
                )
                sector_metrics[sector] = SectorMetrics(
                    sector=sector,
                    allocation=sector_weight,
                    number_of_holdings=len(sector_groups[sector]),
                    assets=list(sector_groups[sector].keys()),
                    individual_weights=sector_groups[sector],
                    volatility=0.0,
                    expected_return=0.0,
                    contribution_to_portfolio_return=0.0,
                    contribution_to_portfolio_risk=0.0,
                    diversification_ratio=1.0,
                )

        # Find largest and most diversified sectors
        largest_sector = max(sector_weights, key=sector_weights.get)
        least_diversified_sector = min(
            sector_metrics, key=lambda s: sector_metrics[s].diversification_ratio
        )
        most_diversified_sector = max(
            sector_metrics, key=lambda s: sector_metrics[s].diversification_ratio
        )

        concentration_level = SectorAnalyzer.classify_concentration_level(hhi)

        return PortfolioSectorAnalysis(
            total_sectors=len(sector_weights),
            sector_weights=sector_weights,
            sector_metrics=sector_metrics,
            herfindahl_index=hhi,
            effective_number_of_sectors=effective_sectors,
            largest_sector=largest_sector,
            largest_sector_weight=sector_weights[largest_sector],
            sector_concentration_level=concentration_level,
            most_diversified_sector=most_diversified_sector,
            least_diversified_sector=least_diversified_sector,
        )
