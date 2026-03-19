# OpenBB Hourly Sync Skill

**Type:** Automation script  
**Trigger:** OpenClaw cron job (hourly)  
**Location:** `~/.openclaw/skills/custom/openbb-sync/`

---

## What It Does

Automated hourly sync for the OpenBB dashboard:

1. **Safety Check:** Skips if you have uncommitted changes (detects active development)
2. **Sync:** Pulls latest from GitHub
3. **Pipeline:** Runs full data refresh if repo changed
4. **Restart:** Restarts dashboard via launchctl
5. **Verify:** Confirms HTTP 200
6. **Report:** Discord message only if changes detected

**Silent by default** — only reports when there's something to report.

---

## Files

| File | Purpose |
|------|---------|
| `hourly_sync.sh` | Main sync script |
| `README.md` | This file |
| `logs/hourly_sync.log` | Sync logs (created on first run) |

**Note:** Script moved from `~/.openbb_platform/scripts/` to OpenClaw skills folder.

---

## Manual Execution

```bash
# Run manually for testing
bash ~/.openclaw/skills/custom/openbb-sync/hourly_sync.sh

# View logs
tail -f ~/.openclaw/skills/custom/openbb-sync/logs/hourly_sync.log
```

---

## Cron Job

Managed via OpenClaw cron:

```bash
# List cron jobs
openclaw cron list

# Run now (test)
openclaw cron run openbb-hourly-sync

# View job details
openclaw cron list | grep openbb
```

**Schedule:** Every hour at `:00` (Asia/Shanghai timezone)

---

## Safety Features

| Check | Action |
|-------|--------|
| Uncommitted git changes | Skip silently (you're coding) |
| No remote changes | Skip silently (nothing new) |
| Pipeline fails | Report error to Discord |
| Dashboard fails health check | Report warning to Discord |

---

## Logs

**Location:** `~/.openclaw/skills/custom/openbb-sync/logs/hourly_sync.log`

**Sample output:**
```
[2026-03-19 16:00:01] === Starting Hourly Sync ===
[2026-03-19 16:00:01] Checking for uncommitted changes...
[2026-03-19 16:00:01] ✅ No uncommitted changes. Proceeding with sync.
[2026-03-19 16:00:01] Syncing OpenBB repo...
[2026-03-19 16:00:03] Changes detected! Before: abc1234 → After: def5678
[2026-03-19 16:00:03] Running data pipeline...
[2026-03-19 16:01:45] Pipeline completed successfully
[2026-03-19 16:01:45] Restarting dashboard server...
[2026-03-19 16:01:53] Verifying dashboard server...
[2026-03-19 16:01:53] ✅ Dashboard verified (HTTP 200)
[2026-03-19 16:01:53] Sending update report to Discord...
[2026-03-19 16:01:53] === Hourly Sync Complete ===
```

---

## Cron Job ID

`790ae0f8-ed04-4121-9058-8922ff5c80a6`

---

*Part of OpenClaw Finance Agent workspace*
