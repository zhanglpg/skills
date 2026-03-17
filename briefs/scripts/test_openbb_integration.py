#!/usr/bin/env python3
"""Tests for extra data (quantitative) integration in the briefs pipeline.

Covers:
- fetcher.py: fetch_extra_data(), staleness check, _format_extra_data_for_prompt()
- generate_brief.py: content_extra_data wiring, staleness warning in output
"""

import json
import logging
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetcher as ft
import generate_brief as gb


# ── Sample Extra Data ─────────────────────────────────────────────────


def _sample_extra_data(generated_at=None):
    """Build a sample brief_data.json structure."""
    if generated_at is None:
        generated_at = datetime.now().isoformat()
    return {
        "generated_at": generated_at,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "portfolio_snapshot": [
            {"symbol": "AAPL", "sector": "tech", "date": "2026-03-17",
             "price": 190.50, "change_pct": 1.25, "volume": 50000000},
            {"symbol": "NVDA", "sector": "semiconductors", "date": "2026-03-17",
             "price": 800.00, "change_pct": -2.10, "volume": 40000000},
            {"symbol": "SPY", "sector": "etfs", "date": "2026-03-17",
             "price": 450.00, "change_pct": 0.30, "volume": 80000000},
        ],
        "technical_signals": {
            "AAPL": {
                "symbol": "AAPL", "latest_close": 190.50, "sma_20": 185.0,
                "price_vs_sma20": "above", "total_return_pct": 8.5,
                "max_drawdown_pct": -5.0, "daily_volatility": 0.015,
            },
            "NVDA": {
                "symbol": "NVDA", "latest_close": 800.0, "sma_20": 820.0,
                "price_vs_sma20": "below", "total_return_pct": -3.0,
                "max_drawdown_pct": -18.0, "daily_volatility": 0.025,
            },
        },
        "valuation_check": [
            {"symbol": "AAPL", "pe_ratio": 28.5, "pb_ratio": 12.3,
             "fcf_yield": 3.5, "earnings_yield": 3.8},
        ],
        "risk_dashboard": {
            "portfolio": {"avg_pairwise_correlation": 0.45, "sector_concentration": {}},
            "most_volatile_3": ["NVDA", "AAPL", "MSFT"],
            "least_volatile_3": ["SPY", "QQQ", "FXI"],
            "per_symbol": [],
        },
        "macro_snapshot": {
            "indicators": [
                {"series_id": "VIXCLS", "latest_value": 22.5, "change_1m": 3.2},
                {"series_id": "DGS10", "latest_value": 4.25, "change_1m": -0.1},
            ],
            "yield_curve_status": "normal",
            "vix_regime": "medium",
            "rate_direction": "stable",
        },
        "sec_activity": {
            "per_symbol": [],
            "recent_8k_activity": [
                {"symbol": "AAPL", "filing_date": "2026-03-10",
                 "description": "Earnings release"},
            ],
            "inactive_symbols": [],
        },
        "alerts": [
            {"severity": "warning", "category": "risk",
             "message": "NVDA: max drawdown -18% exceeds -15% threshold"},
        ],
    }


# ===================================================================
# ContentFetcher.fetch_extra_data
# ===================================================================


