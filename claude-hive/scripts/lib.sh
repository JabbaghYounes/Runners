#!/bin/bash
# Shared functions for claude-hive scripts
# Source this from other scripts: source "$HIVE_DIR/scripts/lib.sh"

# Default rate limit wait (seconds) — can be overridden in hive.conf
RATE_LIMIT_WAIT="${RATE_LIMIT_WAIT:-600}"

# --- Logging ---

# Initialize a log directory for this pipeline run.
# Sets HIVE_RUN_LOG_DIR (exported so child processes inherit it).
# Call once at the start of run-product.sh or swarm.sh.
init_run_log() {
  local log_base="${LOG_DIR:-${HIVE_DIR:-/tmp}/prd/logs}"
  export HIVE_RUN_LOG_DIR="$log_base/run-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$HIVE_RUN_LOG_DIR"
  echo "Logs: $HIVE_RUN_LOG_DIR" >&2
}

# Compute a log file path for an agent call.
# Usage: log_path <agent-name>
# Respects HIVE_FEATURE_SLUG (set by prd-swarm.sh or swarm.sh).
_agent_log_path() {
  local agent=$1
  if [[ -z "${HIVE_RUN_LOG_DIR:-}" ]]; then
    echo ""
    return
  fi
  local subdir="${HIVE_FEATURE_SLUG:-standalone}"
  local dir="$HIVE_RUN_LOG_DIR/$subdir"
  mkdir -p "$dir"
  echo "$dir/${agent}-$(date +%s).log"
}

# --- Rate limiting ---

# Check if file content indicates a rate limit
is_rate_limited() {
  local file=$1
  grep -qiE "hit your limit|rate.?limit|too many requests|overloaded|usage limit" "$file" 2>/dev/null
}

# Run claude with automatic rate-limit detection and retry.
# Captures stdout to a temp file, checks for rate limit patterns,
# sleeps and retries if rate-limited. On success, outputs to stdout
# so callers can redirect as usual (e.g., > spec-file.md).
# If HIVE_AGENT_LOG is set, also writes output to that file.
# If HIVE_COST_LOG is set, appends token usage to CSV.
run_claude() {
  local tmpfile
  tmpfile=$(mktemp "${TMPDIR:-/tmp}/hive-claude.XXXXXX")

  while true; do
    # Run claude, capture exit code separately so we can distinguish
    # rate-limit retries from real failures.
    local exit_code=0
    claude "$@" > "$tmpfile" 2>&1 || exit_code=$?

    if is_rate_limited "$tmpfile"; then
      echo "RATE LIMIT: Pausing for ${RATE_LIMIT_WAIT}s ($(date '+%H:%M:%S'))..." >&2
      echo "Will resume at $(date -d "+${RATE_LIMIT_WAIT} seconds" '+%H:%M:%S' 2>/dev/null || echo "~$(( RATE_LIMIT_WAIT / 60 ))m from now")." >&2
      sleep "$RATE_LIMIT_WAIT"
      continue
    fi

    # Always log output and track costs, even on failure (useful for debugging)
    if [[ -n "${HIVE_AGENT_LOG:-}" ]]; then
      cp "$tmpfile" "$HIVE_AGENT_LOG"
    fi

    # Extract and log token usage if cost tracking is enabled
    if [[ -n "${HIVE_COST_LOG:-}" ]]; then
      _log_token_usage "$tmpfile"
    fi

    # Propagate real failures (non-zero exit that isn't a rate limit)
    if [[ $exit_code -ne 0 ]]; then
      echo "ERROR: claude exited with code $exit_code (log: ${HIVE_AGENT_LOG:-none})" >&2
      cat "$tmpfile" >&2
      rm -f "$tmpfile"
      return $exit_code
    fi

    # Fail on empty output (agent produced nothing)
    if [[ ! -s "$tmpfile" ]]; then
      echo "ERROR: Agent produced no output (log: ${HIVE_AGENT_LOG:-none})" >&2
      rm -f "$tmpfile"
      return 1
    fi

    cat "$tmpfile"
    rm -f "$tmpfile"
    return 0
  done
}

# --- Cost/Token Tracking ---

