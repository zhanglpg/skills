#!/usr/bin/env python3
"""Unit tests for the paper-digest skill."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import digest_paper


class TestArxivPatterns(unittest.TestCase):
    """Test arXiv ID and URL pattern matching."""

    def test_bare_arxiv_id(self):
        m = digest_paper.ARXIV_ID_PATTERN.match('2401.12345')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '2401.12345')

    def test_bare_arxiv_id_with_version(self):
        m = digest_paper.ARXIV_ID_PATTERN.match('2401.12345v2')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '2401.12345')
        self.assertEqual(m.group(2), 'v2')

    def test_bare_arxiv_id_short(self):
        m = digest_paper.ARXIV_ID_PATTERN.match('2401.1234')
        self.assertIsNotNone(m)

    def test_not_arxiv_id(self):
        m = digest_paper.ARXIV_ID_PATTERN.match('paper.pdf')
        self.assertIsNone(m)

    def test_arxiv_abs_url(self):
        url = 'https://arxiv.org/abs/2401.12345'
        m = digest_paper.ARXIV_ABS_PATTERN.search(url)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '2401.12345')

    def test_arxiv_pdf_url(self):
        url = 'https://arxiv.org/pdf/2401.12345'
        m = digest_paper.ARXIV_PDF_PATTERN.search(url)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '2401.12345')

    def test_arxiv_abs_url_with_version(self):
        url = 'https://arxiv.org/abs/2401.12345v3'
        m = digest_paper.ARXIV_ABS_PATTERN.search(url)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), 'v3')


class TestExtractTitle(unittest.TestCase):
    """Test title extraction from paper text."""

    def test_simple_title(self):
        text = "\n--- Page 1 ---\nAttention Is All You Need\nAuthors here\n"
        title = digest_paper.extract_title(text)
        self.assertEqual(title, "Attention Is All You Need")

    def test_skips_blank_lines(self):
        text = "\n\n\n--- Page 1 ---\n\nMy Paper Title\nSomething else\n"
        title = digest_paper.extract_title(text)
        self.assertEqual(title, "My Paper Title")

    def test_skips_arxiv_header(self):
        text = "--- Page 1 ---\narXiv:2401.12345v1\nMy Real Title\n"
        title = digest_paper.extract_title(text)
        self.assertEqual(title, "My Real Title")

    def test_empty_text(self):
        title = digest_paper.extract_title("")
        self.assertEqual(title, "Untitled Paper")

    def test_skips_preprint_header(self):
        text = "--- Page 1 ---\nPreprint submitted to journal\nActual Title\n"
        title = digest_paper.extract_title(text)
        self.assertEqual(title, "Actual Title")


class TestResolveInput(unittest.TestCase):
    """Test input resolution logic."""

    def test_local_file(self):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            logger = MagicMock()
            pdf_path, source = digest_paper.resolve_input(f.name, logger)
            self.assertEqual(pdf_path, f.name)
            self.assertEqual(source, f.name)
            os.unlink(f.name)

    def test_local_file_not_found(self):
        logger = MagicMock()
        with self.assertRaises(FileNotFoundError):
            digest_paper.resolve_input('/nonexistent/paper.pdf', logger)

    @patch('digest_paper._download_arxiv')
    def test_arxiv_id_triggers_download(self, mock_dl):
        mock_dl.return_value = '/tmp/fake.pdf'
        logger = MagicMock()
        pdf_path, source = digest_paper.resolve_input('2401.12345', logger)
        mock_dl.assert_called_once_with('2401.12345', logger)
        self.assertEqual(source, 'arxiv:2401.12345')

    @patch('digest_paper._download_arxiv')
    def test_arxiv_abs_url_triggers_download(self, mock_dl):
        mock_dl.return_value = '/tmp/fake.pdf'
        logger = MagicMock()
        pdf_path, source = digest_paper.resolve_input(
            'https://arxiv.org/abs/2401.12345', logger
        )
        mock_dl.assert_called_once_with('2401.12345', logger)
        self.assertEqual(source, 'arxiv:2401.12345')

    @patch('digest_paper._fetch_url')
    def test_generic_url_downloads(self, mock_fetch):
        logger = MagicMock()
        pdf_path, source = digest_paper.resolve_input(
            'https://example.com/paper.pdf', logger
        )
        mock_fetch.assert_called_once()
        self.assertEqual(source, 'https://example.com/paper.pdf')
        # Clean up temp file
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


class TestBuildPrompt(unittest.TestCase):
    """Test prompt template assembly."""

    def test_fills_placeholders(self):
        template = "Paper: {paper_text}\nContext: {user_context}"
        result = digest_paper.build_prompt(template, {
            'paper_text': 'Hello world',
            'user_context': 'ML researcher',
        })
        self.assertIn('Hello world', result)
        self.assertIn('ML researcher', result)

    def test_missing_placeholder_safe(self):
        template = "Paper: {paper_text}\nExtra: {nonexistent}"
        result = digest_paper.build_prompt(template, {
            'paper_text': 'content',
        })
        self.assertIn('content', result)
        # Missing placeholder should not raise, should be empty
        self.assertIn('Extra: ', result)


class TestRenderOutput(unittest.TestCase):
    """Test output rendering."""

    def test_merges_frontmatter(self):
        gemini_output = (
            '---\ntitle: "My Paper"\nauthors:\n  - "Author One"\n'
            'year: 2024\ntags:\n  - deep-learning\ncategories:\n  - paper-digest\n'
            'related:\n  - "Related Paper"\n---\n\n## 1. Main Idea\nSome content'
        )
        result = digest_paper.render_output(gemini_output, "My Paper", "arxiv:2401.12345")
        self.assertIn('title: "My Paper"', result)
        self.assertIn('source: "arxiv:2401.12345"', result)
        self.assertIn("digested:", result)
        self.assertIn("status: digested", result)
        self.assertIn("## 1. Main Idea", result)
        # Should start with frontmatter
        self.assertTrue(result.startswith("---\n"))

    def test_fallback_without_frontmatter(self):
        result = digest_paper.render_output(
            "## 1. Main Idea\nSome content",
            "My Paper",
            "arxiv:2401.12345"
        )
        self.assertTrue(result.startswith("---\n"))
        self.assertIn('title: "My Paper"', result)
        self.assertIn('source: "arxiv:2401.12345"', result)
        self.assertIn("status: digested", result)
        self.assertIn("## 1. Main Idea", result)

    def test_strips_gemini_whitespace(self):
        result = digest_paper.render_output(
            "  \n  content here  \n  ",
            "Title",
            "source"
        )
        self.assertIn("content here", result)


class TestSaveOutput(unittest.TestCase):
    """Test file saving."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = digest_paper.save_output(
                "# Test digest content",
                "My Test Paper",
                tmpdir
            )
            self.assertTrue(filepath.exists())
            content = filepath.read_text()
            self.assertEqual(content, "# Test digest content")
            self.assertIn("my-test-paper", filepath.name)

    def test_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, 'sub', 'dir')
            filepath = digest_paper.save_output("content", "Title", nested)
            self.assertTrue(filepath.exists())

    def test_sanitizes_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = digest_paper.save_output(
                "content",
                "Paper: A <Special> Title! (2024)",
                tmpdir
            )
            # Filename should not contain special chars
            self.assertNotIn('<', filepath.name)
            self.assertNotIn('>', filepath.name)
            self.assertNotIn(':', filepath.name)


