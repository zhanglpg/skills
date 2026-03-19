#!/bin/bash
# Hourly OpenBB Sync Script
# Syncs repo, reruns pipeline if changes detected, restarts dashboard, verifies & reports

set -e

# Configuration
OPENBB_DIR="$HOME/.openbb_platform"
LOG_FILE="$OPENBB_DIR/logs/hourly_sync.log"
DISCORD_CHANNEL="channel:1478375151270887577"
DASHBOARD_URL="http://localhost:8501"

# Ensure log directory exists
mkdir -p "$OPENBB_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_discord_alert() {
    local title="$1"
    local message="$2"
    
    # Use openclaw message tool via CLI if available
    if command -v openclaw &> /dev/null; then
        openclaw message send --target "$DISCORD_CHANNEL" --message "**$title**

$message" 2>/dev/null || log "Warning: Could not send Discord message"
    else
        # Fallback: write to a file that can be picked up by another process
        echo "$title: $message" >> "$OPENBB_DIR/logs/discord_pending.txt"
        log "Discord message queued (openclaw CLI not available)"
    fi
}

log "=== Starting Hourly Sync ==="

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
    send_discord_alert "❌ OpenBB Sync Failed" "Pipeline execution failed. Check logs: $LOG_FILE"
    exit 1
}

log "Pipeline completed successfully"

# Step 4: Restart dashboard
log "Restarting dashboard server..."
launchctl kickstart -k gui/$(id -u)/com.openclaw.dashboard 2>&1 || true
sleep 8

# Step 5: Verify server is running
log "Verifying dashboard server..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL" 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" != "200" ]; then
    log "❌ Dashboard verification failed (HTTP $HTTP_STATUS)"
    send_discord_alert "❌ OpenBB Sync Warning" "Dashboard restarted but health check failed (HTTP $HTTP_STATUS)"
    exit 1
fi

log "✅ Dashboard verified (HTTP $HTTP_STATUS)"

# Step 6: Get pipeline summary for report
PRICES_COUNT=$(echo "$PIPELINE_OUTPUT" | grep -oP "\d+ rows saved" | head -1 || echo "N/A")
ECONOMIC_STATUS=$(echo "$PIPELINE_OUTPUT" | grep -c "rows saved" || echo "0")

# Step 7: Report to Discord
log "Sending update report to Discord..."

REPORT=$(cat <<EOF
✅ **OpenBB Hourly Sync Complete**

**Commit:** \`${BEFORE_COMMIT:0:7}\` → \`${AFTER_COMMIT:0:7}\`

**Changes:**
\`\`\`
$CHANGES_SUMMARY
\`\`\`

**Pipeline:** ✅ Complete
**Dashboard:** ✅ Verified (HTTP $HTTP_STATUS)
**Data Freshness:** 🟢 Just synced

**Timestamp:** $(date '+%Y-%m-%d %H:%M:%S GMT+8')
EOF
)

send_discord_alert "🔄 OpenBB Auto-Sync" "$REPORT"

log "=== Hourly Sync Complete ==="
exit 0

send_discord_alert() {
    local title="$1"
    local message="$2"
    
    # Use openclaw message tool via CLI if available
    if command -v openclaw &> /dev/null; then
        openclaw message send --target "$DISCORD_CHANNEL" --message "**$title**

$message" 2>/dev/null || log "Warning: Could not send Discord message"
    else
        # Fallback: write to a file that can be picked up by another process
        echo "$title: $message" >> "$OPENBB_DIR/logs/discord_pending.txt"
        log "Discord message queued (openclaw CLI not available)"
    fi
}
