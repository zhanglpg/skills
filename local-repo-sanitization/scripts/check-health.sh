#!/bin/bash

# check-health.sh - Check repository health (read-only)
# Checks for uncommitted changes and GitHub Actions status without making modifications.

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_section() {
    echo -e "\n${CYAN}═══ $1 ═══${NC}\n"
}

# Expand tilde in path
expand_path() {
    local path="$1"
    if [[ "$path" == ~* ]]; then
        echo "${path/#\~/$HOME}"
    else
    echo "$path"
    fi
}

# Check if path is a git repository
is_git_repo() {
    local path="$1"
    if [ -d "$path/.git" ]; then
        return 0
    fi
    return 1
}

# Check for uncommitted changes
check_uncommitted_changes() {
    local repo_path="$1"
    
    cd "$repo_path" || return 1
    
    # Get git status
    local status
    status=$(git status --porcelain 2>/dev/null)
    
    if [ -n "$status" ]; then
        echo "$status"
        return 1
    fi
    
    return 0
}

# Get branch info
get_branch_info() {
    local repo_path="$1"
    
    cd "$repo_path" || return 1
    
    local current_branch
    current_branch=$(git branch --show-current 2>/dev/null)
    
    local ahead_behind
    ahead_behind=$(git status --branch --porcelain 2>/dev/null | head -1)
    
    echo "Branch: $current_branch"
    echo "Status: $ahead_behind"
}

# Check GitHub Actions status
check_github_actions() {
    local remote="$1"
    local branch="$2"
    
    if ! command -v gh &> /dev/null; then
        echo "GitHub CLI not available"
        return 1
    fi
    
    # Check authentication
    if ! gh auth status &> /dev/null; then
        echo "GitHub CLI not authenticated"
        return 1
    fi
    
    # Get recent workflow runs
    local runs
    runs=$(gh run list --repo "$remote" --branch "$branch" --limit 10 --json status,conclusion,name,createdAt,workflowName 2>/dev/null)
    
    if [ -z "$runs" ] || [ "$runs" = "null" ] || [ "$runs" = "[]" ]; then
        echo "No workflow runs found"
        return 0
    fi
    
    # Count by status
    local total passing failed in_progress
    total=$(echo "$runs" | jq 'length' 2>/dev/null)
    passing=$(echo "$runs" | jq '[.[] | select(.conclusion == "success")] | length' 2>/dev/null)
    failed=$(echo "$runs" | jq '[.[] | select(.conclusion == "failure" or .conclusion == "cancelled")] | length' 2>/dev/null)
    in_progress=$(echo "$runs" | jq '[.[] | select(.status == "in_progress")] | length' 2>/dev/null)
    
    echo "Total runs: $total"
    echo "Passing: $passing"
    echo "Failed: $failed"
    echo "In progress: $in_progress"
    echo ""
    echo "Recent runs:"
    
    # Display recent runs
    echo "$runs" | jq -r '.[:5] | .[] | "  \(.workflowName // .name): \(.conclusion // .status) (\(.createdAt | split("T")[0]))"' 2>/dev/null
    
    # Return non-zero if failures exist
    if [ "$failed" -gt 0 ]; then
        return 1
    fi
    
    return 0
}

# Check for common issues
check_common_issues() {
    local repo_path="$1"
    
    cd "$repo_path" || return 1
    
    local issues_found=0
    
    # Check for large files
    local large_files
    large_files=$(find . -type f -size +10M -not -path "./.git/*" 2>/dev/null | head -5)
    if [ -n "$large_files" ]; then
        echo "⚠ Large files detected (>10MB):"
        echo "$large_files" | while read -r f; do
            echo "    $f"
        done
        ((issues_found++))
    fi
    
    # Check for merge conflict markers
    local conflict_files
    conflict_files=$(grep -r "<<<<<<< " --include="*.ts" --include="*.js" --include="*.py" --include="*.go" --include="*.rs" --include="*.md" . 2>/dev/null | head -5)
    if [ -n "$conflict_files" ]; then
        echo "⚠ Merge conflict markers found:"
        echo "$conflict_files" | head -3 | while read -r line; do
            echo "    $line"
        done
        ((issues_found++))
    fi
    
    # Check for TODO/FIXME comments
    local todo_count
    todo_count=$(grep -r "TODO\|FIXME" --include="*.ts" --include="*.js" --include="*.py" --include="*.go" --include="*.rs" . 2>/dev/null | wc -l)
    if [ "$todo_count" -gt 10 ]; then
        echo "ℹ High TODO/FIXME count: $todo_count"
    fi
    
    # Check for outdated dependencies (if package.json exists)
    if [ -f "package.json" ]; then
        echo "ℹ Node.js project detected"
        if [ -d "node_modules" ]; then
            local node_modules_age
            node_modules_age=$(find node_modules -type d -maxdepth 0 -mtime +30 2>/dev/null | wc -l)
            if [ "$node_modules_age" -gt 0 ]; then
                echo "⚠ node_modules may be outdated (last modified >30 days ago)"
            fi
        fi
    fi
    
    return $issues_found
}

