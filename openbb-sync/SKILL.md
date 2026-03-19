---
name: openbb-sync
description: "Sync OpenBB repo from GitHub, rerun data pipeline on changes, restart and verify the dashboard, and report to Discord. Use for automated repo sync, pipeline refresh, and dashboard restart workflows."
---

# OpenBB Sync Skill

Pull the OpenBB repo, rerun the data pipeline when changes are detected, restart the dashboard, and report results to Discord. **Silent by default** — only reports when there's something to report.

## Quick Start

```bash
# Run manually
bash ~/.openclaw/skills/custom/openbb-sync/sync.sh

# View logs
tail -f ~/.openbb_platform/logs/sync.log
```

## How It Works

1. **Safety Check:** Skips if you have uncommitted changes (detects active development)
2. **Sync:** Pulls latest from GitHub
3. **Pipeline:** Runs full data refresh if repo changed
4. **Restart:** Restarts dashboard via launchctl
5. **Verify:** Confirms HTTP 200
6. **Report:** Discord message only if changes detected

## Safety Features

| Check | Action |
|-------|--------|
| Uncommitted git changes | Skip silently (you're coding) |
| No remote changes | Skip silently (nothing new) |
| Pipeline fails | Report error to Discord |
| Dashboard fails health check | Report warning to Discord |

## Configuration

Variables at the top of `sync.sh`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENBB_DIR` | `$HOME/.openbb_platform` | OpenBB platform directory |
| `DISCORD_CHANNEL` | `channel:1478375151270887577` | Discord channel for reports |
| `DASHBOARD_URL` | `http://localhost:8501` | Dashboard health check URL |

## Dependencies

| Tool | Purpose | Notes |
|------|---------|-------|
| bash | Script runtime | |
| git | Repo sync | |
| python 3 | Pipeline execution | Via venv at `$OPENBB_DIR/.venv` |
| curl | Health check | |
| launchctl | Dashboard restart | macOS-specific; adjust for systemd on Linux |
| openclaw CLI | Discord reporting | Falls back to file queue if unavailable |

## Files

| File | Purpose |
|------|---------|
| `sync.sh` | Main sync script |
| `SKILL.md` | This documentation |

## Logs

**Location:** `~/.openbb_platform/logs/sync.log`

**Sample output:**
```
[2026-03-19 16:00:01] === Starting Sync ===
[2026-03-19 16:00:01] Checking for uncommitted changes...
[2026-03-19 16:00:01] ✅ No uncommitted changes. Proceeding with sync.
[2026-03-19 16:00:01] Syncing OpenBB repo...
[2026-03-19 16:00:03] Changes detected! Before: abc1234 → After: def5678
[2026-03-19 16:00:03] Running data pipeline...
[2026-03-19 16:01:45] Pipeline completed successfully
[2026-03-19 16:01:45] Restarting dashboard server...
[2026-03-19 16:01:53] ✅ Dashboard verified (HTTP 200)
[2026-03-19 16:01:53] === Sync Complete ===
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Git pull fails | Check network connectivity and remote URL (`git remote -v`) |
| Pipeline fails | Check `sync.log` for Python errors; verify venv at `$OPENBB_DIR/.venv` |
| Dashboard health check fails (HTTP != 200) | Verify launchctl service exists: `launchctl list \| grep openclaw` |
| Discord messages not sending | Verify `openclaw` CLI is installed; messages fall back to `logs/discord_pending.txt` |
