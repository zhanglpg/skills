#!/usr/bin/env python3
"""Unit tests for shared logging utilities."""

import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging_utils import get_agent_data_dir, setup_logger


class TestGetAgentDataDir(unittest.TestCase):
    """Tests for get_agent_data_dir()."""

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_to_tmp(self):
        # Remove AGENT_DATA_DIR if present in the cleared env
        os.environ.pop('AGENT_DATA_DIR', None)
        self.assertEqual(get_agent_data_dir(), '/tmp')

    @patch.dict(os.environ, {'AGENT_DATA_DIR': '/foo/bar'})
    def test_reads_env_var(self):
        self.assertEqual(get_agent_data_dir(), '/foo/bar')


class TestSetupLogger(unittest.TestCase):
    """Tests for setup_logger()."""

    def test_returns_logger_with_name(self):
        logger = setup_logger('test-skill')
        self.assertEqual(logger.name, 'test-skill')

    def test_console_handler_present(self):
        logger = setup_logger('console-test')
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)
                           and not isinstance(h, logging.FileHandler)]
        self.assertGreaterEqual(len(stream_handlers), 1)

    def test_file_handler_when_log_file_given(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, 'test.log')
            logger = setup_logger('file-test', log_file=log_path)
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            self.assertEqual(len(file_handlers), 1)
            # Clean up handlers to release file
            for h in logger.handlers[:]:
                h.close()
                logger.removeHandler(h)

    def test_no_file_handler_when_no_log_file(self):
        logger = setup_logger('no-file-test')
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(len(file_handlers), 0)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, 'deep', 'nested', 'test.log')
            logger = setup_logger('dir-test', log_file=log_path)
            self.assertTrue(os.path.isdir(os.path.join(tmpdir, 'deep', 'nested')))
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            self.assertEqual(len(file_handlers), 1)
            for h in logger.handlers[:]:
                h.close()
                logger.removeHandler(h)

    def test_tilde_expansion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch expanduser to redirect ~ to tmpdir
            with patch('os.path.expanduser', side_effect=lambda p: p.replace('~', tmpdir)):
                logger = setup_logger('tilde-test', log_file='~/logs/test.log')
                file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
                self.assertEqual(len(file_handlers), 1)
                actual_path = file_handlers[0].baseFilename
                self.assertTrue(actual_path.startswith(tmpdir))
                self.assertNotIn('~', actual_path)
                for h in logger.handlers[:]:
                    h.close()
                    logger.removeHandler(h)


if __name__ == '__main__':
    unittest.main()