# Get repository statistics
get_repo_stats() {
    local repo_path="$1"
    
    cd "$repo_path" || return 1
    
    # Count files by type
    local total_files
    total_files=$(find . -type f -not -path "./.git/*" | wc -l)
    
    # Count code files
    local code_files
    code_files=$(find . -type f \( -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.cpp" -o -name "*.c" -o -name "*.h" \) -not -path "./.git/*" | wc -l)
    
    # Count test files
    local test_files
    test_files=$(find . -type f \( -name "*.test.*" -o -name "*.spec.*" -o -name "*_test.*" \) -not -path "./.git/*" | wc -l)
    
    # Get last commit info
    local last_commit
    last_commit=$(git log -1 --format="%h - %s (%cr)" 2>/dev/null)
    
    echo "Total files: $total_files"
    echo "Code files: $code_files"
    echo "Test files: $test_files"
    echo "Last commit: $last_commit"
}

# Print health report
print_health_report() {
    local repo_name="$1"
    local repo_path="$2"
    local remote="$3"
    local branch="$4"
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  HEALTH REPORT: $repo_name"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "Repository: $repo_path"
    echo "Remote: $remote"
    echo "Branch: $branch"
    echo ""
    
    log_section "Working Directory Status"
    
    local uncommitted
    uncommitted=$(check_uncommitted_changes "$repo_path" 2>&1) || {
        log_error "Uncommitted changes detected:"
        echo "$uncommitted" | while read -r line; do
            if [ -n "$line" ]; then
                echo "  $line"
            fi
        done
        echo ""
        echo "Recommendation: Commit or stash changes before deployment"
    }
    
    if [ -z "$uncommitted" ]; then
        log_success "Working directory is clean"
    fi
    
    # Show branch info
    get_branch_info "$repo_path" | while read -r line; do
        echo "  $line"
    done
    
    log_section "Repository Statistics"
    get_repo_stats "$repo_path" | while read -r line; do
        echo "  $line"
    done
    
    log_section "GitHub Actions Status"
    
    if command -v gh &> /dev/null; then
        local actions_status
        actions_status=$(check_github_actions "$remote" "$branch" 2>&1)
        local actions_result=$?
        
        echo "$actions_status" | while read -r line; do
            if [[ "$line" == *"✗"* ]] || [[ "$line" == "Failed:"* ]]; then
                echo -e "${RED}$line${NC}"
            elif [[ "$line" == *"✓"* ]] || [[ "$line" == "Passing:"* ]]; then
                echo -e "${GREEN}$line${NC}"
            else
                echo "  $line"
            fi
        done
        
        if [ $actions_result -ne 0 ]; then
            echo ""
            log_warning "Some workflows are failing"
            echo "  Recommendation: Check GitHub Actions logs"
        else
            echo ""
            log_success "All workflows passing"
        fi
    else
        log_warning "GitHub CLI not available"
        echo "  Install with: brew install gh"
    fi
    
    log_section "Common Issues Check"
    check_common_issues "$repo_path" || {
        echo ""
        log_warning "Some issues were found (see above)"
    }
    
    # Overall health summary
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  HEALTH SUMMARY"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    
    local health_score=100
    local recommendations=()
    
    # Check uncommitted changes
    if ! check_uncommitted_changes "$repo_path" > /dev/null 2>&1; then
        ((health_score -= 20))
        recommendations+=("Commit or stash uncommitted changes")
    fi
    
    # Check GitHub Actions (if available)
    if command -v gh &> /dev/null; then
        if ! check_github_actions "$remote" "$branch" > /dev/null 2>&1; then
            ((health_score -= 30))
            recommendations+=("Fix failing GitHub Actions workflows")
        fi
    fi
    
    # Display health score
    if [ $health_score -ge 90 ]; then
        echo -e "Overall Health: ${GREEN}EXCELLENT ($health_score/100)${NC}"
    elif [ $health_score -ge 70 ]; then
        echo -e "Overall Health: ${YELLOW}GOOD ($health_score/100)${NC}"
    elif [ $health_score -ge 50 ]; then
        echo -e "Overall Health: ${YELLOW}FAIR ($health_score/100)${NC}"
    else
        echo -e "Overall Health: ${RED}NEEDS ATTENTION ($health_score/100)${NC}"
    fi
    
    # Show recommendations
    if [ ${#recommendations[@]} -gt 0 ]; then
        echo ""
        echo "Recommendations:"
        for rec in "${recommendations[@]}"; do
            echo "  • $rec"
        done
    else
        echo ""
        log_success "No critical issues found"
    fi
    
    echo ""
}

# Get repository config
get_repo_config() {
    local repo_name="$1"
    local field="$2"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        return 1
    fi
    
    if command -v jq &> /dev/null; then
        jq -r ".repos[] | select(.name == \"$repo_name\") | .$field" "$CONFIG_FILE"
    else
        return 1
    fi
}

# Get all repo names
get_all_repo_names() {
    if [ ! -f "$CONFIG_FILE" ]; then
        return 1
    fi
    
    jq -r ".repos[].name" "$CONFIG_FILE"
}

# Check health of a single repository
check_repo_health() {
    local repo_path="$1"
    local repo_name="$2"
    local remote="$3"
    local branch="$4"
    
    # Validate path
    if [ ! -d "$repo_path" ]; then
        log_error "Repository path not found: $repo_path"
        return 1
    fi
    
    # Validate git repo
    if ! is_git_repo "$repo_path"; then
        log_error "Not a git repository: $repo_path"
        return 1
    fi
    
    # Print health report
    print_health_report "$repo_name" "$repo_path" "$remote" "$branch"
}

# Check health of all repositories
check_all_health() {
    log_info "Checking health of all configured repositories..."
    
    local repo_names
    repo_names=$(get_all_repo_names)
    
    echo "$repo_names" | while read -r repo_name; do
        if [ -z "$repo_name" ]; then
            continue
        fi
        
        local repo_path remote branch
        repo_path=$(get_repo_config "$repo_name" "path")
        remote=$(get_repo_config "$repo_name" "remote")
        branch=$(get_repo_config "$repo_name" "branch")
        
        # Expand path
        repo_path=$(expand_path "$repo_path")
        
        check_repo_health "$repo_path" "$repo_name" "$remote" "$branch"
    done
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] <repo-path>"
    echo ""
    echo "Check repository health without making modifications (read-only)."
    echo ""
    echo "Options:"
    echo "  --all              Check all configured repositories"
    echo "  --config <file>    Use custom config file (default: config.json)"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 ~/.openclaw/workspace-coding/my-repo"
    echo "  $0 --all"
    echo ""
    echo "Configured repositories:"
    if [ -f "$CONFIG_FILE" ] && command -v jq &> /dev/null; then
        get_all_repo_names | while read -r name; do
            if [ -n "$name" ]; then
                local path
                path=$(get_repo_config "$name" "path")
                echo "  - $name: $path"
            fi
        done
    fi
}

# Main entry point
main() {
    # Parse arguments
    if [ $# -eq 0 ]; then
        show_usage
        exit 0
    fi
    
    case "$1" in
        --all)
            check_all_health
            exit 0
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        *)
            # Single repo health check
            local repo_path="$1"
            repo_path=$(expand_path "$repo_path")
            
            # Try to find repo name from config
            local repo_name="unknown"
            local remote=""
            local branch="main"
            
            if [ -f "$CONFIG_FILE" ] && command -v jq &> /dev/null; then
                repo_name=$(jq -r --arg path "$repo_path" '.repos[] | select(.path == $path) | .name' "$CONFIG_FILE" 2>/dev/null | head -1)
                
                if [ -n "$repo_name" ] && [ "$repo_name" != "null" ]; then
                    remote=$(get_repo_config "$repo_name" "remote")
                    branch=$(get_repo_config "$repo_name" "branch")
                fi
            fi
            
            if [ -z "$repo_name" ] || [ "$repo_name" = "null" ]; then
                repo_name=$(basename "$repo_path")
            fi
            
            check_repo_health "$repo_path" "$repo_name" "$remote" "$branch"
            exit 0
            ;;
    esac
}

# Run main
main "$@"
