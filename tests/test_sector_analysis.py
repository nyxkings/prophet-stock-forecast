"""Tests for sector analysis module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.sector_analysis import (
    TICKER_SECTOR_MAP,
    PortfolioSectorAnalysis,
    SectorAnalyzer,
    SectorMetrics,
)


class TestSectorMapping:
    """Test sector mapping functionality."""

    def test_get_ticker_sector_known_ticker(self):
        """Test getting sector for known ticker."""
        sector = SectorAnalyzer.get_ticker_sector("AAPL")
        assert sector == "Technology"

    def test_get_ticker_sector_multiple_tickers(self):
        """Test sector mapping for multiple known tickers."""
        sectors = {
            "MSFT": "Technology",
            "JPM": "Financials",
            "WMT": "Consumer Staples",
        }

        for ticker, expected_sector in sectors.items():
            assert SectorAnalyzer.get_ticker_sector(ticker) == expected_sector

    def test_get_ticker_sector_unknown_ticker(self):
        """Test error on unknown ticker."""
        with pytest.raises(ValueError):
            SectorAnalyzer.get_ticker_sector("UNKNOWN")

    def test_custom_sector_mapping(self):
        """Test custom sector mapping."""
        custom_map = {"CUSTOM": "CustomSector"}
        sector = SectorAnalyzer.get_ticker_sector("CUSTOM", custom_map=custom_map)
        assert sector == "CustomSector"

    def test_ticker_sector_map_coverage(self):
        """Test that sector map has reasonable coverage."""
        assert len(TICKER_SECTOR_MAP) > 20
        assert "AAPL" in TICKER_SECTOR_MAP
        assert "JPM" in TICKER_SECTOR_MAP


class TestGroupPortfolio:
    """Test portfolio grouping by sector."""

    def test_group_portfolio_single_sector(self):
        """Test grouping portfolio in single sector."""
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        groups = SectorAnalyzer.group_portfolio_by_sector(weights)

        assert len(groups) == 1
        assert "Technology" in groups
        assert groups["Technology"] == weights

    def test_group_portfolio_multiple_sectors(self):
        """Test grouping portfolio across multiple sectors."""
        weights = {"AAPL": 0.3, "JPM": 0.3, "WMT": 0.4}
        groups = SectorAnalyzer.group_portfolio_by_sector(weights)

        assert len(groups) == 3
        assert groups["Technology"]["AAPL"] == 0.3
        assert groups["Financials"]["JPM"] == 0.3
        assert groups["Consumer Staples"]["WMT"] == 0.4

    def test_group_portfolio_empty(self):
        """Test grouping empty portfolio."""
        weights = {}
        groups = SectorAnalyzer.group_portfolio_by_sector(weights)

        assert len(groups) == 0

    def test_group_portfolio_mixed_weights(self):
        """Test grouping with varied weights."""
        weights = {
            "AAPL": 0.1,
            "MSFT": 0.2,
            "NVDA": 0.15,
            "JPM": 0.25,
            "WMT": 0.3,
        }
        groups = SectorAnalyzer.group_portfolio_by_sector(weights)

        tech_total = sum(groups["Technology"].values())
        assert tech_total == pytest.approx(0.45, rel=0.01)
        assert groups["Financials"]["JPM"] == 0.25
        assert groups["Consumer Staples"]["WMT"] == 0.3


class TestSectorWeights:
    """Test sector weight calculations."""

    def test_calculate_sector_weights_single_ticker(self):
        """Test sector weight with single ticker."""
        weights = {"AAPL": 1.0}
        sector_weights = SectorAnalyzer.calculate_sector_weights(weights)

        assert len(sector_weights) == 1
        assert sector_weights["Technology"] == 1.0

    def test_calculate_sector_weights_multiple_sectors(self):
        """Test sector weights across sectors."""
        weights = {"AAPL": 0.2, "MSFT": 0.2, "JPM": 0.3, "WMT": 0.3}
        sector_weights = SectorAnalyzer.calculate_sector_weights(weights)

        assert sector_weights["Technology"] == pytest.approx(0.4, rel=0.01)
        assert sector_weights["Financials"] == 0.3
        assert sector_weights["Consumer Staples"] == 0.3

    def test_calculate_sector_weights_sum_to_one(self):
        """Test that sector weights sum to 1."""
        weights = {
            "AAPL": 0.15,
            "MSFT": 0.15,
            "NVDA": 0.1,
            "JPM": 0.25,
            "WMT": 0.25,
            "KO": 0.1,
        }
        sector_weights = SectorAnalyzer.calculate_sector_weights(weights)

        total = sum(sector_weights.values())
        assert total == pytest.approx(1.0, rel=0.01)


class TestConcentration:
    """Test sector concentration calculations."""

    def test_concentration_equal_sectors(self):
        """Test concentration with equal sector weights."""
        sector_weights = {"Technology": 0.33, "Financials": 0.33, "Consumer": 0.34}
        hhi, effective = SectorAnalyzer.calculate_sector_concentration(sector_weights)

        # Equal distribution should have low HHI
        assert hhi < 0.4
        assert effective > 2.5

    def test_concentration_single_sector(self):
        """Test concentration with all weight in one sector."""
        sector_weights = {"Technology": 1.0}
        hhi, effective = SectorAnalyzer.calculate_sector_concentration(sector_weights)

        assert hhi == pytest.approx(1.0, rel=0.01)
        assert effective == pytest.approx(1.0, rel=0.01)

    def test_concentration_two_sectors_equal(self):
        """Test concentration with two equal sectors."""
        sector_weights = {"Technology": 0.5, "Financials": 0.5}
        hhi, effective = SectorAnalyzer.calculate_sector_concentration(sector_weights)

        assert hhi == pytest.approx(0.5, rel=0.01)
        assert effective == pytest.approx(2.0, rel=0.05)

    def test_concentration_many_sectors(self):
        """Test concentration with many sectors."""
        sector_weights = {
            "Tech": 0.1,
            "Finance": 0.1,
            "Consumer": 0.1,
            "Healthcare": 0.1,
            "Industrial": 0.1,
            "Energy": 0.1,
            "Materials": 0.1,
            "Utilities": 0.1,
            "RealEstate": 0.1,
            "Telecom": 0.1,
        }
        hhi, effective = SectorAnalyzer.calculate_sector_concentration(sector_weights)

        assert hhi == pytest.approx(0.1, rel=0.01)
        assert effective > 9.5


class TestConcentrationLevel:
    """Test sector concentration level classification."""

    def test_concentration_level_low(self):
        """Test low concentration classification."""
        level = SectorAnalyzer.classify_concentration_level(0.2)
        assert level == "Low"

    def test_concentration_level_medium(self):
        """Test medium concentration classification."""
        level = SectorAnalyzer.classify_concentration_level(0.35)
        assert level == "Medium"

    def test_concentration_level_high(self):
        """Test high concentration classification."""
        level = SectorAnalyzer.classify_concentration_level(0.6)
        assert level == "High"

    def test_concentration_level_boundaries(self):
        """Test boundary values."""
        assert SectorAnalyzer.classify_concentration_level(0.24) == "Low"
        assert SectorAnalyzer.classify_concentration_level(0.25) == "Medium"
        assert SectorAnalyzer.classify_concentration_level(0.49) == "Medium"
        assert SectorAnalyzer.classify_concentration_level(0.50) == "High"


class TestSectorMetrics:
    """Test sector metrics calculation."""

    def test_sector_metrics_creation(self):
        """Test creating sector metrics."""
        metrics = SectorMetrics(
            sector="Technology",
            allocation=0.4,
            number_of_holdings=3,
            assets=["AAPL", "MSFT", "NVDA"],
            individual_weights={"AAPL": 0.15, "MSFT": 0.15, "NVDA": 0.1},
            volatility=0.25,
            expected_return=0.12,
            contribution_to_portfolio_return=0.048,
            contribution_to_portfolio_risk=0.1,
            diversification_ratio=1.2,
        )

        assert metrics.sector == "Technology"
        assert metrics.allocation == 0.4
        assert len(metrics.assets) == 3

    def test_sector_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = SectorMetrics(
            sector="Technology",
            allocation=0.4,
            number_of_holdings=2,
            assets=["AAPL", "MSFT"],
            individual_weights={"AAPL": 0.2, "MSFT": 0.2},
            volatility=0.25,
            expected_return=0.12,
            contribution_to_portfolio_return=0.048,
            contribution_to_portfolio_risk=0.1,
            diversification_ratio=1.2,
        )

        metrics_dict = metrics.to_dict()
        assert metrics_dict["sector"] == "Technology"
        assert metrics_dict["allocation"] == 0.4
        assert len(metrics_dict["assets"]) == 2

    def test_calculate_sector_metrics_with_data(self):
        """Test calculating sector metrics with returns data."""
        # Create sample returns data
        dates = pd.date_range(start="2024-01-01", periods=252)
        returns_aapl = np.random.normal(0.0005, 0.015, 252)
        returns_msft = np.random.normal(0.0003, 0.012, 252)

        returns_data = {
            "AAPL": pd.DataFrame({"Returns": returns_aapl}, index=dates),
            "MSFT": pd.DataFrame({"Returns": returns_msft}, index=dates),
        }

        weights = {"AAPL": 0.6, "MSFT": 0.4}
        expected_returns = {"AAPL": 0.12, "MSFT": 0.10}

        metrics = SectorAnalyzer.calculate_sector_metrics(
            weights, returns_data, expected_returns
        )

        assert "Technology" in metrics
        assert metrics["Technology"].sector == "Technology"
        assert metrics["Technology"].allocation == pytest.approx(1.0, rel=0.01)
        assert metrics["Technology"].number_of_holdings == 2

    def test_calculate_sector_metrics_without_data(self):
        """Test calculating sector metrics without returns data."""
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        returns_data = {}  # Empty returns data

        metrics = SectorAnalyzer.calculate_sector_metrics(weights, returns_data)

        assert "Technology" in metrics
        assert metrics["Technology"].allocation == 1.0
        assert metrics["Technology"].volatility == 0.0


class TestPortfolioSectorAnalysis:
    """Test complete portfolio sector analysis."""

    def test_portfolio_sector_analysis_simple(self):
        """Test analyzing simple portfolio."""
        weights = {"AAPL": 0.5, "MSFT": 0.5}

        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        assert isinstance(analysis, PortfolioSectorAnalysis)
        assert analysis.total_sectors == 1
        assert analysis.largest_sector == "Technology"
        assert analysis.largest_sector_weight == 1.0

    def test_portfolio_sector_analysis_multiple_sectors(self):
        """Test analyzing portfolio with multiple sectors."""
        weights = {
            "AAPL": 0.2,
            "MSFT": 0.2,
            "JPM": 0.3,
            "WMT": 0.3,
        }

        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        assert analysis.total_sectors == 3
        assert analysis.sector_weights["Technology"] == pytest.approx(0.4, rel=0.01)
        assert analysis.sector_weights["Financials"] == 0.3
        assert analysis.sector_weights["Consumer Staples"] == 0.3

    def test_portfolio_analysis_concentration_metrics(self):
        """Test concentration metrics in portfolio analysis."""
        weights = {"AAPL": 0.5, "MSFT": 0.25, "JPM": 0.25}

        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        assert analysis.herfindahl_index > 0
        assert analysis.effective_number_of_sectors > 0
        assert analysis.sector_concentration_level in ["Low", "Medium", "High"]

    def test_portfolio_analysis_to_dict(self):
        """Test converting portfolio analysis to dictionary."""
        weights = {"AAPL": 0.5, "JPM": 0.5}

        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)
        analysis_dict = analysis.to_dict()

        assert analysis_dict["total_sectors"] == 2
        assert "sector_weights" in analysis_dict
        assert "sector_metrics" in analysis_dict
        assert "herfindahl_index" in analysis_dict

    def test_portfolio_analysis_largest_sector(self):
        """Test identification of largest sector."""
        weights = {
            "AAPL": 0.1,
            "MSFT": 0.1,
            "NVDA": 0.1,
            "JPM": 0.2,
            "WMT": 0.2,
            "KO": 0.2,
        }

        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        # Consumer Staples (WMT, KO) has 0.4 weight - largest sector
        assert analysis.largest_sector == "Consumer Staples"
        assert analysis.largest_sector_weight == pytest.approx(0.4, rel=0.01)

    def test_portfolio_analysis_diversified_sector(self):
        """Test identification of diversified sectors."""
        # Create portfolio with returns data so diversification can be measured
        dates = pd.date_range(start="2024-01-01", periods=252)
        returns_aapl = np.random.normal(0.0005, 0.015, 252)
        returns_msft = np.random.normal(0.0005, 0.015, 252)
        returns_nvda = np.random.normal(0.0005, 0.015, 252)
        returns_jpm = np.random.normal(0.0003, 0.012, 252)

        returns_data = {
            "AAPL": pd.DataFrame({"Returns": returns_aapl}, index=dates),
            "MSFT": pd.DataFrame({"Returns": returns_msft}, index=dates),
            "NVDA": pd.DataFrame({"Returns": returns_nvda}, index=dates),
            "JPM": pd.DataFrame({"Returns": returns_jpm}, index=dates),
        }

        weights = {
            "AAPL": 0.25,
            "MSFT": 0.25,
            "NVDA": 0.25,
            "JPM": 0.25,
        }

        analysis = SectorAnalyzer.analyze_portfolio_sectors(
            weights, returns_data=returns_data
        )

        # Technology sector has 3 holdings, Financials has 1
        # So Technology should be more diversified
        assert analysis.most_diversified_sector == "Technology"
        # Just verify least_diversified_sector is in sectors (may vary by volatility)
        assert analysis.least_diversified_sector in ["Financials", "Technology"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_ticker_portfolio(self):
        """Test portfolio with single ticker."""
        weights = {"AAPL": 1.0}
        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        assert analysis.total_sectors == 1
        assert analysis.herfindahl_index == pytest.approx(1.0, rel=0.01)
        assert analysis.sector_concentration_level == "High"

    def test_equal_weight_portfolio(self):
        """Test equally-weighted portfolio."""
        weights = {
            "AAPL": 0.125,
            "MSFT": 0.125,
            "NVDA": 0.125,
            "AMD": 0.125,
            "JPM": 0.125,
            "WMT": 0.125,
            "KO": 0.125,
            "MCD": 0.125,
        }
        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        assert len(analysis.sector_weights) == 4
        total_weight = sum(analysis.sector_weights.values())
        assert total_weight == pytest.approx(1.0, rel=0.01)

    def test_many_sectors_portfolio(self):
        """Test portfolio spanning many sectors."""
        weights = {
            "AAPL": 0.05,
            "JPM": 0.05,
            "WMT": 0.05,
            "JNJ": 0.05,
            "BA": 0.05,
            "XOM": 0.05,
            "NEE": 0.05,
            "PLD": 0.05,
            "NEM": 0.05,
            "NFLX": 0.55,
        }
        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        assert analysis.total_sectors >= 6
        assert analysis.largest_sector_weight > 0.5

    def test_very_small_weights(self):
        """Test portfolio with very small weights."""
        weights = {
            "AAPL": 0.001,
            "MSFT": 0.001,
            "JPM": 0.998,
        }
        analysis = SectorAnalyzer.analyze_portfolio_sectors(weights)

        assert analysis.herfindahl_index > 0.99
        assert analysis.sector_concentration_level == "High"

    def test_custom_sector_mapping_portfolio(self):
        """Test portfolio analysis with custom sector mapping."""
        custom_map = {
            "TICKER1": "CustomSector1",
            "TICKER2": "CustomSector1",
            "TICKER3": "CustomSector2",
        }
        weights = {
            "TICKER1": 0.3,
            "TICKER2": 0.3,
            "TICKER3": 0.4,
        }

        analysis = SectorAnalyzer.analyze_portfolio_sectors(
            weights, custom_map=custom_map
        )

        assert "CustomSector1" in analysis.sector_weights
        assert "CustomSector2" in analysis.sector_weights
        assert analysis.sector_weights["CustomSector1"] == pytest.approx(0.6, rel=0.01)