class TestFetchExtraData(unittest.TestCase):
    """Tests for fetcher.ContentFetcher.fetch_extra_data()."""

    def _make_fetcher(self, config=None):
        logger = logging.getLogger("test_extra_data")
        logger.handlers = []
        return ft.ContentFetcher(config or {}, logger)

    def test_returns_none_when_no_path_configured(self):
        f = self._make_fetcher({})
        result = f.fetch_extra_data()
        self.assertIsNone(result)

    def test_returns_none_when_file_missing(self):
        f = self._make_fetcher({"extra_data_path": "/nonexistent/path.json"})
        result = f.fetch_extra_data()
        self.assertIsNone(result)

    def test_loads_valid_json(self):
        data = _sample_extra_data()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            result = f.fetch_extra_data()
            self.assertIsNotNone(result)
            self.assertEqual(result["date"], data["date"])
            self.assertIsNone(result.get("_stale"))
        finally:
            os.unlink(tmp_path)

    def test_stores_data_on_instance(self):
        data = _sample_extra_data()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            f.fetch_extra_data()
            self.assertIsNotNone(f.extra_data)
            self.assertEqual(len(f.extra_data["portfolio_snapshot"]), 3)
        finally:
            os.unlink(tmp_path)

    def test_expands_tilde_in_path(self):
        """Tilde expansion should work for home directory paths."""
        f = self._make_fetcher({"extra_data_path": "~/nonexistent_file.json"})
        # Should not crash, just return None (file doesn't exist)
        result = f.fetch_extra_data()
        self.assertIsNone(result)

    def test_handles_corrupt_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("{invalid json!!")
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            result = f.fetch_extra_data()
            self.assertIsNone(result)
        finally:
            os.unlink(tmp_path)


# ===================================================================
# Staleness check
# ===================================================================


