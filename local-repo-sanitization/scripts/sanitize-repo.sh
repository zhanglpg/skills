#!/bin/bash

# sanitize-repo.sh - Sanitize a GitHub repository
# Checks for uncommitted changes, analyzes README, updates documentation,
# and verifies GitHub Actions workflows.

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config.json"
CLAUDE_PATH="/Users/lipingzhang/.local/bin/claude"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Error codes
ERR_SUCCESS=0
ERR_UNCOMMITTED=1
ERR_PATH_NOT_FOUND=2
ERR_NOT_GIT_REPO=3
ERR_GH_CLI=4
ERR_CLAUDE=5
ERR_CONFIG=6

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
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

# Check for uncommitted changes (CRITICAL SAFETY CHECK)
check_uncommitted_changes() {
    local repo_path="$1"
    local check_untracked="$2"

    cd "$repo_path" || exit 1

    # Get all status lines
    local all_changes
    all_changes=$(git status --porcelain 2>/dev/null)

    if [ -z "$all_changes" ]; then
        return 0
    fi

    # Filter: always check tracked file changes (staged/unstaged)
    local tracked_changes
    tracked_changes=$(echo "$all_changes" | grep -v "^??" || true)

    if [ -n "$tracked_changes" ]; then
        echo "$tracked_changes"
        return 1
    fi

    # Only check untracked files if configured
    if [ "$check_untracked" = "true" ]; then
        local untracked
        untracked=$(echo "$all_changes" | grep "^??" || true)
        if [ -n "$untracked" ]; then
            echo "$untracked"
            return 1
        fi
    fi

    return 0
}

# Get repository info from config
get_repo_config() {
    local repo_name="$1"
    local field="$2"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Config file not found: $CONFIG_FILE"
        exit $ERR_CONFIG
    fi
    
    # Use jq to parse JSON
    if command -v jq &> /dev/null; then
        jq -r ".repos[] | select(.name == \"$repo_name\") | .$field" "$CONFIG_FILE"
    else
        log_error "jq is required but not installed"
        exit $ERR_CONFIG
    fi
}

# Get all repo names from config
get_all_repo_names() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Config file not found: $CONFIG_FILE"
        exit $ERR_CONFIG
    fi
    
    jq -r ".repos[].name" "$CONFIG_FILE"
}

# Get settings from config
get_setting() {
    local key="$1"
    local default="$2"
    
    if command -v jq &> /dev/null; then
        local value
        value=$(jq -r ".settings.$key // \"$default\"" "$CONFIG_FILE" 2>/dev/null)
        if [ "$value" = "null" ] || [ -z "$value" ]; then
            echo "$default"
        else
            echo "$value"
        fi
    else
        echo "$default"
    fi
}

# Spawn Claude Code for README analysis
analyze_readme() {
    local repo_path="$1"
    local readme_file="$2"
    
    log_info "Spawning Claude Code for deep README analysis..."
    
    cd "$repo_path" || exit 1
    
    # Check if README exists
    if [ ! -f "$readme_file" ]; then
        log_warning "README not found at $readme_file, checking for alternatives..."
        if [ -f "README.md" ]; then
            readme_file="README.md"
        elif [ -f "readme.md" ]; then
            readme_file="readme.md"
        elif [ -f "Readme.md" ]; then
            readme_file="Readme.md"
        else
            log_warning "No README found, skipping analysis"
            return 0
        fi
    fi
    
    # Create analysis prompt
    local prompt="Analyze this repository and its README file. Compare the README documentation with the actual codebase structure. Identify any discrepancies, outdated information, or missing documentation. Provide specific recommendations for updates.

Repository: $repo_path
README: $readme_file

Tasks:
1. List the main components/modules in the codebase
2. Check if README accurately describes the project structure
3. Identify any features in code not mentioned in README
4. Identify any documented features that no longer exist
5. Check if installation/setup instructions are current
6. Verify API/function documentation matches actual signatures
7. Recommend specific updates needed

Output format:
- ACCURATE: List of accurate sections
- OUTDATED: List of outdated sections with specific issues
- MISSING: List of missing documentation
- RECOMMENDATIONS: Specific changes to make"

    # Run Claude Code analysis
    local analysis_output
    analysis_output=$($CLAUDE_PATH -p "$prompt" --model sonnet --permission-mode plan 2>&1) || {
        log_error "Claude Code analysis failed"
        return $ERR_CLAUDE
    }
    
    echo "$analysis_output"
}

