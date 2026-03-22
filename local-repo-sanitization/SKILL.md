---
name: local-repo-sanitization
description: "Sanitize local GitHub repos: deep-analyze and update READMEs, ensure all tests are in CI, fix broken GitHub Actions. Use when: asked to sanitize repos, check repo health, or run repo maintenance. Also runs as a daily cron job."
---

# Local Repo Sanitization

Automated maintenance for all configured GitHub repositories. For each repo: verify working directory is clean, deep-analyze and update README, ensure test CI coverage, and fix broken GitHub Actions.

## Config

Read the repo list from `config.json` in the same directory as this file (`~/.openclaw/skills/custom/local-repo-sanitization/config.json`).

Each entry has: `name`, `path` (supports `~`), `remote` (owner/repo), `branch`.

## Workflow

Process each repo in `config.json`. If a repo path doesn't exist, report it and move to the next one.

### Step 1: Safety check

```bash
cd <repo_path>
git status --porcelain
```

- Filter out `??` lines (untracked files are OK).
- If any tracked changes remain (modified, staged, deleted): **SKIP this repo entirely**. Report it as dirty in the summary. Do not modify anything.
- If clean, pull latest: `git pull`

### Step 2: Deep README analysis and update

Read the README file and explore the actual codebase — directory structure, main modules, scripts, configs, entry points.

Compare the README against reality:
- Are there sections describing features that no longer exist?
- Are there modules or scripts not mentioned in the README?
- Are installation/setup instructions still accurate?
- Does the project structure section match the actual file tree?

If discrepancies are found:
1. Update the README — preserve existing style, only change what's necessary
2. Stage only the README: `git add README.md`
3. Commit: `git commit -m "docs: update README to reflect current codebase"`
4. Push: `git push origin <branch>`

If the README is accurate, move on.

### Step 3: Test CI coverage

Find all `test_*.py` files in the repo (excluding `.git/`).

Find the test workflow — check for `.github/workflows/tests.yml` or `.github/workflows/test.yml`.

If no test workflow exists or no test files exist, skip this step.

For each test file, check if its module name (e.g., `test_foo` from `test_foo.py`) appears in the workflow YAML.

**Exclusions:** If a `.ci-skip-tests` file exists at the repo root, each line is a module name to exclude from this check (e.g., `test_foo`).

If any test files are missing from the workflow:
1. Add the appropriate step(s) to the workflow YAML, following the existing step pattern (name, `python -m unittest <module> -v`, `working-directory`)
2. Stage: `git add .github/workflows/`
3. Commit: `git commit -m "ci: add missing test modules to workflow"`
4. Push: `git push origin <branch>`

### Step 4: Fix broken GitHub Actions

Get the latest run of each workflow:

```bash
gh run list --repo <remote> --branch <branch> --limit 20 --json status,conclusion,name,databaseId,workflowName
```

Group by `workflowName` and take only the most recent run of each. Check whether that latest run has `conclusion: "failure"`.

For each workflow whose latest run is failing:
1. Fetch the failure logs: `gh run view <databaseId> --repo <remote> --log-failed | tail -100`
2. Read the relevant workflow file and any code it references
3. Analyze the root cause from the logs
4. Fix the issue — it may be in the workflow YAML, the code, or dependencies
5. Stage the changed files specifically (not `git add -A`)
6. Commit: `git commit -m "fix: resolve <workflow_name> failure"`
7. Push: `git push origin <branch>`

If the latest run of every workflow is passing, move on.

### Step 5: Summary report

After processing all repos, output a summary table:

```
Repo Sanitization Summary
─────────────────────────
skills:                 clean | README: ok        | Tests: ok    | CI: passing
agentic-coding-skills:  clean | README: updated   | Tests: ok    | CI: passing
md-serve:               DIRTY | (skipped)
code-complexity-measure: clean | README: ok       | Tests: 1 added | CI: fixed
```

## Important rules

- **Never modify a dirty repo.** If there are uncommitted tracked changes, skip it entirely.
- **Stage specific files**, not `git add -A`. Only stage what you changed.
- **One commit per concern.** README changes, CI changes, and workflow fixes get separate commits.
- **Preserve style.** When editing READMEs or workflow files, match the existing formatting.
- **Don't over-edit.** Only change what's actually wrong. If the README is fine, don't touch it.
