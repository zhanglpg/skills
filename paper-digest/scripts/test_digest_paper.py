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
            'related:\n  - "Related Paper"\n'
            'concepts:\n  - "Transformer"\n  - "Attention Mechanism"\n'
            '---\n\n## 1. Main Idea\nSome content'
        )
        result = digest_paper.render_output(gemini_output, "My Paper", "arxiv:2401.12345")
        self.assertIn('title: "My Paper"', result)
        self.assertIn('source: "arxiv:2401.12345"', result)
        self.assertIn("digested:", result)
        self.assertIn("status: digested", result)
        self.assertIn("## 1. Main Idea", result)
        # Concepts should be preserved in the merged frontmatter
        self.assertIn("concepts:", result)
        self.assertIn("Transformer", result)
        self.assertIn("Attention Mechanism", result)
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
            self.assertIn("My Test Paper", filepath.name)

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
    def test_output_dir_defaults_to_openclaw_when_agent_data_dir_unset(
        self, mock_save, mock_gemini, mock_template, mock_extract,
        mock_resolve, mock_logger
    ):
        os.environ.pop('AGENT_DATA_DIR', None)
        fallback = os.path.expanduser('~/.openclaw')
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
            self.assertEqual(actual_output_dir, f'{fallback}/paper-digests')