# Update README based on analysis
update_readme() {
    local repo_path="$1"
    local analysis="$2"
    local readme_file="$3"
    
    log_info "Updating README based on analysis..."
    
    cd "$repo_path" || exit 1
    
    # Create update prompt for implementation
    local prompt="Based on the following analysis, update the README file to accurately reflect the codebase. Make only necessary changes - don't rewrite everything.

ANALYSIS:
$analysis

README FILE: $readme_file

Tasks:
1. Update outdated sections
2. Add missing documentation
3. Remove references to non-existent features
4. Ensure consistency with actual code structure

IMPORTANT: 
- Preserve the existing README style and format
- Only change what's necessary for accuracy
- Keep commits focused on documentation accuracy

Please implement the necessary changes to the README file."

    # Run Claude Code for implementation
    local update_output
    update_output=$($CLAUDE_PATH -p "$prompt" --model sonnet --permission-mode acceptEdits 2>&1) || {
        log_error "README update failed"
        return $ERR_CLAUDE
    }
    
    echo "$update_output"
}

# Commit and push changes
commit_and_push() {
    local repo_path="$1"
    local commit_message="$2"
    local branch="$3"
    
    cd "$repo_path" || exit 1
    
    # Check if there are changes to commit
    local changes
    changes=$(git status --porcelain)
    
    if [ -z "$changes" ]; then
        log_info "No changes to commit"
        return 0
    fi
    
    # Stage changes
    git add -A || {
        log_error "Failed to stage changes"
        return $ERR_GH_CLI
    }
    
    # Commit
    git commit -m "$commit_message" || {
        log_error "Failed to commit changes"
        return $ERR_GH_CLI
    }
    
    # Push
    git push origin "$branch" || {
        log_error "Failed to push changes"
        return $ERR_GH_CLI
    }
    
    log_success "Changes committed and pushed"
    return 0
}

# Check GitHub Actions status
check_github_actions() {
    local remote="$1"
    local branch="$2"
    
    log_info "Checking GitHub Actions status for $remote..."
    
    # Get recent workflow runs
    local runs
    runs=$(gh run list --repo "$remote" --branch "$branch" --limit 5 --json status,conclusion,name,createdAt 2>/dev/null) || {
        log_warning "Failed to fetch workflow runs (gh CLI may not be authenticated)"
        return $ERR_GH_CLI
    }
    
    if [ -z "$runs" ] || [ "$runs" = "null" ]; then
        log_info "No workflow runs found"
        return 0
    fi
    
    # Parse and display results
    echo "$runs" | jq -r '.[] | "[\(.status)] \(.name): \(.conclusion // "in_progress") (\(.createdAt))"' 2>/dev/null || {
        log_warning "Failed to parse workflow runs"
    }
    
    # Check for failures
    local failures
    failures=$(echo "$runs" | jq -r '[.[] | select(.conclusion == "failure")] | length' 2>/dev/null) || {
        failures=0
    }
    
    if [ "$failures" -gt 0 ]; then
        log_warning "Found $failures failed workflow run(s)"
        return 1
    fi
    
    log_success "All workflows passing"
    return 0
}

# Fix broken workflows by fetching failure logs and spawning Claude Code
fix_broken_workflows() {
    local repo_path="$1"
    local remote="$2"
    local branch="$3"

    cd "$repo_path" || exit 1

    # Get recent failed runs with workflow names
    local failed_runs
    failed_runs=$(gh run list --repo "$remote" --branch "$branch" --status failure --limit 5 --json databaseId,name,workflowName 2>/dev/null) || {
        log_warning "Failed to fetch failed run details"
        return $ERR_GH_CLI
    }

    if [ -z "$failed_runs" ] || [ "$failed_runs" = "null" ] || [ "$failed_runs" = "[]" ]; then
        log_info "No failed runs to analyze"
        return 0
    fi

    # Process each failed run
    local fixed_any=false
    echo "$failed_runs" | jq -c '.[]' 2>/dev/null | while read -r run; do
        local run_id workflow_name
        run_id=$(echo "$run" | jq -r '.databaseId' 2>/dev/null)
        workflow_name=$(echo "$run" | jq -r '.workflowName // .name' 2>/dev/null)

        if [ -z "$run_id" ] || [ "$run_id" = "null" ]; then
            continue
        fi

        log_info "Analyzing failed run #$run_id ($workflow_name)..."

        # Fetch the actual failure logs
        local failure_logs
        failure_logs=$(gh run view "$run_id" --repo "$remote" --log-failed 2>/dev/null | tail -100) || {
            log_warning "Could not fetch logs for run #$run_id"
            continue
        }

        if [ -z "$failure_logs" ]; then
            failure_logs="(No failure logs available)"
        fi

        # Spawn Claude Code with both the workflow file and actual failure logs
        local prompt="A GitHub Actions workflow has failed in this repository.

Repository: $repo_path
Workflow: $workflow_name
Failed run ID: $run_id

## Failure logs (last 100 lines):
$failure_logs

## Task:
1. Read the relevant workflow file(s) under .github/workflows/
2. Analyze the failure logs above to understand the root cause
3. Fix the issue — it may be in the workflow YAML, in the code, or in dependencies
4. Make minimal changes to resolve the failure

Please fix the issue."

        local fix_output
        fix_output=$($CLAUDE_PATH -p "$prompt" --model sonnet --permission-mode acceptEdits 2>&1) || {
            log_warning "Automated fix failed for $workflow_name"
            continue
        }

        log_success "Fix attempted for $workflow_name (run #$run_id)"
        fixed_any=true
    done

    return 0
}

