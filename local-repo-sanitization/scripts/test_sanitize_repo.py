#!/usr/bin/env python3
"""Tests for sanitize-repo.sh and check-health.sh bash scripts.

Creates temporary git repos and exercises shell functions via subprocess.
External tools (claude, gh) are stubbed out with fake scripts.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import textwrap
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SANITIZE_SCRIPT = os.path.join(SCRIPT_DIR, "sanitize-repo.sh")
HEALTH_SCRIPT = os.path.join(SCRIPT_DIR, "check-health.sh")


def run_bash(code, env=None, cwd=None):
    """Run a bash snippet and return (returncode, stdout, stderr)."""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(
        ["bash", "-c", code],
        capture_output=True, text=True, env=merged, cwd=cwd,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def source_and_call(function_call, env=None, cwd=None, script=None):
    """Source a script (skipping its main call) and call a function."""
    script = script or SANITIZE_SCRIPT
    # eval the script minus 'main "$@"' and 'set -e' so we can test individual functions
    code = (
        f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{script}")"; '
        f'{function_call}'
    )
    return run_bash(code, env=env, cwd=cwd)


class TempGitRepo:
    """Context manager that creates a temporary git repo."""

    def __init__(self, files=None, commit=True):
        self.files = files or {"README.md": "# Test\n"}
        self.commit = commit

    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = self.tmpdir
        subprocess.run(
            ["git", "init", self.path],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", self.path, "config", "user.email", "test@test.com"],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", self.path, "config", "user.name", "Test"],
            capture_output=True, check=True,
        )
        for name, content in self.files.items():
            fpath = os.path.join(self.path, name)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w") as f:
                f.write(content)
        if self.commit:
            subprocess.run(
                ["git", "-C", self.path, "add", "-A"],
                capture_output=True, check=True,
            )
            subprocess.run(
                ["git", "-C", self.path, "commit", "-m", "Initial commit"],
                capture_output=True, check=True,
            )
        return self

    def __exit__(self, *args):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TempConfig:
    """Context manager that creates a temporary config.json."""

    def __init__(self, repos, settings=None):
        self.repos = repos
        self.settings = settings or {
            "claudePath": "/usr/bin/true",
            "checkUntrackedFiles": False,
            "autoFixWorkflows": True,
            "commitPrefix": "docs:",
            "dryRun": False,
        }

    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "config.json")
        data = {"repos": self.repos, "settings": self.settings}
        with open(self.path, "w") as f:
            json.dump(data, f)
        return self

    def __exit__(self, *args):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests for expand_path
# ---------------------------------------------------------------------------
class TestExpandPath(unittest.TestCase):
    def test_expands_tilde(self):
        rc, out, _ = source_and_call('expand_path "~/foo"')
        self.assertEqual(rc, 0)
        expected = os.path.expanduser("~/foo")
        self.assertEqual(out.strip(), expected)

    def test_absolute_path_unchanged(self):
        rc, out, _ = source_and_call('expand_path "/tmp/bar"')
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "/tmp/bar")

    def test_relative_path_unchanged(self):
        rc, out, _ = source_and_call('expand_path "relative/path"')
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "relative/path")


# ---------------------------------------------------------------------------
# Tests for is_git_repo
# ---------------------------------------------------------------------------
class TestIsGitRepo(unittest.TestCase):
    def test_git_repo_returns_zero(self):
        with TempGitRepo() as repo:
            rc, _, _ = source_and_call(f'is_git_repo "{repo.path}"')
            self.assertEqual(rc, 0)

    def test_non_git_dir_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, _, _ = source_and_call(f'is_git_repo "{tmp}"')
            self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Tests for check_uncommitted_changes
# ---------------------------------------------------------------------------
class TestCheckUncommittedChanges(unittest.TestCase):
    def test_clean_repo_returns_zero(self):
        with TempGitRepo() as repo:
            rc, out, _ = source_and_call(
                f'check_uncommitted_changes "{repo.path}" "false"'
            )
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")

    def test_modified_tracked_file_returns_nonzero(self):
        with TempGitRepo() as repo:
            with open(os.path.join(repo.path, "README.md"), "w") as f:
                f.write("changed\n")
            rc, out, _ = source_and_call(
                f'check_uncommitted_changes "{repo.path}" "false"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("README.md", out)

    def test_staged_changes_returns_nonzero(self):
        with TempGitRepo() as repo:
            new_file = os.path.join(repo.path, "new.txt")
            with open(new_file, "w") as f:
                f.write("staged\n")
            subprocess.run(
                ["git", "-C", repo.path, "add", "new.txt"],
                capture_output=True, check=True,
            )
            rc, out, _ = source_and_call(
                f'check_uncommitted_changes "{repo.path}" "false"'
            )
            self.assertNotEqual(rc, 0)

    def test_untracked_ignored_when_false(self):
        with TempGitRepo() as repo:
            with open(os.path.join(repo.path, "untracked.txt"), "w") as f:
                f.write("new\n")
            rc, out, _ = source_and_call(
                f'check_uncommitted_changes "{repo.path}" "false"'
            )
            self.assertEqual(rc, 0)

    def test_untracked_detected_when_true(self):
        with TempGitRepo() as repo:
            with open(os.path.join(repo.path, "untracked.txt"), "w") as f:
                f.write("new\n")
            rc, out, _ = source_and_call(
                f'check_uncommitted_changes "{repo.path}" "true"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("untracked.txt", out)


# ---------------------------------------------------------------------------
# Tests for get_repo_config / get_all_repo_names / get_setting
# ---------------------------------------------------------------------------
class TestConfigParsing(unittest.TestCase):
    def test_get_repo_config(self):
        with TempConfig([{
            "name": "test-repo",
            "path": "/tmp/test",
            "remote": "user/repo",
            "branch": "main",
        }]) as cfg:
            code = (
                f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                f'CONFIG_FILE="{cfg.path}"; '
                'get_repo_config "test-repo" "remote"'
            )
            rc, out, _ = run_bash(code)
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "user/repo")

    def test_get_all_repo_names(self):
        with TempConfig([
            {"name": "a", "path": "/a", "remote": "u/a", "branch": "main"},
            {"name": "b", "path": "/b", "remote": "u/b", "branch": "main"},
        ]) as cfg:
            code = (
                f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                f'CONFIG_FILE="{cfg.path}"; '
                'get_all_repo_names'
            )
            rc, out, _ = run_bash(code)
            self.assertEqual(rc, 0)
            names = out.strip().split("\n")
            self.assertEqual(names, ["a", "b"])

    def test_get_setting_with_default(self):
        with TempConfig([], settings={"claudePath": "/bin/claude"}) as cfg:
            code = (
                f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                f'CONFIG_FILE="{cfg.path}"; '
                'get_setting "nonExistent" "fallback"'
            )
            rc, out, _ = run_bash(code)
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "fallback")

    def test_get_setting_reads_value(self):
        with TempConfig([], settings={
            "commitPrefix": "chore:",
        }) as cfg:
            code = (
                f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                f'CONFIG_FILE="{cfg.path}"; '
                'get_setting "commitPrefix" "docs:"'
            )
            rc, out, _ = run_bash(code)
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "chore:")


# ---------------------------------------------------------------------------
# Tests for sanitize_repo (integration)
# ---------------------------------------------------------------------------
class TestSanitizeRepoIntegration(unittest.TestCase):
    def _make_stub_bin(self, tmpdir, name, script="exit 0"):
        """Create a stub executable in tmpdir."""
        stub = os.path.join(tmpdir, name)
        with open(stub, "w") as f:
            f.write(f"#!/bin/bash\n{script}\n")
        os.chmod(stub, 0o755)
        return stub

    def test_aborts_on_uncommitted_changes(self):
        with TempGitRepo() as repo:
            # Modify a tracked file
            with open(os.path.join(repo.path, "README.md"), "w") as f:
                f.write("modified\n")
            with TempConfig([{
                "name": "test",
                "path": repo.path,
                "remote": "user/repo",
                "branch": "main",
            }]) as cfg:
                code = (
                    f'CONFIG_FILE="{cfg.path}"; '
                    f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                    f'sanitize_repo "{repo.path}" "test" "user/repo" "main" "false"'
                )
                rc, out, _ = run_bash(code)
                self.assertEqual(rc, 1)
                self.assertIn("UNCOMMITTED", out)

    def test_aborts_on_missing_path(self):
        with TempConfig([]) as cfg:
            code = (
                f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                f'CONFIG_FILE="{cfg.path}"; '
                'sanitize_repo "/nonexistent/path" "test" "user/repo" "main" "false"'
            )
            rc, out, _ = run_bash(code)
            self.assertEqual(rc, 2)
            self.assertIn("not found", out)

    def test_aborts_on_non_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TempConfig([]) as cfg:
                code = (
                    f'CONFIG_FILE="{cfg.path}"; '
                    f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                    f'sanitize_repo "{tmp}" "test" "user/repo" "main" "false"'
                )
                rc, out, _ = run_bash(code)
                self.assertEqual(rc, 3)
                self.assertIn("Not a git repo", out)

    def test_clean_repo_with_stubbed_tools(self):
        """Clean repo with stubbed claude and gh runs through successfully."""
        with TempGitRepo() as repo:
            stub_dir = tempfile.mkdtemp()
            try:
                # Stub claude to output "ACCURATE: everything"
                self._make_stub_bin(
                    stub_dir, "claude",
                    'echo "ACCURATE: All sections are up to date"'
                )
                # Stub gh to return empty runs
                self._make_stub_bin(
                    stub_dir, "gh",
                    'echo "[]"'
                )
                with TempConfig([], settings={
                    "claudePath": os.path.join(stub_dir, "claude"),
                    "checkUntrackedFiles": False,
                    "autoFixWorkflows": True,
                    "commitPrefix": "docs:",
                    "dryRun": False,
                }) as cfg:
                    env = {"PATH": f"{stub_dir}:{os.environ['PATH']}"}
                    code = (
                        f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                        f'CONFIG_FILE="{cfg.path}"; '
                        f'CLAUDE_PATH="{os.path.join(stub_dir, "claude")}"; '
                        f'sanitize_repo "{repo.path}" "test" "user/repo" "main" "false"'
                    )
                    rc, out, _ = run_bash(code, env=env)
                    self.assertEqual(rc, 0)
                    self.assertIn("[OK]", out)
            finally:
                shutil.rmtree(stub_dir, ignore_errors=True)

    def test_untracked_files_ignored_by_default(self):
        """Untracked files should not block sanitization when checkUntrackedFiles=false."""
        with TempGitRepo() as repo:
            # Add untracked file
            with open(os.path.join(repo.path, "notes.txt"), "w") as f:
                f.write("personal notes\n")
            stub_dir = tempfile.mkdtemp()
            try:
                self._make_stub_bin(
                    stub_dir, "claude",
                    'echo "ACCURATE: everything looks good"'
                )
                self._make_stub_bin(stub_dir, "gh", 'echo "[]"')
                with TempConfig([], settings={
                    "claudePath": os.path.join(stub_dir, "claude"),
                    "checkUntrackedFiles": False,
                    "autoFixWorkflows": True,
                    "commitPrefix": "docs:",
                    "dryRun": False,
                }) as cfg:
                    env = {"PATH": f"{stub_dir}:{os.environ['PATH']}"}
                    code = (
                        f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                        f'CONFIG_FILE="{cfg.path}"; '
                        f'CLAUDE_PATH="{os.path.join(stub_dir, "claude")}"; '
                        f'sanitize_repo "{repo.path}" "test" "user/repo" "main" "false"'
                    )
                    rc, out, _ = run_bash(code, env=env)
                    self.assertEqual(rc, 0)
                    self.assertNotIn("UNCOMMITTED", out)
            finally:
                shutil.rmtree(stub_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests for the main CLI entry point
# ---------------------------------------------------------------------------
class TestMainCLI(unittest.TestCase):
    def test_no_args_shows_usage(self):
        rc, out, _ = run_bash(f'bash "{SANITIZE_SCRIPT}"')
        self.assertEqual(rc, 0)
        self.assertIn("Usage:", out)

    def test_help_flag(self):
        rc, out, _ = run_bash(f'bash "{SANITIZE_SCRIPT}" --help')
        self.assertEqual(rc, 0)
        self.assertIn("Usage:", out)
        self.assertIn("--all", out)

    def test_nonexistent_repo_path(self):
        rc, out, _ = run_bash(f'bash "{SANITIZE_SCRIPT}" /nonexistent/repo')
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Tests for check-health.sh
# ---------------------------------------------------------------------------
class TestCheckHealthExpandPath(unittest.TestCase):
    def test_expands_tilde(self):
        code = f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{HEALTH_SCRIPT}")";expand_path "~/foo"'
        rc, out, _ = run_bash(code)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), os.path.expanduser("~/foo"))


class TestCheckHealthCLI(unittest.TestCase):
    def test_no_args_shows_usage(self):
        rc, out, _ = run_bash(f'bash "{HEALTH_SCRIPT}"')
        self.assertEqual(rc, 0)
        self.assertIn("Usage:", out)

    def test_help_flag(self):
        rc, out, _ = run_bash(f'bash "{HEALTH_SCRIPT}" --help')
        self.assertEqual(rc, 0)
        self.assertIn("--all", out)


class TestCheckHealthRepo(unittest.TestCase):
    def test_nonexistent_path(self):
        rc, out, _ = run_bash(f'bash "{HEALTH_SCRIPT}" /nonexistent/path')
        self.assertIn("not found", out)

    def test_non_git_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, _ = run_bash(f'bash "{HEALTH_SCRIPT}" "{tmp}"')
            self.assertIn("Not a git repo", out)

    def test_clean_repo_reports_clean(self):
        """Health check on a clean repo with no gh should still report."""
        with TempGitRepo() as repo:
            # Remove gh from PATH to avoid external calls
            env = {"PATH": "/usr/bin:/bin"}
            rc, out, _ = run_bash(
                f'bash "{HEALTH_SCRIPT}" "{repo.path}"',
                env=env,
            )
            self.assertIn("HEALTH REPORT", out)

    def test_dirty_repo_reports_uncommitted(self):
        with TempGitRepo() as repo:
            with open(os.path.join(repo.path, "README.md"), "w") as f:
                f.write("changed\n")
            env = {"PATH": "/usr/bin:/bin"}
            rc, out, _ = run_bash(
                f'bash "{HEALTH_SCRIPT}" "{repo.path}"',
                env=env,
            )
            self.assertIn("HEALTH REPORT", out)
            self.assertIn("Uncommitted changes", out.replace("\n", " "))


# ---------------------------------------------------------------------------
# Tests for commit_and_push
# ---------------------------------------------------------------------------
class TestCommitAndPush(unittest.TestCase):
    def test_no_changes_does_not_commit(self):
        with TempGitRepo() as repo:
            code = (
                f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                f'commit_and_push "{repo.path}" "test commit" "main"'
            )
            rc, out, _ = run_bash(code)
            self.assertEqual(rc, 0)
            self.assertIn("No changes to commit", out)

    def test_stages_and_commits(self):
        with TempGitRepo() as repo:
            # Create a change
            with open(os.path.join(repo.path, "new.txt"), "w") as f:
                f.write("new file\n")
            # commit_and_push does git add -A, so it should pick up new.txt
            # but push will fail (no remote) — that's expected
            code = (
                f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
                f'commit_and_push "{repo.path}" "add new file" "main"'
            )
            rc, out, _ = run_bash(code)
            # Push will fail since there's no remote, but commit should succeed
            # Verify the commit was created
            log_rc, log_out, _ = run_bash(
                f'git -C "{repo.path}" log --oneline -1'
            )
            self.assertIn("add new file", log_out)


# ---------------------------------------------------------------------------
# Tests for print_status_report
# ---------------------------------------------------------------------------
class TestPrintStatusReport(unittest.TestCase):
    def test_ok_status(self):
        code = (
            f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
            'print_status_report "my-repo" "OK" "Updated" "All passing" "None"'
        )
        rc, out, _ = run_bash(code)
        self.assertEqual(rc, 0)
        self.assertIn("my-repo", out)
        self.assertIn("OK", out)
        self.assertIn("Updated", out)

    def test_uncommitted_status(self):
        code = (
            f'eval "$(grep -v -e \'^main "\\$@"$\' -e \'^set -e$\' "{SANITIZE_SCRIPT}")"; '
            'print_status_report "my-repo" "UNCOMMITTED" "" "" "Uncommitted changes"'
        )
        rc, out, _ = run_bash(code)
        self.assertEqual(rc, 0)
        self.assertIn("ERROR", out)
        self.assertIn("UNCOMMITTED", out)


# ---------------------------------------------------------------------------
# Tests for check_test_coverage_in_ci
# ---------------------------------------------------------------------------
class TestCheckTestCoverageInCI(unittest.TestCase):
    def test_no_test_workflow_returns_zero(self):
        """Repos without a test workflow should pass."""
        with TempGitRepo({"README.md": "# Test\n", "test_foo.py": "pass\n"}) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertEqual(rc, 0)
            self.assertIn("No test workflow", out)

    def test_all_tests_covered(self):
        """When all test files are in the workflow, should pass."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: python -m unittest test_foo -v
                    working-directory: scripts
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "scripts/test_foo.py": "import unittest\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertEqual(rc, 0)
            self.assertIn("All test files are included", out)

    def test_missing_test_detected(self):
        """Test files not in the workflow should be reported."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: python -m unittest test_foo -v
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "scripts/test_foo.py": "import unittest\n",
            "scripts/test_bar.py": "import unittest\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("test_bar.py", out)
            self.assertNotIn("test_foo.py", out)

    def test_excluded_test_not_reported(self):
        """Tests listed in .ci-skip-tests should be skipped."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: python -m unittest test_foo -v
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "scripts/test_foo.py": "import unittest\n",
            "scripts/test_bar.py": "import unittest\n",
            ".ci-skip-tests": "test_bar\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertEqual(rc, 0)
            self.assertNotIn("test_bar.py", out)

    def test_no_test_files_returns_zero(self):
        """Repos with no test files should pass."""
        workflow = "name: Tests\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        files = {
            ".github/workflows/tests.yml": workflow,
            "src/main.py": "print('hello')\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertEqual(rc, 0)

    def test_multiple_missing_tests(self):
        """All missing tests should be reported, not just the first."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: python -m unittest test_existing -v
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "a/test_existing.py": "import unittest\n",
            "b/test_alpha.py": "import unittest\n",
            "c/test_beta.py": "import unittest\n",
            "d/test_gamma.py": "import unittest\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("test_alpha.py", out)
            self.assertIn("test_beta.py", out)
            self.assertIn("test_gamma.py", out)
            self.assertNotIn("test_existing", out.split("missing")[0]
                             if "missing" in out else out)

    def test_test_yml_fallback(self):
        """Should detect test.yml as alternative workflow name."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: python -m unittest test_foo -v
        """)
        files = {
            ".github/workflows/test.yml": workflow,
            "test_foo.py": "import unittest\n",
            "test_missing.py": "import unittest\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("test_missing.py", out)

    def test_tests_yml_takes_priority_over_test_yml(self):
        """tests.yml should be preferred when both exist."""
        workflow_tests = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: python -m unittest test_foo -v
                  - run: python -m unittest test_bar -v
        """)
        workflow_test = textwrap.dedent("""\
            name: Test
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: python -m unittest test_foo -v
        """)
        files = {
            ".github/workflows/tests.yml": workflow_tests,
            ".github/workflows/test.yml": workflow_test,
            "test_foo.py": "import unittest\n",
            "test_bar.py": "import unittest\n",
        }
        with TempGitRepo(files) as repo:
            # tests.yml has both, so all covered
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertEqual(rc, 0)

    def test_multiple_exclusions(self):
        """Multiple entries in .ci-skip-tests should all be excluded."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: echo "placeholder"
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "test_a.py": "import unittest\n",
            "test_b.py": "import unittest\n",
            "test_c.py": "import unittest\n",
            ".ci-skip-tests": "test_a\ntest_b\ntest_c\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertEqual(rc, 0)

    def test_partial_exclusion(self):
        """Only excluded tests should be skipped, others still reported."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: echo "placeholder"
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "test_included.py": "import unittest\n",
            "test_excluded.py": "import unittest\n",
            ".ci-skip-tests": "test_excluded\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("test_included.py", out)
            self.assertNotIn("test_excluded.py", out)

    def test_deeply_nested_test_files(self):
        """Test files in deeply nested directories should be found."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: echo "placeholder"
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "a/b/c/test_deep.py": "import unittest\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("test_deep.py", out)

    def test_empty_ci_skip_tests_file(self):
        """An empty .ci-skip-tests file should not exclude anything."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: echo "placeholder"
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "test_foo.py": "import unittest\n",
            ".ci-skip-tests": "",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("test_foo.py", out)

    def test_exclusion_only_matches_exact_module_name(self):
        """Exclusion should match exact module name, not partial."""
        workflow = textwrap.dedent("""\
            name: Tests
            on: push
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - run: echo "placeholder"
        """)
        files = {
            ".github/workflows/tests.yml": workflow,
            "test_foo.py": "import unittest\n",
            "test_foobar.py": "import unittest\n",
            ".ci-skip-tests": "test_foo\n",
        }
        with TempGitRepo(files) as repo:
            rc, out, _ = source_and_call(
                f'check_test_coverage_in_ci "{repo.path}"'
            )
            # test_foo excluded, but test_foobar should still be missing
            self.assertNotEqual(rc, 0)
            self.assertIn("test_foobar.py", out)


if __name__ == "__main__":
    unittest.main()
