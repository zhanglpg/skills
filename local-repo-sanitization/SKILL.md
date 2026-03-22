# local-repo-sanitization Skill

## Purpose

This skill sanitizes local GitHub repositories by ensuring README files accurately reflect the actual codebase, checking GitHub Actions workflow health, and maintaining repository hygiene.

## Description

The `local-repo-sanitization` skill provides automated repository maintenance by:

1. **Detecting uncommitted changes** - Prevents modifications when local work is in progress
2. **Analyzing README accuracy** - Uses Claude Code to compare README documentation with actual code
3. **Updating documentation** - Automatically fixes discrepancies between README and codebase
4. **Checking CI/CD health** - Monitors GitHub Actions workflow status
5. **Fixing broken workflows** - Attempts to repair failing GitHub Actions configurations

## Usage

### Sanitize a Single Repository

```bash
~/.openclaw/skills/custom/local-repo-sanitization/scripts/sanitize-repo.sh <repo-path>
```

Example:
```bash
~/.openclaw/skills/custom/local-repo-sanitization/scripts/sanitize-repo.sh ~/.openclaw/workspace-coding/agentic-coding-skills
```

### Check Repository Health (Read-Only)

```bash
~/.openclaw/skills/custom/local-repo-sanitization/scripts/check-health.sh <repo-path>
```

Example:
```bash
~/.openclaw/skills/custom/local-repo-sanitization/scripts/check-health.sh ~/.openclaw/workspace-coding/agentic-coding-skills
```

### Sanitize All Configured Repositories

```bash
cd ~/.openclaw/skills/custom/local-repo-sanitization
./scripts/sanitize-repo.sh --all
```

## Configuration

Edit `config.json` to customize repositories and settings:

```json
{
  "repos": [
    {
      "name": "repo-name",
      "path": "~/path/to/repo",
      "remote": "username/repo-name",
      "branch": "main"
    }
  ]
}
```

### Configuration Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Friendly name for the repository |
| `path` | string | Yes | Local path (supports `~` expansion) |
| `remote` | string | Yes | GitHub remote in `owner/repo` format |
| `branch` | string | Yes | Default branch name |

## Safety Checks

### Uncommitted Changes Detection

**CRITICAL:** The skill will **STOP immediately** if uncommitted changes are detected:

- Modified tracked files
- Staged changes
- Untracked files (optional, configurable)

When uncommitted changes are found:
1. Script exits with error code `1`
2. Clear error message is displayed
3. **No modifications are made** to the repository
4. User must commit or stash changes before running sanitization

This prevents:
- Loss of work-in-progress
- Accidental commits of incomplete changes
- Conflicts with local development

## Task Workflow

### sanitize-repo.sh Workflow

1. **Validate Input**
   - Check if repo path exists
   - Verify it's a git repository
   - Load configuration

2. **Safety Check**
   - Detect uncommitted changes (`git status --porcelain`)
   - Exit with error if changes found

3. **Deep README Analysis**
   - Spawn Claude Code subagent
   - Analyze actual code structure
   - Compare with README content
   - Identify discrepancies

4. **Update README**
   - Apply necessary documentation updates
   - Ensure accuracy with codebase

5. **Commit and Push**
   - Stage README changes
   - Create descriptive commit message
   - Push to remote repository

6. **Validate Test CI Coverage**
   - Find all `test_*.py` files in the repo
   - Check each is referenced in the test workflow (`.github/workflows/tests.yml` or `test.yml`)
   - Respect `.ci-skip-tests` exclusion file (one module name per line, e.g. `test_foo`)
   - If missing tests found, spawn Claude Code to add them to the workflow
   - Commit and push

7. **Check GitHub Actions**
   - Query recent workflow runs
   - Identify failed runs

8. **Fix Broken Workflows** (if any)
   - Analyze failure reasons
   - Attempt automated fixes
   - Commit and push fixes

9. **Report Results**
   - Repository status (OK/ERROR/UNCOMMITTED)
   - README changes made
   - Workflow status
   - Fixes applied

### check-health.sh Workflow

1. **Validate Input**
   - Check if repo path exists
   - Verify it's a git repository

2. **Check Uncommitted Changes**
   - Report any pending changes
   - Does NOT exit or modify

3. **Check GitHub Actions Status**
   - Query recent workflow runs
   - Report pass/fail status

4. **Report Health Summary**
   - Clean/dirty status
   - CI/CD health
   - Recommendations

## Output Format

### Success Output

```
[OK] Repository: agentic-coding-skills
├─ README: Updated (3 sections added, 2 sections modified)
├─ Commit: "docs: update README to reflect current codebase"
├─ Push: Success (origin/main)
├─ Workflows: All passing (3/3)
└─ Status: SANITIZED
```

### Error Output (Uncommitted Changes)

```
[ERROR] Repository: agentic-coding-skills
├─ Status: UNCOMMITTED CHANGES DETECTED
├─ Modified files:
│  ├─ M src/index.ts
│  └─ M package.json
├─ Action: Commit or stash changes before sanitization
└─ Exit Code: 1
```

### Health Check Output

```
[HEALTH] Repository: agentic-coding-skills
├─ Working Directory: Clean
├─ Uncommitted Changes: None
├─ GitHub Actions:
│  ├─ CI: ✅ Passing (2h ago)
│  ├─ Deploy: ✅ Passing (1d ago)
│  └─ Lint: ⚠️ Failed (3h ago)
└─ Recommendations: Check lint workflow
```

## Prerequisites

- Git installed and configured
- GitHub CLI (`gh`) authenticated
- Claude Code CLI (`claude`) available
- Node.js (for script execution)

## Files

```
local-repo-sanitization/
├── SKILL.md              # This documentation
├── config.json           # Repository configuration
└── scripts/
    ├── sanitize-repo.sh  # Main sanitization script
    └── check-health.sh   # Health check script
```

## Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Uncommitted changes detected |
| 2 | Repository path not found |
| 3 | Not a git repository |
| 4 | GitHub CLI error |
| 5 | Claude Code analysis failed |

## Security Considerations

- Scripts only operate on configured repositories
- No external data exfiltration
- All changes are committed with descriptive messages
- Push requires proper GitHub authentication
- Read-only health checks available for auditing

## Troubleshooting

### "Uncommitted changes detected"
Commit or stash your local changes before running sanitization:
```bash
git add . && git commit -m "WIP"
# or
git stash
```

### "Repository not found"
Verify the path in `config.json` exists and is accessible.

### "GitHub CLI not authenticated"
Run `gh auth login` to authenticate with GitHub.

### "Claude Code analysis failed"
Ensure Claude Code CLI is installed and accessible at `/Users/lipingzhang/.local/bin/claude`.