# Print repository status report
print_status_report() {
    local repo_name="$1"
    local status="$2"
    local readme_changes="$3"
    local workflow_status="$4"
    local fixes_applied="$5"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}[OK]${NC} Repository: $repo_name"
    elif [ "$status" = "UNCOMMITTED" ]; then
        echo -e "${RED}[ERROR]${NC} Repository: $repo_name"
    else
        echo -e "${YELLOW}[WARN]${NC} Repository: $repo_name"
    fi
    echo "├─ Status: $status"
    
    if [ -n "$readme_changes" ]; then
        echo "├─ README: $readme_changes"
    fi
    
    if [ -n "$workflow_status" ]; then
        echo "├─ Workflows: $workflow_status"
    fi
    
    if [ -n "$fixes_applied" ]; then
        echo "├─ Fixes Applied: $fixes_applied"
    fi
    
    echo "└─ Completed: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# Sanitize a single repository
sanitize_repo() {
    local repo_path="$1"
    local repo_name="$2"
    local remote="$3"
    local branch="$4"
    local check_untracked="$5"
    
    log_info "Starting sanitization for: $repo_name"
    log_info "Path: $repo_path"
    
    # Validate path exists
    if [ ! -d "$repo_path" ]; then
        log_error "Repository path not found: $repo_path"
        print_status_report "$repo_name" "ERROR" "" "" "Path not found"
        return $ERR_PATH_NOT_FOUND
    fi
    
    # Validate it's a git repo
    if ! is_git_repo "$repo_path"; then
        log_error "Not a git repository: $repo_path"
        print_status_report "$repo_name" "ERROR" "" "" "Not a git repo"
        return $ERR_NOT_GIT_REPO
    fi
    
    # CRITICAL: Check for uncommitted changes
    log_info "Checking for uncommitted changes..."
    local uncommitted
    uncommitted=$(check_uncommitted_changes "$repo_path" "$check_untracked" 2>&1) || {
        log_error "UNCOMMITTED CHANGES DETECTED"
        echo ""
        echo "Modified files:"
        echo "$uncommitted" | while read -r line; do
            echo "  $line"
        done
        echo ""
        echo "Action required: Commit or stash changes before sanitization"
        echo ""
        print_status_report "$repo_name" "UNCOMMITTED" "" "" "Uncommitted changes detected"
        return $ERR_UNCOMMITTED
    }
    
    log_success "Working directory is clean"
    
    # Find README file
    local readme_file="README.md"
    if [ ! -f "$repo_path/$readme_file" ]; then
        for f in README.md readme.md Readme.md README README.txt; do
            if [ -f "$repo_path/$f" ]; then
                readme_file="$f"
                break
            fi
        done
    fi
    
    # Analyze README
    local analysis=""
    local readme_changes="No changes needed"
    
    if [ -f "$repo_path/$readme_file" ]; then
        analysis=$(analyze_readme "$repo_path" "$readme_file") || {
            log_warning "README analysis failed, continuing..."
        }
        
        if [ -n "$analysis" ]; then
            # Check if updates are needed
            if echo "$analysis" | grep -q "OUTDATED\|MISSING"; then
                log_info "Discrepancies found, updating README..."
                update_readme "$repo_path" "$analysis" "$readme_file" || {
                    log_warning "README update failed"
                }
                readme_changes="Updated based on code analysis"
            else
                log_success "README is accurate"
                readme_changes="Accurate (no changes needed)"
            fi
        fi
    else
        log_warning "No README found, skipping analysis"
        readme_changes="No README present"
    fi
    
    # Commit and push if changes were made
    if [ "$readme_changes" = "Updated based on code analysis" ]; then
        local commit_prefix
        commit_prefix=$(get_setting "commitPrefix" "docs:")
        commit_and_push "$repo_path" "${commit_prefix} update README to reflect current codebase" "$branch" || {
            log_warning "Failed to commit changes"
        }
    fi
    
    # Check GitHub Actions
    local workflow_status="Not checked"
    local fixes_applied="None"
    
    if command -v gh &> /dev/null; then
        check_github_actions "$remote" "$branch" || {
            workflow_status="Failures detected"
            
            # Attempt to fix if enabled
            local auto_fix
            auto_fix=$(get_setting "autoFixWorkflows" "true")
            if [ "$auto_fix" = "true" ]; then
                log_info "Attempting to fix broken workflows..."
                fix_broken_workflows "$repo_path" "$remote" "$branch" || true
                fixes_applied="Attempted fixes"

                # Commit workflow fixes if any changes were made
                commit_and_push "$repo_path" "fix: resolve workflow issues" "$branch" || true
            fi
        }
        
        if [ "$workflow_status" = "Not checked" ]; then
            workflow_status="All passing"
        fi
    else
        log_warning "GitHub CLI not available, skipping workflow check"
        workflow_status="gh CLI not available"
    fi
    
    # Print final report
    print_status_report "$repo_name" "OK" "$readme_changes" "$workflow_status" "$fixes_applied"
    
    return $ERR_SUCCESS
}

