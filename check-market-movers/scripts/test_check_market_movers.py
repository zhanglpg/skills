#!/usr/bin/env python3
"""Unit tests for check-market-movers.py."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure the script directory is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock yfinance before importing the module
sys.modules['yfinance'] = MagicMock()
sys.modules['pandas'] = MagicMock()

import importlib
cmm = importlib.import_module('check-market-movers')


class TestCheckSignificantEventsStocks(unittest.TestCase):
    """Tests for stock-specific threshold logic in check_significant_events."""

    def test_stock_above_threshold_triggers_interrupt(self):
        data = {'holdings': {'GOOG': {'change_pct': 6.0}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertTrue(should_interrupt)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'portfolio_move')
        self.assertEqual(events[0]['symbol'], 'GOOG')

    def test_stock_below_threshold_no_interrupt(self):
        data = {'holdings': {'GOOG': {'change_pct': 2.0}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertFalse(should_interrupt)
        self.assertEqual(len(events), 0)

    def test_stock_exactly_at_threshold_triggers(self):
        data = {'holdings': {'NVDA': {'change_pct': 5.0}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertTrue(should_interrupt)
        self.assertEqual(events[0]['symbol'], 'NVDA')

    def test_negative_move_above_threshold_triggers(self):
        data = {'holdings': {'BABA': {'change_pct': -7.0}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertTrue(should_interrupt)
        self.assertEqual(events[0]['change'], -7.0)

    def test_severity_medium_at_threshold(self):
        data = {'holdings': {'GOOG': {'change_pct': 5.0}}, 'news': []}
        _, events = cmm.check_significant_events(data)
        self.assertEqual(events[0]['severity'], 'medium')

    def test_severity_high_above_1_5x_threshold(self):
        # Stock threshold is 5.0, so 1.5x = 7.5. A move > 7.5 is "high".
        data = {'holdings': {'GOOG': {'change_pct': 8.0}}, 'news': []}
        _, events = cmm.check_significant_events(data)
        self.assertEqual(events[0]['severity'], 'high')


class TestCheckSignificantEventsETFs(unittest.TestCase):
    """Tests for ETF-specific threshold logic."""

    def test_etf_uses_lower_threshold(self):
        # ETF threshold is 3.0 (not 5.0 like stocks)
        data = {'holdings': {'SPY': {'change_pct': 3.5}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertTrue(should_interrupt)
        self.assertEqual(events[0]['symbol'], 'SPY')

    def test_etf_below_threshold_no_interrupt(self):
        data = {'holdings': {'FXI': {'change_pct': 2.0}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertFalse(should_interrupt)

    def test_kweb_classified_as_etf(self):
        data = {'holdings': {'KWEB': {'change_pct': 3.0}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertTrue(should_interrupt)


class TestCheckSignificantEventsChina(unittest.TestCase):
    """Tests for China exposure detection."""

    def test_china_market_move_detected(self):
        data = {'holdings': {'FXI': {'change_pct': 5.0}}, 'news': []}
        _, events = cmm.check_significant_events(data)
        china_events = [e for e in events if e['type'] == 'china_market_move']
        self.assertGreater(len(china_events), 0)
        self.assertIn('China portfolio', china_events[0]['note'])

    def test_china_move_severity_high_above_6(self):
        data = {'holdings': {'FXI': {'change_pct': -7.0}}, 'news': []}
        _, events = cmm.check_significant_events(data)
        china_events = [e for e in events if e['type'] == 'china_market_move']
        self.assertEqual(china_events[0]['severity'], 'high')

    def test_china_move_severity_medium_below_6(self):
        data = {'holdings': {'KWEB': {'change_pct': 5.0}}, 'news': []}
        _, events = cmm.check_significant_events(data)
        china_events = [e for e in events if e['type'] == 'china_market_move']
        self.assertEqual(china_events[0]['severity'], 'medium')

    def test_china_below_threshold_no_china_event(self):
        data = {'holdings': {'FXI': {'change_pct': 2.0}}, 'news': []}
        _, events = cmm.check_significant_events(data)
        china_events = [e for e in events if e['type'] == 'china_market_move']
        self.assertEqual(len(china_events), 0)


class TestCheckSignificantEventsNews(unittest.TestCase):
    """Tests for portfolio-relevant news detection."""

    def test_high_significance_portfolio_news_interrupts(self):
        data = {
            'holdings': {},
            'news': [{
                'sector': 'Tech',
                'tickers': ['GOOG'],
                'significance': 'high',
                'headline': 'Major Google event',
                'source': 'Reuters',
            }],
        }
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertTrue(should_interrupt)
        news_events = [e for e in events if e['type'] == 'portfolio_news']
        self.assertEqual(len(news_events), 1)
        self.assertEqual(news_events[0]['headline'], 'Major Google event')

    def test_medium_significance_portfolio_news_no_interrupt(self):
        data = {
            'holdings': {},
            'news': [{
                'sector': 'Semiconductors',
                'tickers': ['NVDA'],
                'significance': 'medium',
                'headline': 'Chip news',
                'source': 'Bloomberg',
            }],
        }
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertFalse(should_interrupt)
        # Medium news is added to events but doesn't trigger interrupt
        news_events = [e for e in events if e['type'] == 'portfolio_news']
        self.assertEqual(len(news_events), 1)

    def test_non_portfolio_news_ignored(self):
        data = {
            'holdings': {},
            'news': [{
                'sector': 'Healthcare',
                'tickers': ['PFE'],
                'significance': 'high',
                'headline': 'Pharma news',
                'source': 'Reuters',
            }],
        }
        _, events = cmm.check_significant_events(data)
        news_events = [e for e in events if e['type'] == 'portfolio_news']
        self.assertEqual(len(news_events), 0)

    def test_news_related_tickers_filtered_to_portfolio(self):
        data = {
            'holdings': {},
            'news': [{
                'sector': 'Tech',
                'tickers': ['GOOG', 'AAPL', 'MSFT'],
                'significance': 'high',
                'headline': 'Big tech news',
                'source': 'Reuters',
            }],
        }
        _, events = cmm.check_significant_events(data)
        news_events = [e for e in events if e['type'] == 'portfolio_news']
        self.assertEqual(news_events[0]['related_tickers'], ['GOOG'])


class TestCheckSignificantEventsEdgeCases(unittest.TestCase):
    """Edge case tests for check_significant_events."""

    def test_empty_holdings(self):
        data = {'holdings': {}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertFalse(should_interrupt)
        self.assertEqual(len(events), 0)

    def test_none_change_pct_skipped(self):
        data = {'holdings': {'GOOG': {'change_pct': None}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertFalse(should_interrupt)

    def test_non_portfolio_ticker_ignored(self):
        data = {'holdings': {'AAPL': {'change_pct': 10.0}}, 'news': []}
        should_interrupt, events = cmm.check_significant_events(data)
        self.assertFalse(should_interrupt)

    def test_multiple_events_all_returned(self):
        data = {
            'holdings': {
                'GOOG': {'change_pct': 6.0},
                'NVDA': {'change_pct': -8.0},
            },
            'news': [],
        }
        _, events = cmm.check_significant_events(data)
        portfolio_events = [e for e in events if e['type'] == 'portfolio_move']
        self.assertEqual(len(portfolio_events), 2)


class TestFormatReport(unittest.TestCase):
    """Tests for format_report."""

    def _make_data(self, holdings=None):
        return {
            'holdings': holdings or {},
            'fetched_at': '2026-03-06T10:00:00',
        }

    @patch.object(cmm, 'datetime')
    def test_report_contains_header(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        data = self._make_data()
        report = cmm.format_report(data, [])
        self.assertIn('Portfolio Check', report)
        self.assertIn('2026-03-06', report)

    @patch.object(cmm, 'datetime')
    def test_report_contains_portfolio_table(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        data = self._make_data({
            'GOOG': {'price': 150.25, 'change_pct': 2.5},
        })
        report = cmm.format_report(data, [])
        self.assertIn('GOOG', report)
        self.assertIn('$150.25', report)
        self.assertIn('+2.50%', report)

    @patch.object(cmm, 'datetime')
    def test_tsm_displayed_as_tsmc(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        data = self._make_data({
            'TSM': {'price': 100.0, 'change_pct': 1.0},
        })
        report = cmm.format_report(data, [])
        self.assertIn('TSMC', report)

    @patch.object(cmm, 'datetime')
    def test_null_price_shows_na(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        data = self._make_data({
            'GOOG': {'price': None, 'change_pct': None},
        })
        report = cmm.format_report(data, [])
        self.assertIn('N/A', report)

    @patch.object(cmm, 'datetime')
    def test_events_section_present_when_events_exist(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        events = [{'type': 'portfolio_move', 'symbol': 'GOOG', 'name': 'Alphabet',
                    'sector': 'Tech', 'change': 6.0, 'severity': 'medium'}]
        data = self._make_data()
        report = cmm.format_report(data, events)
        self.assertIn('Portfolio Events', report)
        self.assertIn('GOOG', report)
        self.assertIn('+6.00%', report)

    @patch.object(cmm, 'datetime')
    def test_no_events_section_when_empty(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        data = self._make_data()
        report = cmm.format_report(data, [])
        self.assertNotIn('Portfolio Events', report)

    @patch.object(cmm, 'datetime')
    def test_portfolio_news_event_format(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        events = [{'type': 'portfolio_news', 'headline': 'Big News',
                    'source': 'Reuters', 'related_tickers': ['GOOG'],
                    'sector': 'Tech', 'severity': 'high'}]
        data = self._make_data()
        report = cmm.format_report(data, events)
        self.assertIn('Big News', report)

    @patch.object(cmm, 'datetime')
    def test_china_market_event_format(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        events = [{'type': 'china_market_move', 'symbol': 'FXI',
                    'change': -5.0, 'severity': 'medium',
                    'note': 'Affects China portfolio (BABA, FXI, KWEB)'}]
        data = self._make_data()
        report = cmm.format_report(data, events)
        self.assertIn('FXI', report)
        self.assertIn('-5.00%', report)

    @patch.object(cmm, 'datetime')
    def test_green_indicator_for_positive_change(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        data = self._make_data({'GOOG': {'price': 150.0, 'change_pct': 2.0}})
        report = cmm.format_report(data, [])
        self.assertIn('\U0001f7e2', report)  # green circle

    @patch.object(cmm, 'datetime')
    def test_red_indicator_for_negative_change(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 6, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        data = self._make_data({'GOOG': {'price': 150.0, 'change_pct': -1.0}})
        report = cmm.format_report(data, [])
        self.assertIn('\U0001f534', report)  # red circle


class TestSaveReport(unittest.TestCase):
    """Tests for save_report."""

    def test_saves_file_with_correct_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(cmm, 'OUTPUT_DIR', tmpdir):
                # Re-create OUTPUT_DIR as a Path
                from pathlib import Path
                cmm.OUTPUT_DIR = Path(tmpdir)
                ts = datetime(2026, 3, 6, 14, 0, 0)
                filepath = cmm.save_report("# Report content", ts)
                self.assertTrue(filepath.exists())
                self.assertEqual(filepath.name, '2026-03-06-14-check.md')
                content = filepath.read_text()
                self.assertEqual(content, "# Report content")

    def test_creates_directory_if_needed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            nested = Path(tmpdir) / 'deep' / 'nested'
            cmm.OUTPUT_DIR = nested
            ts = datetime(2026, 3, 6, 14, 0, 0)
            filepath = cmm.save_report("content", ts)
            self.assertTrue(filepath.exists())


class TestUpdateState(unittest.TestCase):
    """Tests for update_state."""

    def test_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            state_file = Path(tmpdir) / 'state.json'
            original = cmm.STATE_FILE
            cmm.STATE_FILE = state_file
            try:
                cmm.update_state([])
                state = json.loads(state_file.read_text())
                self.assertIn('marketMoversCheck', state)
                self.assertIn('portfolio', state)
            finally:
                cmm.STATE_FILE = original

    def test_tsm_mapped_to_tsmc_in_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            state_file = Path(tmpdir) / 'state.json'
            original = cmm.STATE_FILE
            cmm.STATE_FILE = state_file
            try:
                cmm.update_state([])
                state = json.loads(state_file.read_text())
                holdings = state['portfolio']['holdings']
                self.assertIn('TSMC', holdings)
                self.assertNotIn('TSM', holdings)
            finally:
                cmm.STATE_FILE = original

    def test_events_stored_in_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            state_file = Path(tmpdir) / 'state.json'
            original = cmm.STATE_FILE
            cmm.STATE_FILE = state_file
            try:
                event = {'type': 'portfolio_move', 'symbol': 'GOOG', 'change': 6.0}
                cmm.update_state([event])
                state = json.loads(state_file.read_text())
                self.assertEqual(
                    state['marketMoversCheck']['lastSignificantEvent']['symbol'], 'GOOG')
            finally:
                cmm.STATE_FILE = original

    def test_no_events_null_last_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            state_file = Path(tmpdir) / 'state.json'
            original = cmm.STATE_FILE
            cmm.STATE_FILE = state_file
            try:
                cmm.update_state([])
                state = json.loads(state_file.read_text())
                self.assertIsNone(state['marketMoversCheck']['lastSignificantEvent'])
            finally:
                cmm.STATE_FILE = original


class TestGetMarketData(unittest.TestCase):
    """Tests for get_market_data."""

    @patch.object(cmm, 'yf')
    def test_returns_expected_structure(self, mock_yf):
        import pandas as pd
        # Create a mock DataFrame that behaves like yfinance output
        mock_df = MagicMock()
        mock_df.__len__ = lambda self: 1

        def mock_getitem(key):
            col_mock = MagicMock()
            col_mock.iloc.__getitem__ = lambda self, idx: 150.0
            return col_mock

        mock_df.__getitem__ = mock_getitem
        mock_yf.download.return_value = mock_df

        result = cmm.get_market_data()
        self.assertIn('holdings', result)
        self.assertIn('fetched_at', result)
        self.assertIn('news', result)
        # All portfolio tickers should be in holdings
        for ticker in cmm.PORTFOLIO:
            self.assertIn(ticker, result['holdings'])

    @patch.object(cmm, 'yf')
    def test_handles_download_exception(self, mock_yf):
        mock_yf.download.side_effect = Exception("Network error")
        result = cmm.get_market_data()
        self.assertIn('holdings', result)
        # All holdings should have None values
        for _ticker, holding in result['holdings'].items():
            self.assertIsNone(holding['price'])
            self.assertIsNone(holding['change_pct'])

    @patch.object(cmm, 'yf')
    def test_handles_empty_dataframe(self, mock_yf):
        mock_df = MagicMock()
        mock_df.__len__ = lambda self: 0
        mock_yf.download.return_value = mock_df

        result = cmm.get_market_data()
        self.assertIn('holdings', result)


class TestMain(unittest.TestCase):
    """Tests for the main function."""

    @patch.object(cmm, 'update_state')
    @patch.object(cmm, 'check_significant_events', return_value=(False, []))
    @patch.object(cmm, 'get_market_data', return_value={'holdings': {}, 'news': [], 'fetched_at': ''})
    def test_returns_0_when_no_events(self, mock_data, mock_check, mock_state):
        with patch('sys.argv', ['check-market-movers.py']):
            result = cmm.main()
        self.assertEqual(result, 0)

    @patch.object(cmm, 'save_report', return_value=MagicMock())
    @patch.object(cmm, 'format_report', return_value='# Report')
    @patch.object(cmm, 'update_state')
    @patch.object(cmm, 'check_significant_events')
    @patch.object(cmm, 'get_market_data', return_value={'holdings': {}, 'news': [], 'fetched_at': ''})
    def test_returns_1_when_events_found(self, mock_data, mock_check, mock_state, mock_format, mock_save):
        mock_check.return_value = (True, [{'type': 'portfolio_move', 'symbol': 'GOOG', 'change': 6.0}])
        with patch('sys.argv', ['check-market-movers.py']):
            result = cmm.main()
        self.assertEqual(result, 1)

    @patch.object(cmm, 'update_state')
    @patch.object(cmm, 'check_significant_events', return_value=(False, []))
    @patch.object(cmm, 'get_market_data', return_value={'holdings': {}, 'news': [], 'fetched_at': ''})
    def test_always_calls_update_state(self, mock_data, mock_check, mock_state):
        with patch('sys.argv', ['check-market-movers.py']):
            cmm.main()
        mock_state.assert_called_once()


if __name__ == '__main__':
    unittest.main()
