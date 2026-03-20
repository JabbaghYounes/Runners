#!/bin/bash
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$HIVE_DIR/.." && pwd)"

# Source config
CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

# Defaults
TEST_CMD="${TEST_CMD:-npm test}"
BASE_BRANCH="${BASE_BRANCH:-main}"
MAX_RETRIES="${MAX_RETRIES:-3}"
DESIGN_AGENTS="${DESIGN_AGENTS:-system-architect db-designer api-designer ux-designer}"
IMPL_AGENTS="${IMPL_AGENTS:-backend frontend}"
CLAUDE_PERMISSIONS="${CLAUDE_PERMISSIONS:---dangerously-skip-permissions}"
DESIGN_MODEL="${DESIGN_MODEL:-claude-sonnet-4-6}"
IMPL_MODEL="${IMPL_MODEL:-claude-sonnet-4-6}"
MAX_TURNS="${MAX_TURNS:-25}"
RATE_LIMIT_WAIT="${RATE_LIMIT_WAIT:-600}"
ENABLE_REVIEW="${ENABLE_REVIEW:-false}"
POLISH_PASSES="${POLISH_PASSES:-0}"

# Source shared functions (rate-limit retry, logging, status tracking)
source "$HIVE_DIR/scripts/lib.sh"

# Parse flags
SKIP_DESIGN=false
FEATURE_SLUG=""
OVERRIDE_BRANCH=""
OVERRIDE_PROJECT_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-design)      SKIP_DESIGN=true; shift ;;
    --feature-slug)     FEATURE_SLUG="$2"; shift 2 ;;
    --branch)           OVERRIDE_BRANCH="$2"; shift 2 ;;
    --project-root)     OVERRIDE_PROJECT_ROOT="$2"; shift 2 ;;
    *)                  break ;;
  esac
done

TASK="${1:-}"

# Validate
if [[ -z "$TASK" ]]; then
  echo "Usage: swarm.sh [--skip-design] [--feature-slug <slug>] [--branch <name>] [--project-root <dir>] <task description>" >&2
  exit 1
fi

command -v claude >/dev/null || { echo "Error: claude CLI not found" >&2; exit 1; }

# Override project root if specified (for worktree-based parallel execution)
if [[ -n "$OVERRIDE_PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$OVERRIDE_PROJECT_ROOT"
fi

cd "$PROJECT_ROOT"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Error: not a git repo" >&2; exit 1; }

# Export feature slug for logging
export HIVE_FEATURE_SLUG="${FEATURE_SLUG:-standalone}"

# Initialize logging for this run (if not already set by parent)
if [[ -z "${HIVE_RUN_LOG_DIR:-}" ]]; then
  init_run_log
fi

# Initialize cost tracking
init_cost_tracking

# Map design agent names to spec filenames
spec_filename() {
  case "$1" in
    system-architect) echo "architecture.md" ;;
    db-designer)      echo "db-schema.md" ;;
    api-designer)     echo "api-spec.md" ;;
    ux-designer)      echo "ux-spec.md" ;;
    *)                echo "$1.md" ;;
  esac
}

# Build claude flags for a given model
claude_flags() {
  local model=$1
  local flags="--print $CLAUDE_PERMISSIONS --model $model"
  if [[ "$MAX_TURNS" -gt 0 ]]; then
    flags="$flags --max-turns $MAX_TURNS"
  fi
  echo "$flags"
}

run_agent() {
  local AGENT=$1
  local PROMPT=$2
  local MODEL=${3:-$IMPL_MODEL}

  # Resolve agent file (supports custom agents)
  local AGENT_FILE
  AGENT_FILE=$(resolve_agent "$AGENT") || {
    echo "Warning: agent $AGENT not found, skipping" >&2
    return 1
  }

  echo "--- Running agent: $AGENT (model: $MODEL) ---" >&2

  # Set up logging
  local log_file
  log_file=$(_agent_log_path "$AGENT")
  if [[ -n "$log_file" ]]; then
    export HIVE_AGENT_LOG="$log_file"
  fi

  # Set up cost tracking metadata
  export HIVE_AGENT_NAME="$AGENT"
  export HIVE_AGENT_MODEL="$MODEL"

  run_claude \
    --system-prompt "$(cat "$AGENT_FILE")" \
    $(claude_flags "$MODEL") \
    "$PROMPT"

  unset HIVE_AGENT_LOG HIVE_AGENT_NAME HIVE_AGENT_MODEL
}