# Initialize cost tracking for a pipeline run.
# Sets HIVE_COST_LOG (exported so child processes inherit it).
init_cost_tracking() {
  if [[ -n "${HIVE_RUN_LOG_DIR:-}" ]]; then
    export HIVE_COST_LOG="$HIVE_RUN_LOG_DIR/cost.csv"
  fi
}

# Extract token usage from claude output and append to cost CSV.
# Looks for token usage patterns in the output. The claude CLI may include
# usage stats when run with certain flags. This function attempts to parse them.
_log_token_usage() {
  local file=$1
  [[ -n "${HIVE_COST_LOG:-}" ]] || return 0

  local agent="${HIVE_AGENT_NAME:-unknown}"
  local feature="${HIVE_FEATURE_SLUG:-unknown}"
  local model="${HIVE_AGENT_MODEL:-unknown}"
  local ts
  ts=$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')

  # Try to extract token counts from output
  # Claude CLI may output usage info in various formats
  local input_tokens="0"
  local output_tokens="0"

  # Pattern 1: JSON format (--output-format json)
  if grep -q '"input_tokens"' "$file" 2>/dev/null; then
    input_tokens=$(grep -o '"input_tokens":[0-9]*' "$file" | head -1 | grep -o '[0-9]*' || echo "0")
    output_tokens=$(grep -o '"output_tokens":[0-9]*' "$file" | head -1 | grep -o '[0-9]*' || echo "0")
  fi

  # Pattern 2: Text format (verbose output)
  if [[ "$input_tokens" == "0" ]] && grep -qiE "input tokens|tokens used" "$file" 2>/dev/null; then
    input_tokens=$(grep -oiE "input.?tokens:?\s*[0-9,]+" "$file" | head -1 | grep -o '[0-9]*' | head -1 || echo "0")
    output_tokens=$(grep -oiE "output.?tokens:?\s*[0-9,]+" "$file" | head -1 | grep -o '[0-9]*' | head -1 || echo "0")
  fi

  # Append to cost log (create with header if new)
  if [[ ! -f "$HIVE_COST_LOG" ]]; then
    echo "agent,feature,input_tokens,output_tokens,model,timestamp" > "$HIVE_COST_LOG"
  fi
  echo "$agent,$feature,$input_tokens,$output_tokens,$model,$ts" >> "$HIVE_COST_LOG"
}

# --- Custom Agent Resolution ---

# Resolve an agent name to its .md file path.
# Checks: CUSTOM_AGENTS_DIR first, then HIVE_DIR/agents/, then absolute path.
# Usage: resolve_agent <agent-name>
# Returns: path to the .md file, or exits 1 if not found.
resolve_agent() {
  local agent_name=$1
  local custom_dir="${CUSTOM_AGENTS_DIR:-${HIVE_DIR:-}/custom-agents}"

  # Check custom directory first (user overrides)
  if [[ -n "$custom_dir" ]] && [[ -f "$custom_dir/$agent_name.md" ]]; then
    echo "$custom_dir/$agent_name.md"
    return 0
  fi
  # Check built-in agents
  if [[ -f "${HIVE_DIR:-}/agents/$agent_name.md" ]]; then
    echo "${HIVE_DIR:-}/agents/$agent_name.md"
    return 0
  fi
  # Check as absolute/relative path
  if [[ -f "$agent_name" ]]; then
    echo "$agent_name"
    return 0
  fi
  # Not found
  return 1
}

# --- Notifications ---

# Send a notification via webhook (Slack or Discord).
# Usage: notify <status> <message>
# Status: "success" or "failure"
# Requires NOTIFY_WEBHOOK to be set. Does nothing if empty.
notify() {
  local status=$1
  local message=$2

  [[ -n "${NOTIFY_WEBHOOK:-}" ]] || return 0
  command -v curl >/dev/null || { echo "Warning: curl not found, skipping notification" >&2; return 0; }

  # Filter by NOTIFY_ON setting
  local notify_on="${NOTIFY_ON:-all}"
  case "$notify_on" in
    failure)    [[ "$status" != "failure" ]] && return 0 ;;
    completion) [[ "$status" != "success" ]] && return 0 ;;
    all)        ;;
  esac

  # Auto-detect provider from URL
  local provider="${NOTIFY_PROVIDER:-auto}"
  if [[ "$provider" == "auto" ]]; then
    case "$NOTIFY_WEBHOOK" in
      *hooks.slack.com*)   provider="slack" ;;
      *discord.com/api*)   provider="discord" ;;
      *)                   provider="slack" ;;
    esac
  fi

  # Format payload
  local payload
  case "$provider" in
    slack)
      local emoji
      if [[ "$status" == "success" ]]; then emoji=":white_check_mark:"; else emoji=":x:"; fi
      payload="{\"text\": \"${emoji} Claude Hive: ${message}\"}"
      ;;
    discord)
      local color
      if [[ "$status" == "success" ]]; then color="3066993"; else color="15158332"; fi
      # Escape double quotes in message for JSON
      local safe_msg="${message//\"/\\\"}"
      payload="{\"embeds\": [{\"title\": \"Claude Hive Pipeline\", \"description\": \"${safe_msg}\", \"color\": ${color}}]}"
      ;;
  esac

  # Fire and forget — never block the pipeline on notification failure
  curl -s -X POST -H "Content-Type: application/json" -d "$payload" "$NOTIFY_WEBHOOK" >/dev/null 2>&1 &
}