class TestLoadConceptIndex(unittest.TestCase):
    """Tests for loading concept_index.md."""

    def test_loads_concept_lines(self):
        content = (
            "---\ntitle: Concept Index\ntype: concept-index\n"
            "date-updated: 2026-04-05\n---\n\n"
            "# Concept Index\n\n"
            "> Auto-generated. Do not edit manually.\n\n"
            "- Transformer | aliases: Transformer Architecture, Transformer Model\n"
            "- RLHF | aliases: Reinforcement Learning from Human Feedback\n"
            "- BERT\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = digest_paper.load_concept_index(f.name)
            os.unlink(f.name)

        lines = result.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("Transformer | aliases:", lines[0])
        self.assertIn("RLHF", lines[1])
        self.assertIn("BERT", lines[2])

    def test_returns_empty_for_missing_file(self):
        result = digest_paper.load_concept_index('/nonexistent/concept_index.md')
        self.assertEqual(result, "")

    def test_strips_frontmatter_and_headings(self):
        content = (
            "---\ntitle: Concept Index\n---\n\n"
            "# Concept Index\n\n"
            "> Some note\n\n"
            "- OnlyConcept\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = digest_paper.load_concept_index(f.name)
            os.unlink(f.name)

        self.assertEqual(result, "- OnlyConcept")
        self.assertNotIn("Concept Index", result)
        self.assertNotIn("---", result)


class TestLoadNameIndex(unittest.TestCase):
    """Tests for loading name_index.md."""

    def test_loads_name_lines(self):
        content = (
            "---\ntitle: Name Index\ntype: name-index\n"
            "date-updated: 2026-04-05\n---\n\n"
            "# Name Index\n\n"
            "> Auto-generated.\n\n"
            "- Geoffrey Hinton | aliases: Geoff Hinton\n"
            "- ImageNet\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = digest_paper.load_name_index(f.name)
            os.unlink(f.name)

        lines = result.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Geoffrey Hinton", lines[0])
        self.assertIn("ImageNet", lines[1])

    def test_returns_empty_for_missing_file(self):
        result = digest_paper.load_name_index('/nonexistent/name_index.md')
        self.assertEqual(result, "")


class TestKnownConceptsInPrompt(unittest.TestCase):
    """Test that known_concepts placeholder works in prompt."""

    def test_known_concepts_injected(self):
        template = "Concepts: {known_concepts}\nPaper: {paper_text}"
        result = digest_paper.build_prompt(template, {
            'paper_text': 'content',
            'known_concepts': '- Transformer\n- BERT',
        })
        self.assertIn("- Transformer", result)
        self.assertIn("- BERT", result)

    def test_known_concepts_absent_gracefully(self):
        template = "Concepts: {known_concepts}\nPaper: {paper_text}"
        result = digest_paper.build_prompt(template, {
            'paper_text': 'content',
        })
        self.assertIn("Concepts: ", result)
        self.assertIn("content", result)


class TestParseArgsConceptIndex(unittest.TestCase):
    """Test --concept_index argument."""

    def test_concept_index_arg(self):
        args = digest_paper.parse_args([
            'paper.pdf', '--concept_index', '/path/to/concept_index.md'
        ])
        self.assertEqual(args.concept_index, '/path/to/concept_index.md')

    def test_concept_index_default_none(self):
        args = digest_paper.parse_args(['paper.pdf'])
        self.assertIsNone(args.concept_index)

    def test_name_index_arg(self):
        args = digest_paper.parse_args([
            'paper.pdf', '--name_index', '/path/to/name_index.md'
        ])
        self.assertEqual(args.name_index, '/path/to/name_index.md')

    def test_name_index_default_none(self):
        args = digest_paper.parse_args(['paper.pdf'])
        self.assertIsNone(args.name_index)


class TestParseArgsForce(unittest.TestCase):
    """Test --force argument."""

    def test_force_flag(self):
        args = digest_paper.parse_args(['paper.pdf', '--force'])
        self.assertTrue(args.force)

    def test_force_default_false(self):
        args = digest_paper.parse_args(['paper.pdf'])
        self.assertFalse(args.force)


class TestForceRedigest(unittest.TestCase):
    """Test --force flag skips/re-digests existing digests."""

    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_skips_existing_digest(self, mock_extract, mock_gemini):
        """Without --force, existing digest should be skipped."""
        mock_extract.return_value = "Paper Title\nContent of the paper."
        mock_gemini.return_value = "## 1. Main Idea\nSummary"

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            with tempfile.TemporaryDirectory() as tmpdir:
                # First run creates the digest
                result = digest_paper.main([f.name, '--output_dir', tmpdir])
                self.assertEqual(result, 0)
                self.assertEqual(mock_gemini.call_count, 1)

                # Second run without --force should skip
                result = digest_paper.main([f.name, '--output_dir', tmpdir])
                self.assertEqual(result, 0)
                # Gemini should NOT have been called again
                self.assertEqual(mock_gemini.call_count, 1)
            os.unlink(f.name)

    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_force_redigests_existing(self, mock_extract, mock_gemini):
        """With --force, existing digest should be overwritten."""
        mock_extract.return_value = "Paper Title\nContent of the paper."
        mock_gemini.return_value = "## 1. Main Idea\nSummary"

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            with tempfile.TemporaryDirectory() as tmpdir:
                # First run creates the digest
                result = digest_paper.main([f.name, '--output_dir', tmpdir])
                self.assertEqual(result, 0)
                self.assertEqual(mock_gemini.call_count, 1)

                # Second run with --force should re-digest
                result = digest_paper.main([f.name, '--output_dir', tmpdir, '--force'])
                self.assertEqual(result, 0)
                # Gemini should have been called again
                self.assertEqual(mock_gemini.call_count, 2)
            os.unlink(f.name)


class TestSearchHnForPaper(unittest.TestCase):
    """Test Hacker News search for paper threads."""

    @patch('digest_paper._hn_get_json')
    def test_finds_matching_story(self, mock_get):
        mock_get.return_value = {
            "hits": [{
                "objectID": "12345",
                "title": "Attention Is All You Need",
            }]
        }
        logger = MagicMock()
        story_id = digest_paper.search_hn_for_paper("Attention Is All You Need", logger)
        self.assertEqual(story_id, 12345)

    @patch('digest_paper._hn_get_json')
    def test_returns_none_for_no_hits(self, mock_get):
        mock_get.return_value = {"hits": []}
        logger = MagicMock()
        story_id = digest_paper.search_hn_for_paper("Obscure Paper Title", logger)
        self.assertIsNone(story_id)

    @patch('digest_paper._hn_get_json')
    def test_returns_none_for_low_overlap(self, mock_get):
        mock_get.return_value = {
            "hits": [{
                "objectID": "99999",
                "title": "Completely Unrelated Discussion",
            }]
        }
        logger = MagicMock()
        story_id = digest_paper.search_hn_for_paper("Attention Is All You Need", logger)
        self.assertIsNone(story_id)

    @patch('digest_paper._hn_get_json')
    def test_returns_none_on_api_failure(self, mock_get):
        mock_get.return_value = None
        logger = MagicMock()
        story_id = digest_paper.search_hn_for_paper("Any Title", logger)
        self.assertIsNone(story_id)


class TestCollectComments(unittest.TestCase):
    """Test HN comment tree collection."""

    def test_collects_top_level_comments(self):
        item = {
            "children": [
                {"type": "comment", "text": "Great paper!", "author": "user1", "children": []},
                {"type": "comment", "text": "Interesting work", "author": "user2", "children": []},
            ]
        }
        comments = digest_paper._collect_comments(item)
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["author"], "user1")
        self.assertEqual(comments[1]["text"], "Interesting work")

    def test_collects_nested_comments(self):
        item = {
            "children": [
                {
                    "type": "comment", "text": "Top level", "author": "user1",
                    "children": [
                        {"type": "comment", "text": "Reply", "author": "user2", "children": []},
                    ]
                },
            ]
        }
        comments = digest_paper._collect_comments(item, max_depth=2)
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["depth"], 0)
        self.assertEqual(comments[1]["depth"], 1)

    def test_respects_max_depth(self):
        item = {
            "children": [
                {
                    "type": "comment", "text": "Level 0", "author": "a",
                    "children": [
                        {
                            "type": "comment", "text": "Level 1", "author": "b",
                            "children": [
                                {"type": "comment", "text": "Level 2", "author": "c", "children": []},
                            ]
                        },
                    ]
                },
            ]
        }
        comments = digest_paper._collect_comments(item, max_depth=0)
        self.assertEqual(len(comments), 1)

    def test_skips_empty_text(self):
        item = {
            "children": [
                {"type": "comment", "text": "", "author": "user1", "children": []},
                {"type": "comment", "text": "Real comment", "author": "user2", "children": []},
            ]
        }
        comments = digest_paper._collect_comments(item)
        self.assertEqual(len(comments), 1)


class TestFetchHnComments(unittest.TestCase):
    """Test fetching and formatting HN comments."""

    @patch('digest_paper._hn_get_json')
    def test_formats_comments(self, mock_get):
        mock_get.return_value = {
            "title": "Paper Discussion",
            "children": [
                {"type": "comment", "text": "Insightful comment", "author": "expert", "children": []},
            ]
        }
        logger = MagicMock()
        result = digest_paper.fetch_hn_comments(12345, logger)
        self.assertIn("Hacker News Discussion", result)
        self.assertIn("Paper Discussion", result)
        self.assertIn("[expert]: Insightful comment", result)
        self.assertIn("news.ycombinator.com/item?id=12345", result)

    @patch('digest_paper._hn_get_json')
    def test_returns_empty_on_failure(self, mock_get):
        mock_get.return_value = None
        logger = MagicMock()
        result = digest_paper.fetch_hn_comments(12345, logger)
        self.assertEqual(result, "")

    @patch('digest_paper._hn_get_json')
    def test_returns_empty_for_no_comments(self, mock_get):
        mock_get.return_value = {"title": "Story", "children": []}
        logger = MagicMock()
        result = digest_paper.fetch_hn_comments(12345, logger)
        self.assertEqual(result, "")

    @patch('digest_paper._hn_get_json')
    def test_strips_html_tags(self, mock_get):
        mock_get.return_value = {
            "title": "Story",
            "children": [
                {"type": "comment", "text": "<p>Hello <a href='x'>world</a></p>", "author": "u", "children": []},
            ]
        }
        logger = MagicMock()
        result = digest_paper.fetch_hn_comments(12345, logger)
        self.assertNotIn("<p>", result)
        self.assertNotIn("<a", result)
        self.assertIn("Hello", result)
        self.assertIn("world", result)


class TestHnIntegrationInMain(unittest.TestCase):
    """Test that HN search is called during main flow."""

    @patch('digest_paper.search_hn_for_paper')
    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_main_searches_hn(self, mock_extract, mock_gemini, mock_hn_search):
        mock_extract.return_value = "Paper Title\nContent of the paper."
        mock_gemini.return_value = "## 1. Main Idea\nSummary"
        mock_hn_search.return_value = None

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            with tempfile.TemporaryDirectory() as tmpdir:
                digest_paper.main([f.name, '--output_dir', tmpdir])
            os.unlink(f.name)

        mock_hn_search.assert_called_once()

    @patch('digest_paper.fetch_hn_comments')
    @patch('digest_paper.search_hn_for_paper')
    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_main_includes_hn_comments_in_prompt(self, mock_extract, mock_gemini, mock_hn_search, mock_hn_comments):
        mock_extract.return_value = "Paper Title\nContent of the paper."
        mock_gemini.return_value = "## 1. Main Idea\nSummary"
        mock_hn_search.return_value = 12345
        mock_hn_comments.return_value = "### Hacker News Discussion\n[user]: Great paper!"

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            with tempfile.TemporaryDirectory() as tmpdir:
                digest_paper.main([f.name, '--output_dir', tmpdir])
            os.unlink(f.name)

        # Check that HN comments were passed to Gemini
        prompt_sent = mock_gemini.call_args[0][0]
        self.assertIn("Hacker News Discussion", prompt_sent)
        self.assertIn("Great paper!", prompt_sent)

    @patch('digest_paper.search_hn_for_paper')
    @patch('digest_paper.run_gemini')
    @patch('digest_paper.extract_text_from_pdf')
    def test_main_handles_hn_failure_gracefully(self, mock_extract, mock_gemini, mock_hn_search):
        mock_extract.return_value = "Paper Title\nContent of the paper."
        mock_gemini.return_value = "## 1. Main Idea\nSummary"
        mock_hn_search.side_effect = Exception("Network error")

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf')
            f.flush()
            with tempfile.TemporaryDirectory() as tmpdir:
                result = digest_paper.main([f.name, '--output_dir', tmpdir])
            os.unlink(f.name)

        # Should still succeed — HN is non-fatal
        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