class TestRunGemini(unittest.TestCase):
    """Test Gemini CLI invocation."""

    @patch('subprocess.run')
    def test_successful_run(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Summary here")
        result = digest_paper.run_gemini("test prompt", timeout=30)
        self.assertEqual(result, "Summary here")

    @patch('subprocess.run')
    def test_gemini_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = digest_paper.run_gemini("test prompt", timeout=30, retry=0)
        self.assertIn("not found", result)

    @patch('subprocess.run')
    def test_retry_on_failure(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="error"),
            MagicMock(returncode=0, stdout="Success"),
        ]
        result = digest_paper.run_gemini("test prompt", timeout=30, retry=1)
        self.assertEqual(result, "Success")
        self.assertEqual(mock_run.call_count, 2)


class TestParseArgs(unittest.TestCase):
    """Test argument parsing."""

    def test_minimal_args(self):
        args = digest_paper.parse_args(['paper.pdf'])
        self.assertEqual(args.paper, 'paper.pdf')
        self.assertIsNone(args.config)
        self.assertIsNone(args.output_dir)

    def test_all_args(self):
        args = digest_paper.parse_args([
            '2401.12345',
            '--config', 'config.json',
            '--output_dir', '/tmp/out',
            '--gemini_timeout', '300',
            '--user_context', 'ML researcher',
        ])
        self.assertEqual(args.paper, '2401.12345')
        self.assertEqual(args.config, 'config.json')
        self.assertEqual(args.output_dir, '/tmp/out')
        self.assertEqual(args.gemini_timeout, 300)
        self.assertEqual(args.user_context, 'ML researcher')