# Create or reuse feature branch
if [[ -n "$OVERRIDE_BRANCH" ]]; then
  BRANCH="$OVERRIDE_BRANCH"
  # If branch exists, check it out; otherwise create it
  if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    git checkout "$BRANCH"
  else
    git checkout -b "$BRANCH" "$BASE_BRANCH"
  fi
else
  BRANCH="ai-feature-$(date +%s)"
  git checkout -b "$BRANCH" "$BASE_BRANCH"
fi

# Record branch in status
if [[ -n "$FEATURE_SLUG" ]]; then
  write_feature_status "$FEATURE_SLUG" "branch" "$BRANCH"
fi

# Temp file for test output
TEST_OUTPUT_FILE=$(mktemp "${TMPDIR:-/tmp}/hive-test-output.XXXXXX")

# Cleanup on exit
cleanup() {
  local exit_code=$?
  rm -f "$TEST_OUTPUT_FILE"
  if [[ $exit_code -ne 0 ]]; then
    echo "Swarm failed on branch '$BRANCH'." >&2
    echo "To return to base branch: git checkout $BASE_BRANCH" >&2
  fi
}
trap cleanup EXIT

# --- Stage functions ---

run_stage_design() {
  if [[ "$SKIP_DESIGN" == true ]]; then
    echo "=== Skipping design (--skip-design) ==="
    return 0
  fi
  if [[ "$DESIGN_AGENTS" == "none" ]]; then
    echo "=== Skipping design (DESIGN_AGENTS=none) ==="
    return 0
  fi

  SPECS_DIR="$HIVE_DIR/prd/specs"
  mkdir -p "$SPECS_DIR"

  echo "=== Design phase ==="
  for AGENT in $DESIGN_AGENTS; do
    if resolve_agent "$AGENT" >/dev/null 2>&1; then
      SPEC_FILE="$SPECS_DIR/$(spec_filename "$AGENT")"
      run_agent "$AGENT" "Design for: $TASK" "$DESIGN_MODEL" > "$SPEC_FILE" || return 1
      echo "Wrote spec: $SPEC_FILE"
    else
      echo "Warning: agent $AGENT not found, skipping" >&2
    fi
  done
}