# Sanitize all configured repositories
sanitize_all() {
    log_info "Sanitizing all configured repositories..."
    echo ""
    
    local repo_names
    repo_names=$(get_all_repo_names)
    
    local success_count=0
    local error_count=0
    local skipped_count=0
    
    echo "$repo_names" | while read -r repo_name; do
        if [ -z "$repo_name" ]; then
            continue
        fi
        
        local repo_path remote branch check_untracked
        repo_path=$(get_repo_config "$repo_name" "path")
        remote=$(get_repo_config "$repo_name" "remote")
        branch=$(get_repo_config "$repo_name" "branch")
        check_untracked=$(get_setting "checkUntrackedFiles" "false")

        # Expand path
        repo_path=$(expand_path "$repo_path")

        sanitize_repo "$repo_path" "$repo_name" "$remote" "$branch" "$check_untracked"
        
        local result=$?
        if [ $result -eq 0 ]; then
            ((success_count++))
        elif [ $result -eq $ERR_UNCOMMITTED ]; then
            ((skipped_count++))
        else
            ((error_count++))
        fi
    done
    
    echo ""
    log_info "Sanitization complete"
    log_info "Success: $success_count, Skipped: $skipped_count, Errors: $error_count"
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] <repo-path>"
    echo ""
    echo "Sanitize a GitHub repository by updating README and checking workflows."
    echo ""
    echo "Options:"
    echo "  --all              Sanitize all configured repositories"
    echo "  --config <file>    Use custom config file (default: config.json)"
    echo "  --dry-run          Show what would be done without making changes"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 ~/.openclaw/workspace-coding/my-repo"
    echo "  $0 --all"
    echo ""
    echo "Configured repositories:"
    get_all_repo_names | while read -r name; do
        if [ -n "$name" ]; then
            local path
            path=$(get_repo_config "$name" "path")
            echo "  - $name: $path"
        fi
    done
}

# Main entry point
main() {
    # Parse arguments
    if [ $# -eq 0 ]; then
        show_usage
        exit $ERR_SUCCESS
    fi
    
    case "$1" in
        --all)
            sanitize_all
            exit $?
            ;;
        --help|-h)
            show_usage
            exit $ERR_SUCCESS
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --dry-run)
            log_warning "Dry run mode not fully implemented"
            shift
            ;;
        *)
            # Single repo sanitization
            local repo_path="$1"
            repo_path=$(expand_path "$repo_path")
            
            # Try to find repo name from config
            local repo_name="unknown"
            local remote=""
            local branch="main"
            local check_untracked="false"

            # Search config for matching path
            if [ -f "$CONFIG_FILE" ] && command -v jq &> /dev/null; then
                local expanded_path="$repo_path"
                repo_name=$(jq -r --arg path "$expanded_path" '.repos[] | select(.path == $path or .path == "'"$repo_path"'") | .name' "$CONFIG_FILE" 2>/dev/null | head -1)

                if [ -n "$repo_name" ] && [ "$repo_name" != "null" ]; then
                    remote=$(get_repo_config "$repo_name" "remote")
                    branch=$(get_repo_config "$repo_name" "branch")
                    check_untracked=$(get_setting "checkUntrackedFiles" "false")
                fi
            fi

            if [ -z "$repo_name" ] || [ "$repo_name" = "null" ]; then
                repo_name=$(basename "$repo_path")
                log_warning "Repository not in config, using defaults"
            fi

            sanitize_repo "$repo_path" "$repo_name" "$remote" "$branch" "$check_untracked"
            exit $?
            ;;
    esac
}

# Run main
main "$@"