class TestMainIntegration(unittest.TestCase):
    """Integration tests for the main function."""

    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_main_with_local_pdf(self, mock_extract, mock_gemini):
        mock_extract.return_value = "Paper Title\nThis is the paper content about ML."
        mock_gemini.return_value = "## 1. Main Idea\nTest summary output"

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            with tempfile.TemporaryDirectory() as tmpdir:
                result = digest_paper.main([f.name, '--output_dir', tmpdir])
                self.assertEqual(result, 0)
                # Check that a file was created
                files = list(Path(tmpdir).glob('*.md'))
                self.assertEqual(len(files), 1)
            os.unlink(f.name)

    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_main_with_empty_pdf(self, mock_extract, mock_gemini):
        mock_extract.return_value = ""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            result = digest_paper.main([f.name])
            self.assertEqual(result, 1)  # Should fail
            os.unlink(f.name)

    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_main_gemini_error(self, mock_extract, mock_gemini):
        mock_extract.return_value = "Paper Title\nContent here"
        mock_gemini.return_value = "Error: Gemini CLI failed after all retry attempts"

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            result = digest_paper.main([f.name])
            self.assertEqual(result, 1)
            os.unlink(f.name)


class TestLogFileDefault(unittest.TestCase):
    """Tests for log file path defaults."""

    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_default_log_file_uses_tmp(self, mock_extract, mock_gemini):
        mock_extract.return_value = "Paper Title\nContent for testing"
        mock_gemini.return_value = "## 1. Main Idea\nTest output"

        with patch('digest_paper.setup_logger') as mock_setup:
            mock_setup.return_value = MagicMock()
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(b'fake pdf')
                f.flush()
                with tempfile.TemporaryDirectory() as tmpdir:
                    digest_paper.main([f.name, '--output_dir', tmpdir])
                os.unlink(f.name)
            # setup_logger should have been called with the default /tmp path
            call_args = mock_setup.call_args
            log_file_arg = call_args[0][0] if call_args[0] else call_args[1].get('log_file')
            self.assertTrue(log_file_arg.startswith('/tmp/'))

    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_config_overrides_log_file(self, mock_extract, mock_gemini):
        mock_extract.return_value = "Paper Title\nContent for testing"
        mock_gemini.return_value = "## 1. Main Idea\nTest output"

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({'log_file': '/custom/log/path.log'}, f)

            with patch('digest_paper.setup_logger') as mock_setup:
                mock_setup.return_value = MagicMock()
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pf:
                    pf.write(b'fake pdf')
                    pf.flush()
                    digest_paper.main([pf.name, '--config', config_path, '--output_dir', tmpdir])
                    os.unlink(pf.name)
                call_args = mock_setup.call_args
                log_file_arg = call_args[0][0] if call_args[0] else call_args[1].get('log_file')
                self.assertEqual(log_file_arg, '/custom/log/path.log')


class TestOutputDirAgentDataDirDefault(unittest.TestCase):
    """Test output_dir defaults to /tmp when AGENT_DATA_DIR is unset."""

    @patch.dict(os.environ, {}, clear=True)
    @patch('digest_paper.setup_logger')
    @patch('digest_paper.resolve_input')
    @patch('digest_paper.extract_text_from_pdf')
    @patch('digest_paper.load_template')
    @patch('digest_paper.run_gemini')
    @patch('digest_paper.save_output')
    def test_output_dir_defaults_to_tmp_when_agent_data_dir_unset(
        self, mock_save, mock_gemini, mock_template, mock_extract,
        mock_resolve, mock_logger
    ):
        os.environ.pop('AGENT_DATA_DIR', None)
        mock_logger.return_value = MagicMock()
        mock_resolve.return_value = ('/tmp/fake.pdf', 'fake.pdf')
        mock_extract.return_value = "Title\nfake paper text"
        mock_template.return_value = "{paper_text}\n{user_context}"
        mock_gemini.return_value = "# Digest"
        mock_save.return_value = Path('/tmp/digest.md')

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({'output_dir': '$AGENT_DATA_DIR/paper-digests'}, f)

            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pf:
                pf.write(b'fake pdf')
                pf.flush()
                digest_paper.main([pf.name, '--config', config_path])
                os.unlink(pf.name)

            # save_output was called with expanded path
            call_args = mock_save.call_args
            actual_output_dir = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get('output_dir')
            self.assertEqual(actual_output_dir, '/tmp/paper-digests')


if __name__ == '__main__':
    unittest.main()