run_stage_architect() {
  # Warn if specs are missing when design was skipped
  if [[ "$SKIP_DESIGN" == true ]]; then
    SPECS_DIR="$HIVE_DIR/prd/specs"
    if [[ ! -d "$SPECS_DIR" ]] || ! ls "$SPECS_DIR"/*.md >/dev/null 2>&1; then
      echo "WARNING: --skip-design was passed but no spec files found in $SPECS_DIR/." >&2
      echo "Downstream agents will proceed without design specs." >&2
    fi
  fi

  echo "=== Architecture & Planning phase ==="
  SPECS_DIR="$HIVE_DIR/prd/specs"
  mkdir -p "$SPECS_DIR"
  FEATURE_PLAN_FILE="$SPECS_DIR/feature-plan.md"
  run_agent architect "$TASK" "$DESIGN_MODEL" > "$FEATURE_PLAN_FILE" || return 1
  echo "Wrote feature plan: $FEATURE_PLAN_FILE"
}

run_stage_implement() {
  # Build context from architect output
  FEATURE_PLAN_FILE="$HIVE_DIR/prd/specs/feature-plan.md"
  local plan_context=""
  if [[ -f "$FEATURE_PLAN_FILE" ]]; then
    plan_context=$(cat "$FEATURE_PLAN_FILE")
  fi

  local impl_prompt="Implement this feature: $TASK

## Feature Architecture & Plan
$plan_context"

  echo "=== Implementation phase ==="
  IMPL_PIDS=()
  for AGENT in $IMPL_AGENTS; do
    if resolve_agent "$AGENT" >/dev/null 2>&1; then
      run_agent "$AGENT" "$impl_prompt" "$IMPL_MODEL" &
      IMPL_PIDS+=($!)
    else
      echo "Warning: agent $AGENT not found, skipping" >&2
    fi
  done

  local impl_fail=0
  for PID in "${IMPL_PIDS[@]}"; do
    wait "$PID" || impl_fail=1
  done
  if [[ $impl_fail -ne 0 ]]; then
    echo "ERROR: Implementation agents failed." >&2
    return 1
  fi
}

run_stage_test() {
  FEATURE_PLAN_FILE="$HIVE_DIR/prd/specs/feature-plan.md"
  local plan_context=""
  if [[ -f "$FEATURE_PLAN_FILE" ]]; then
    plan_context=$(cat "$FEATURE_PLAN_FILE")
  fi

  echo "=== Test phase ==="
  local tester_prompt="Write tests for this feature: $TASK

## Feature Architecture & Plan
$plan_context"
  run_agent tester "$tester_prompt" "$IMPL_MODEL" || return 1
}

run_stage_debug() {
  echo "=== Running tests ==="
  local retry=0
  while true; do
    if $TEST_CMD > "$TEST_OUTPUT_FILE" 2>&1; then
      echo "Tests passed."
      return 0
    fi

    retry=$((retry + 1))
    if [[ $retry -ge $MAX_RETRIES ]]; then
      echo "ERROR: Tests still failing after $MAX_RETRIES retries. Aborting." >&2
      cat "$TEST_OUTPUT_FILE" >&2
      return 1
    fi

    echo "Tests failed (attempt $retry/$MAX_RETRIES). Running debugger..."
    local test_output
    test_output=$(cat "$TEST_OUTPUT_FILE")
    run_agent debugger "Fix failing tests. Attempt $retry of $MAX_RETRIES.

## Test Command
$TEST_CMD

## Test Output
$test_output" "$IMPL_MODEL" || echo "WARNING: Debugger agent failed, will retry test loop" >&2
  done
}

run_stage_polish() {
  if [[ "$POLISH_PASSES" -le 0 ]]; then
    echo "=== Skipping polish (POLISH_PASSES=0) ==="
    return 0
  fi

  echo "=== Polish phase ($POLISH_PASSES passes) ==="

  # Resume: check how many passes already completed
  local completed_passes=0
  if [[ -n "$FEATURE_SLUG" ]]; then
    completed_passes=$(read_feature_status "$FEATURE_SLUG" "polish_pass_completed")
    completed_passes="${completed_passes:-0}"
  fi

  FEATURE_PLAN_FILE="$HIVE_DIR/prd/specs/feature-plan.md"
  local plan_context=""
  if [[ -f "$FEATURE_PLAN_FILE" ]]; then
    plan_context=$(cat "$FEATURE_PLAN_FILE")
  fi

  for pass in $(seq $((completed_passes + 1)) "$POLISH_PASSES"); do
    echo "--- Polish pass $pass/$POLISH_PASSES ---"

    run_agent polisher "Polish pass $pass of $POLISH_PASSES for: $TASK

## Feature Architecture & Plan
$plan_context

## Instructions
This is polish pass $pass. Focus on pass $pass priorities as described in your system prompt." "$IMPL_MODEL" || return 1

    # Verify tests still pass after polishing
    echo "--- Running tests after polish pass $pass ---"
    local retry=0
    while true; do
      if $TEST_CMD > "$TEST_OUTPUT_FILE" 2>&1; then
        echo "Tests passed after polish pass $pass."
        break
      fi

      retry=$((retry + 1))
      if [[ $retry -ge $MAX_RETRIES ]]; then
        echo "ERROR: Tests failing after polish pass $pass, aborting." >&2
        cat "$TEST_OUTPUT_FILE" >&2
        return 1
      fi

      echo "Tests failed after polish (attempt $retry/$MAX_RETRIES). Running debugger..."
      local test_output
      test_output=$(cat "$TEST_OUTPUT_FILE")
      run_agent debugger "Fix failing tests after polish pass $pass.

## Test Command
$TEST_CMD

## Test Output
$test_output" "$IMPL_MODEL" || echo "WARNING: Debugger agent failed, will retry test loop" >&2
    done

    # Track per-pass progress for resume
    if [[ -n "$FEATURE_SLUG" ]]; then
      write_feature_status "$FEATURE_SLUG" "polish_pass_completed" "$pass"
    fi
  done
}

run_stage_review() {
  if [[ "${ENABLE_REVIEW}" != "true" ]]; then
    echo "=== Skipping review (ENABLE_REVIEW!=true) ==="
    return 0
  fi

  echo "=== Review phase ==="
  FEATURE_PLAN_FILE="$HIVE_DIR/prd/specs/feature-plan.md"
  local plan_context=""
  if [[ -f "$FEATURE_PLAN_FILE" ]]; then
    plan_context=$(cat "$FEATURE_PLAN_FILE")
  fi

  local review_output
  review_output=$(run_agent reviewer "Review the changes for: $TASK

## Feature Plan
$plan_context

## Branch
$BRANCH" "$DESIGN_MODEL") || return 1

  if echo "$review_output" | grep -q "NEEDS_CHANGES"; then
    echo "Reviewer requested changes. Changes have been applied." >&2
  else
    echo "Review passed." >&2
  fi
}

run_stage_commit() {
  echo "=== Commit phase ==="
  run_agent versioncontroller "Commit and create a PR for: $TASK

## Git Context
- Current branch: $BRANCH
- Base branch: $BASE_BRANCH
- Push this branch to origin before creating the PR
- Create the PR against $BASE_BRANCH using: gh pr create --base $BASE_BRANCH" "$DESIGN_MODEL" || return 1
}

# --- Stage orchestration with granular resume ---

STAGES=(design architect implement test debug polish review commit)

for STAGE in "${STAGES[@]}"; do
  # Check if this stage is already complete (resume support)
  if [[ -n "$FEATURE_SLUG" ]]; then
    stage_status=$(read_feature_status "$FEATURE_SLUG" "stage_${STAGE}")
    if [[ "$stage_status" == "complete" || "$stage_status" == "skipped" ]]; then
      echo "=== Skipping $STAGE (already $stage_status) ==="
      continue
    fi
  fi

  # Mark stage as in-progress
  if [[ -n "$FEATURE_SLUG" ]]; then
    write_stage_status "$FEATURE_SLUG" "$STAGE" "in-progress"
  fi

  # Run the stage
  if "run_stage_${STAGE}"; then
    # Determine if it was skipped or completed
    STAGE_RESULT="complete"
    if [[ "$STAGE" == "design" ]] && [[ "$SKIP_DESIGN" == true || "$DESIGN_AGENTS" == "none" ]]; then
      STAGE_RESULT="skipped"
    fi
    if [[ "$STAGE" == "polish" ]] && [[ "$POLISH_PASSES" -le 0 ]]; then
      STAGE_RESULT="skipped"
    fi
    if [[ "$STAGE" == "review" ]] && [[ "${ENABLE_REVIEW}" != "true" ]]; then
      STAGE_RESULT="skipped"
    fi
    if [[ -n "$FEATURE_SLUG" ]]; then
      write_stage_status "$FEATURE_SLUG" "$STAGE" "$STAGE_RESULT"
    fi
  else
    # Stage failed
    if [[ -n "$FEATURE_SLUG" ]]; then
      write_stage_status "$FEATURE_SLUG" "$STAGE" "failed"
    fi
    exit 1
  fi
done

echo "=== Swarm complete ==="