class TestStalenessCheck(unittest.TestCase):
    """Tests for the 2-day staleness detection in fetch_extra_data()."""

    def _make_fetcher(self, config=None):
        logger = logging.getLogger("test_stale")
        logger.handlers = []
        return ft.ContentFetcher(config or {}, logger)

    def test_fresh_data_not_marked_stale(self):
        data = _sample_extra_data(generated_at=datetime.now().isoformat())
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            f.fetch_extra_data()
            self.assertFalse(f.extra_data.get("_stale", False))
        finally:
            os.unlink(tmp_path)

    def test_1_day_old_not_stale(self):
        old_time = (datetime.now() - timedelta(days=1)).isoformat()
        data = _sample_extra_data(generated_at=old_time)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            f.fetch_extra_data()
            self.assertFalse(f.extra_data.get("_stale", False))
        finally:
            os.unlink(tmp_path)

    def test_3_day_old_is_stale(self):
        old_time = (datetime.now() - timedelta(days=3)).isoformat()
        data = _sample_extra_data(generated_at=old_time)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            f.fetch_extra_data()
            self.assertTrue(f.extra_data.get("_stale"))
            self.assertIn("STALE", f.extra_data.get("_stale_message", ""))
        finally:
            os.unlink(tmp_path)

    def test_7_day_old_is_stale(self):
        old_time = (datetime.now() - timedelta(days=7)).isoformat()
        data = _sample_extra_data(generated_at=old_time)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            f.fetch_extra_data()
            self.assertTrue(f.extra_data["_stale"])
            self.assertIn("7 days", f.extra_data["_stale_message"])
        finally:
            os.unlink(tmp_path)

    def test_missing_generated_at_no_crash(self):
        data = _sample_extra_data()
        del data["generated_at"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            f = self._make_fetcher({"extra_data_path": tmp_path})
            result = f.fetch_extra_data()
            self.assertIsNotNone(result)
            # No crash, no stale flag (can't determine age)
            self.assertFalse(result.get("_stale", False))
        finally:
            os.unlink(tmp_path)


# ===================================================================
# _format_extra_data_for_prompt
# ===================================================================


class TestFormatExtraDataForPrompt(unittest.TestCase):
    """Tests for fetcher.ContentFetcher._format_extra_data_for_prompt()."""

    def _make_fetcher_with_data(self, data=None):
        logger = logging.getLogger("test_format")
        logger.handlers = []
        f = ft.ContentFetcher({}, logger)
        f.extra_data = data or _sample_extra_data()
        return f

    def test_empty_data_returns_empty_string(self):
        logger = logging.getLogger("test_format")
        f = ft.ContentFetcher({}, logger)
        result = f._format_extra_data_for_prompt()
        self.assertEqual(result, "")

    def test_contains_portfolio_snapshot_table(self):
        f = self._make_fetcher_with_data()
        result = f._format_extra_data_for_prompt()
        self.assertIn("Portfolio Price Snapshot", result)
        self.assertIn("AAPL", result)
        self.assertIn("NVDA", result)
        self.assertIn("$190.50", result)

    def test_contains_technical_signals(self):
        f = self._make_fetcher_with_data()
        result = f._format_extra_data_for_prompt()
        self.assertIn("Technical Signals", result)
        self.assertIn("Bullish", result)
        self.assertIn("Bearish", result)

    def test_contains_valuation_screen(self):
        f = self._make_fetcher_with_data()
        result = f._format_extra_data_for_prompt()
        self.assertIn("Valuation Screen", result)
        self.assertIn("28.5", result)  # PE ratio

    def test_contains_risk_dashboard(self):
        f = self._make_fetcher_with_data()
        result = f._format_extra_data_for_prompt()
        self.assertIn("Risk Dashboard", result)
        self.assertIn("Most Volatile", result)
        self.assertIn("0.45", result)  # correlation

    def test_contains_macro_snapshot(self):
        f = self._make_fetcher_with_data()
        result = f._format_extra_data_for_prompt()
        self.assertIn("Macro Snapshot", result)
        self.assertIn("normal", result)  # yield curve
        self.assertIn("medium", result)  # VIX regime

    def test_contains_sec_activity(self):
        f = self._make_fetcher_with_data()
        result = f._format_extra_data_for_prompt()
        self.assertIn("SEC 8-K", result)
        self.assertIn("AAPL", result)
        self.assertIn("Earnings release", result)

    def test_contains_alerts(self):
        f = self._make_fetcher_with_data()
        result = f._format_extra_data_for_prompt()
        self.assertIn("Quantitative Alerts", result)
        self.assertIn("WARNING", result)
        self.assertIn("NVDA", result)

    def test_stale_data_shows_warning(self):
        data = _sample_extra_data()
        data["_stale"] = True
        data["_stale_message"] = "Extra data is STALE (5 days old)"
        f = self._make_fetcher_with_data(data)
        result = f._format_extra_data_for_prompt()
        self.assertIn("STALE", result)
        self.assertIn("5 days old", result)

    def test_handles_missing_sections_gracefully(self):
        """Partial data should not crash the formatter."""
        data = {
            "generated_at": datetime.now().isoformat(),
            "portfolio_snapshot": [],
            "technical_signals": {},
            "valuation_check": [],
            "risk_dashboard": {},
            "macro_snapshot": {},
            "sec_activity": {},
            "alerts": [],
        }
        f = self._make_fetcher_with_data(data)
        result = f._format_extra_data_for_prompt()
        # Should produce empty or minimal output, no crash
        self.assertIsInstance(result, str)

    def test_handles_none_values_in_valuation(self):
        data = _sample_extra_data()
        data["valuation_check"] = [
            {"symbol": "BABA", "pe_ratio": None, "pb_ratio": None,
             "fcf_yield": None, "earnings_yield": None},
        ]
        f = self._make_fetcher_with_data(data)
        result = f._format_extra_data_for_prompt()
        self.assertIn("N/A", result)


# ===================================================================
# get_formatted_sections includes extra_data
# ===================================================================


class TestGetFormattedSectionsWithExtraData(unittest.TestCase):
    """Tests that get_formatted_sections() includes extra_data when data is loaded."""

    def test_includes_extra_data_key_when_data_present(self):
        logger = logging.getLogger("test_sections")
        f = ft.ContentFetcher({}, logger)
        f.extra_data = _sample_extra_data()
        sections = f.get_formatted_sections()
        self.assertIn("extra_data", sections)
        self.assertIn("AAPL", sections["extra_data"])

    def test_excludes_extra_data_key_when_no_data(self):
        logger = logging.getLogger("test_sections")
        f = ft.ContentFetcher({}, logger)
        sections = f.get_formatted_sections()
        self.assertNotIn("extra_data", sections)


# ===================================================================
# fetch_all includes extra_data step
# ===================================================================


class TestFetchAllWithExtraData(unittest.TestCase):
    """Test that fetch_all() calls fetch_extra_data when configured."""

    def test_fetch_all_calls_extra_data_when_configured(self):
        data = _sample_extra_data()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            config = {
                "extra_data_path": tmp_path,
                "rss_sources": [],
                "arxiv_categories": [],
                "web_only_sources": [],
                "twitter_accounts": [],
            }
            logger = logging.getLogger("test_fetch_all")
            logger.handlers = []
            f = ft.ContentFetcher(config, logger)
            f.fetch_all()
            self.assertIsNotNone(f.extra_data)
        finally:
            os.unlink(tmp_path)

    def test_fetch_all_skips_extra_data_when_not_configured(self):
        config = {
            "rss_sources": [],
            "arxiv_categories": [],
            "web_only_sources": [],
            "twitter_accounts": [],
        }
        logger = logging.getLogger("test_fetch_all")
        logger.handlers = []
        f = ft.ContentFetcher(config, logger)
        f.fetch_all()
        self.assertIsNone(f.extra_data)


# ===================================================================
# BriefGenerator staleness warning in output
# ===================================================================


class TestBriefGeneratorExtraDataWiring(unittest.TestCase):
    """Test that generate_brief.py wires extra data into prompt_vars."""

    def test_content_extra_data_in_prompt_vars(self):
        """Verify _build_portfolio_context and content_extra_data are wired."""
        # Create a generator with a temp config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump({
                "rss_sources": [],
                "web_only_sources": [],
                "twitter_accounts": [],
                "arxiv_categories": [],
                "template": "templates/portfolio-brief.md",
                "prompt": "prompts/portfolio-brief.md",
                "output_dir": tempfile.mkdtemp(),
            }, tmp)
            config_path = tmp.name

        try:
            gen = gb.BriefGenerator(config_path=config_path)
            # Simulate extra data loaded on fetcher
            gen.fetcher.extra_data = _sample_extra_data()

            sections = gen.fetcher.get_formatted_sections()
            self.assertIn("extra_data", sections)
        finally:
            os.unlink(config_path)

    def test_stale_warning_appended_to_output(self):
        """When extra data is stale, a DATA WARNING should be appended."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump({
                "rss_sources": [],
                "web_only_sources": [],
                "twitter_accounts": [],
                "arxiv_categories": [],
                "template": "templates/portfolio-brief.md",
                "prompt": "prompts/portfolio-brief.md",
                "output_dir": tempfile.mkdtemp(),
            }, tmp)
            config_path = tmp.name

        try:
            gen = gb.BriefGenerator(config_path=config_path)
            # Simulate stale extra data
            gen.fetcher.extra_data = _sample_extra_data()
            gen.fetcher.extra_data["_stale"] = True
            gen.fetcher.extra_data["_stale_message"] = "Extra data is STALE (5 days old)"

            # Mock the summarizer to return a simple brief
            gen.summarizer.summarize = lambda tmpl, vars: "# Test Brief\n\nContent here."

            brief = gen.generate_brief()
            self.assertIn("DATA WARNING", brief)
            self.assertIn("STALE", brief)
        finally:
            os.unlink(config_path)

    def test_no_warning_when_data_fresh(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump({
                "rss_sources": [],
                "web_only_sources": [],
                "twitter_accounts": [],
                "arxiv_categories": [],
                "template": "templates/portfolio-brief.md",
                "prompt": "prompts/portfolio-brief.md",
                "output_dir": tempfile.mkdtemp(),
            }, tmp)
            config_path = tmp.name

        try:
            gen = gb.BriefGenerator(config_path=config_path)
            gen.fetcher.extra_data = _sample_extra_data()
            # No _stale flag

            gen.summarizer.summarize = lambda tmpl, vars: "# Test Brief\n\nContent here."

            brief = gen.generate_brief()
            self.assertNotIn("DATA WARNING", brief)
        finally:
            os.unlink(config_path)


if __name__ == "__main__":
    unittest.main()
