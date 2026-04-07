---
name: syncing-openbb
description: "Syncs the OpenBB repo from GitHub, reruns the data pipeline on changes, and restarts and verifies the dashboard. Silent by default -- reporting is the caller's responsibility. Use when the dashboard needs a data refresh or repo synchronization."
---

# OpenBB Sync Skill

Pull the OpenBB repo, rerun the data pipeline when changes are detected, and restart the dashboard. **Silent by default** — no Discord messages sent by this skill.

## Quick Start

```bash
# Run manually
bash ~/.openclaw/skills/custom/openbb-sync/sync.sh

# Check exit code
echo $?  # 0=success, 1=pipeline failed, 2=dashboard failed

# View logs
tail -f ~/.openclaw/logs/skills/openbb-sync/sync.log
```

## How It Works

1. **Safety Check:** Skips if uncommitted changes are detected (detects active development)
2. **Sync:** Pulls latest from GitHub
3. **Pipeline:** Runs full data refresh if repo changed
4. **Restart:** Restarts dashboard via launchctl
5. **Verify:** Confirms HTTP 200

**Note:** This skill does NOT send Discord messages. Reporting is the caller's responsibility.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or skipped due to no changes/uncommitted work) |
| `1` | Pipeline execution failed |
| `2` | Dashboard verification failed |

## Safety Features

| Check | Action |
|-------|--------|
| Uncommitted git changes | Skip silently (active development detected) |
| No remote changes | Skip silently (nothing new) |
| Pipeline fails | Exit with code 1 |
| Dashboard fails health check | Exit with code 2 |

## Configuration

Variables at the top of `sync.sh`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENBB_DIR` | `$HOME/.openbb_platform` | OpenBB platform directory |
| `LOG_FILE` | `~/.openclaw/logs/skills/openbb-sync/sync.log` | Log file location |
| `DASHBOARD_URL` | `http://localhost:8501` | Dashboard health check URL |

## Dependencies

| Tool | Purpose | Notes |
|------|---------|-------|
| bash | Script runtime | |
| git | Repo sync | |
| python 3 | Pipeline execution | Via venv at `$OPENBB_DIR/.venv` |
| curl | Health check | |
| launchctl | Dashboard restart | macOS-specific; adjust for systemd on Linux |

## Files

| File | Purpose |
|------|---------|
| `sync.sh` | Main sync script |
| `SKILL.md` | This documentation |
| `~/.openclaw/logs/skills/openbb-sync/sync.log` | Sync logs (created on first run) |

## Logs

**Location:** `~/.openclaw/logs/skills/openbb-sync/sync.log`

**Sample output:**
```
[2026-03-20 15:28:11] === Starting Sync ===
[2026-03-20 15:28:11] Checking for uncommitted changes...
[2026-03-20 15:28:11] ✅ No uncommitted changes. Proceeding with sync.
[2026-03-20 15:28:11] Syncing OpenBB repo...
[2026-03-20 15:28:12] Changes detected! Before: 35af049 → After: c114bd0
[2026-03-20 15:28:12] Running data pipeline...
[2026-03-20 15:31:03] Pipeline completed successfully
[2026-03-20 15:31:03] Restarting dashboard server...
[2026-03-20 15:31:12] ✅ Dashboard verified (HTTP 200)
[2026-03-20 15:31:12] === Sync Complete ===
```

## Example: Add Reporting to the Workflow

```bash
# Run sync and report result
if bash ~/.openclaw/skills/custom/openbb-sync/sync.sh; then
    openclaw message send --target "channel:1478375151270887577" \
        --message "✅ OpenBB sync complete"
else
    openclaw message send --target "channel:1478375151270887577" \
        --message "⚠️ OpenBB sync completed with warnings (exit code: $?)"
fi
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Git pull fails | Check network connectivity and remote URL (`git remote -v`) |
| Pipeline fails | Check `sync.log` for Python errors; verify venv at `$OPENBB_DIR/.venv` |
| Dashboard health check fails (HTTP != 200) | Verify launchctl service exists: `launchctl list \| grep openclaw` |
| Exit code 1 | Pipeline execution failed — check logs for details |
| Exit code 2 | Dashboard verification failed — restart manually or check launchctl config |
