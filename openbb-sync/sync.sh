#!/bin/bash
# OpenBB Sync Script
# Syncs repo, reruns pipeline if changes detected, restarts dashboard, verifies
# 
# Note: This skill does NOT send Discord messages. Reporting is the caller's responsibility.
# Exit codes:
#   0 - Success (or no changes/skipped)
#   1 - Pipeline failed
#   2 - Dashboard verification failed

set -e

# Configuration
OPENBB_DIR="$HOME/.openbb_platform"
LOG_FILE="$HOME/.openclaw/logs/skills/openbb-sync/sync.log"
DASHBOARD_URL="http://localhost:8501"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Starting Sync ==="

# Step 0: Check for uncommitted local changes (user might be working on code)
log "Checking for uncommitted changes..."
cd "$OPENBB_DIR"

UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

if [ "$UNCOMMITTED" -gt 0 ]; then
    log "⚠️ Uncommitted changes detected ($UNCOMMITTED files). User may be working on code. Skipping sync."
    exit 0
fi

log "✅ No uncommitted changes. Proceeding with sync."

# Step 1: Sync repo
log "Syncing OpenBB repo..."

# Get commit hash before pull
BEFORE_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Pull from remote
PULL_OUTPUT=$(git pull origin main 2>&1) || true

# Get commit hash after pull
AFTER_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Check if anything changed
if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    log "No changes detected (commit: $BEFORE_COMMIT). Exiting silently."
    exit 0
fi

log "Changes detected! Before: $BEFORE_COMMIT → After: $AFTER_COMMIT"

# Extract summary from git pull output
CHANGES_SUMMARY=$(echo "$PULL_OUTPUT" | grep -E "^\s+[a-z]+\s+" | head -10 || echo "Repo updated")

log "Changes: $CHANGES_SUMMARY"

# Step 2: Activate venv
log "Activating virtual environment..."
source "$OPENBB_DIR/.venv/bin/activate"

# Step 3: Rerun pipeline
log "Running data pipeline..."
PIPELINE_OUTPUT=$(python src/run_pipeline.py full 2>&1) || {
    log "❌ Pipeline failed!"
    exit 1
}

log "Pipeline completed successfully"

# Step 4: Restart dashboard
log "Restarting dashboard server..."
# macOS-specific: restart dashboard via launchctl. Adjust for systemd on Linux.
launchctl kickstart -k gui/$(id -u)/com.openclaw.dashboard 2>&1 || true
sleep 8

# Step 5: Verify server is running
log "Verifying dashboard server..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL" 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" != "200" ]; then
    log "❌ Dashboard verification failed (HTTP $HTTP_STATUS)"
    exit 2
fi

log "✅ Dashboard verified (HTTP $HTTP_STATUS)"

log "=== Sync Complete ==="
exit 0
