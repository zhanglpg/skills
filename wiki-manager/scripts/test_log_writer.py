"""Tests for log_writer.py."""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from log_writer import append_log, read_log


class TestAppendLog(unittest.TestCase):
    """Tests for append_log."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "log.md"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_log_file(self):
        self.assertFalse(self.log_path.exists())
        append_log(self.log_path, "ingest", "Test Paper")
        self.assertTrue(self.log_path.exists())

    def test_log_header(self):
        append_log(self.log_path, "ingest", "Test Paper")
        content = self.log_path.read_text()
        self.assertIn("Wiki Activity Log", content)

    def test_log_entry_content(self):
        ts = datetime(2026, 4, 5, 14, 30)
        append_log(self.log_path, "ingest", '"Paper A"', timestamp=ts)
        content = self.log_path.read_text()
        self.assertIn("## 2026-04-05", content)
        self.assertIn("14:30", content)
        self.assertIn("ingest", content)
        self.assertIn("Paper A", content)

    def test_log_details(self):
        append_log(
            self.log_path,
            "ingest",
            "Paper A",
            details=["Created entity: [[Transformer]]", "Updated index"],
        )
        content = self.log_path.read_text()
        self.assertIn("Created entity: [[Transformer]]", content)
        self.assertIn("Updated index", content)

    def test_multiple_entries_same_day(self):
        ts1 = datetime(2026, 4, 5, 14, 0)
        ts2 = datetime(2026, 4, 5, 15, 0)
        append_log(self.log_path, "ingest", "Paper A", timestamp=ts1)
        append_log(self.log_path, "ingest", "Paper B", timestamp=ts2)
        content = self.log_path.read_text()
        # Date heading should appear only once
        self.assertEqual(content.count("## 2026-04-05"), 1)
        self.assertIn("Paper A", content)
        self.assertIn("Paper B", content)

    def test_different_days(self):
        ts1 = datetime(2026, 4, 5, 14, 0)
        ts2 = datetime(2026, 4, 6, 10, 0)
        append_log(self.log_path, "ingest", "Paper A", timestamp=ts1)
        append_log(self.log_path, "lint", "Clean", timestamp=ts2)
        content = self.log_path.read_text()
        self.assertIn("## 2026-04-05", content)
        self.assertIn("## 2026-04-06", content)


class TestReadLog(unittest.TestCase):
    """Tests for read_log."""

    def test_missing_log(self):
        result = read_log("/nonexistent/log.md")
        self.assertIn("No log file", result)

    def test_reads_existing(self):
        tmpdir = tempfile.mkdtemp()
        log_path = Path(tmpdir) / "log.md"
        append_log(log_path, "ingest", "Paper A")
        result = read_log(log_path)
        self.assertIn("Paper A", result)
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
