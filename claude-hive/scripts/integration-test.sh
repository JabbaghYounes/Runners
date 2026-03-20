#!/bin/bash
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$HIVE_DIR/.." && pwd)"

# Source config
CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

TEST_CMD="${TEST_CMD:-npm test}"
BASE_BRANCH="${BASE_BRANCH:-main}"
MAX_RETRIES="${MAX_RETRIES:-3}"
CLAUDE_PERMISSIONS="${CLAUDE_PERMISSIONS:---dangerously-skip-permissions}"
IMPL_MODEL="${IMPL_MODEL:-claude-sonnet-4-6}"
MAX_TURNS="${MAX_TURNS:-25}"
RATE_LIMIT_WAIT="${RATE_LIMIT_WAIT:-600}"

# Source shared functions
source "$HIVE_DIR/scripts/lib.sh"

cd "$PROJECT_ROOT"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Error: not a git repo" >&2; exit 1; }

echo "=========================================="
echo " CLAUDE HIVE: Integration Test Pass"
echo "=========================================="

# Initialize logging
export HIVE_FEATURE_SLUG="integration"
if [[ -z "${HIVE_RUN_LOG_DIR:-}" ]]; then
  init_run_log
fi
init_cost_tracking

# Collect completed feature branches from status files
HIVE_STATUS_DIR="${HIVE_STATUS_DIR:-$HIVE_DIR/prd/status}"
BRANCHES=()
BRANCH_FEATURES=()

if [[ -d "$HIVE_STATUS_DIR" ]]; then
  for f in "$HIVE_STATUS_DIR"/*.status; do
    [[ -f "$f" ]] || continue
    slug=$(basename "$f" .status)
    status=$(read_feature_status "$slug" "status")
    branch=$(read_feature_status "$slug" "branch")
    if [[ "$status" == "complete" ]] && [[ -n "$branch" ]]; then
      # Verify branch exists (local or remote)
      if git show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null || \
         git show-ref --verify --quiet "refs/remotes/origin/$branch" 2>/dev/null; then
        BRANCHES+=("$branch")
        BRANCH_FEATURES+=("$slug")
        echo "  Including: $slug ($branch)"
      else
        echo "  Skipping: $slug (branch $branch not found)" >&2
      fi
    fi
  done
fi

if [[ ${#BRANCHES[@]} -lt 2 ]]; then
  echo ""
  echo "Need at least 2 completed feature branches for integration testing."
  echo "Found ${#BRANCHES[@]} branch(es). Skipping."
  exit 0
fi

# Create integration branch
INTEGRATION_BRANCH="ai-integration-$(date +%s)"
git checkout -b "$INTEGRATION_BRANCH" "$BASE_BRANCH"

echo ""
echo "--- Merging ${#BRANCHES[@]} feature branches ---"

MERGE_FAILED=false
MERGED_BRANCHES=()

for i in "${!BRANCHES[@]}"; do
  BRANCH="${BRANCHES[$i]}"
  FEAT="${BRANCH_FEATURES[$i]}"
  echo "Merging: $FEAT ($BRANCH)"
  if git merge "$BRANCH" --no-edit 2>&1; then
    MERGED_BRANCHES+=("$BRANCH")
  else
    echo "WARNING: Merge conflict with $FEAT ($BRANCH)" >&2
    MERGE_FAILED=true
    git merge --abort 2>/dev/null || true
    echo "Skipping $FEAT due to merge conflict." >&2
  fi
done

if [[ ${#MERGED_BRANCHES[@]} -lt 2 ]]; then
  echo "ERROR: Could not merge enough branches. Need at least 2." >&2
  git checkout "$BASE_BRANCH"
  git branch -D "$INTEGRATION_BRANCH" 2>/dev/null || true
  exit 1
fi

if [[ "$MERGE_FAILED" == true ]]; then
  echo ""
  echo "WARNING: Some branches had merge conflicts and were skipped." >&2
fi

# Run tests
echo ""
echo "--- Running integration tests ---"
TEST_OUTPUT_FILE=$(mktemp "${TMPDIR:-/tmp}/hive-integration-test.XXXXXX")

cleanup() {
  rm -f "$TEST_OUTPUT_FILE"
}
trap cleanup EXIT

retry=0
while true; do
  if $TEST_CMD > "$TEST_OUTPUT_FILE" 2>&1; then
    echo "Integration tests passed!"
    break
  fi

  retry=$((retry + 1))
  if [[ $retry -gt $MAX_RETRIES ]]; then
    echo "ERROR: Integration tests still failing after $MAX_RETRIES retries." >&2
    cat "$TEST_OUTPUT_FILE" >&2
    echo ""
    echo "Integration branch preserved: $INTEGRATION_BRANCH"
    echo "Inspect manually: git checkout $INTEGRATION_BRANCH"
    git checkout "$BASE_BRANCH"
    notify "failure" "Integration tests failed after $MAX_RETRIES retries."
    exit 1
  fi

  echo "Integration tests failed (attempt $retry/$MAX_RETRIES). Running integration-tester..."

  test_output=$(cat "$TEST_OUTPUT_FILE")

  # Set up logging
  local_log=$(_agent_log_path "integration-tester")
  if [[ -n "$local_log" ]]; then
    export HIVE_AGENT_LOG="$local_log"
  fi
  export HIVE_AGENT_NAME="integration-tester"
  export HIVE_AGENT_MODEL="$IMPL_MODEL"

  AGENT_FILE=$(resolve_agent "integration-tester") || {
    echo "ERROR: integration-tester agent not found" >&2
    git checkout "$BASE_BRANCH"
    exit 1
  }

  TURNS_FLAG=""
  if [[ "$MAX_TURNS" -gt 0 ]]; then
    TURNS_FLAG="--max-turns $MAX_TURNS"
  fi

  run_claude \
    --system-prompt "$(cat "$AGENT_FILE")" \
    --print \
    $CLAUDE_PERMISSIONS \
    --model "$IMPL_MODEL" \
    $TURNS_FLAG \
    "Fix integration test failures.

## Test Command
$TEST_CMD

## Test Output
$test_output

## Merged Branches
${MERGED_BRANCHES[*]}"

  unset HIVE_AGENT_LOG HIVE_AGENT_NAME HIVE_AGENT_MODEL
done

echo ""
echo "=========================================="
echo " Integration Test Pass: SUCCESS"
echo " Branch: $INTEGRATION_BRANCH"
echo " Merged: ${#MERGED_BRANCHES[@]} feature branches"
echo "=========================================="

git checkout "$BASE_BRANCH"
notify "success" "Integration tests passed. Branch: $INTEGRATION_BRANCH"