# --- Granular status tracking ---

# Status directory: one file per feature with key=value pairs
# Format: claude-hive/prd/status/<feature-slug>.status
# Keys: status, branch, stage_design, stage_architect, stage_implement, stage_test, stage_debug, stage_review, stage_commit, last_updated

HIVE_STATUS_DIR="${HIVE_STATUS_DIR:-${HIVE_DIR:-/tmp}/prd/status}"

# Read a key from a feature's status file
# Usage: read_feature_status <slug> <key>
read_feature_status() {
  local slug=$1 key=$2
  local file="$HIVE_STATUS_DIR/$slug.status"
  if [[ -f "$file" ]]; then
    grep "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- || true
  fi
}

# Write a key=value to a feature's status file (atomic via flock)
# Usage: write_feature_status <slug> <key> <value>
write_feature_status() {
  local slug=$1 key=$2 value=$3
  local file="$HIVE_STATUS_DIR/$slug.status"
  mkdir -p "$HIVE_STATUS_DIR"
  (
    flock -x 200
    if [[ -f "$file" ]] && grep -q "^${key}=" "$file" 2>/dev/null; then
      # Update existing key
      sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
      # Append new key
      echo "${key}=${value}" >> "$file"
    fi
    # Always update timestamp
    if [[ "$key" != "last_updated" ]]; then
      local ts
      ts=$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')
      if grep -q "^last_updated=" "$file" 2>/dev/null; then
        sed -i "s|^last_updated=.*|last_updated=${ts}|" "$file"
      else
        echo "last_updated=${ts}" >> "$file"
      fi
    fi
  ) 200>"$file.lock"
}

# Write a stage status for a feature
# Usage: write_stage_status <slug> <stage> <status>
write_stage_status() {
  local slug=$1 stage=$2 status=$3
  write_feature_status "$slug" "stage_${stage}" "$status"
  write_feature_status "$slug" "status" "$( _compute_overall_status "$slug" )"
}

# Compute overall feature status from stage statuses
_compute_overall_status() {
  local slug=$1
  local file="$HIVE_STATUS_DIR/$slug.status"
  [[ -f "$file" ]] || { echo "pending"; return; }
  if grep -q "^stage_.*=failed$" "$file" 2>/dev/null; then
    echo "failed"
  elif grep -qE "^stage_commit=complete$" "$file" 2>/dev/null; then
    echo "complete"
  elif grep -q "^stage_.*=in-progress$" "$file" 2>/dev/null; then
    echo "in-progress"
  else
    echo "in-progress"
  fi
}

# Generate status.json from per-feature status files (for backward compatibility)
generate_status_json() {
  local status_file="${1:-${HIVE_DIR:-/tmp}/prd/status.json}"
  local json="{"
  local first=true
  if [[ -d "$HIVE_STATUS_DIR" ]]; then
    for f in "$HIVE_STATUS_DIR"/*.status; do
      [[ -f "$f" ]] || continue
      local slug
      slug=$(basename "$f" .status)
      local status
      status=$(read_feature_status "$slug" "status")
      status="${status:-pending}"
      if [[ "$first" == true ]]; then
        first=false
      else
        json+=","
      fi
      json+=$'\n'"  \"${slug}\": \"${status}\""
    done
  fi
  json+=$'\n'"}"
  echo "$json" > "$status_file"
}
