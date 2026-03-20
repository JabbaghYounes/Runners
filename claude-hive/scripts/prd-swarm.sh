#!/bin/bash
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$HIVE_DIR/.." && pwd)"
FEATURES_DIR="$HIVE_DIR/prd/features"
STATUS_FILE="$HIVE_DIR/prd/status.json"

# Source config
CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

RATE_LIMIT_WAIT="${RATE_LIMIT_WAIT:-600}"
MAX_PARALLEL="${MAX_PARALLEL:-1}"
BASE_BRANCH="${BASE_BRANCH:-main}"

# Source shared functions
source "$HIVE_DIR/scripts/lib.sh"

# Initialize logging (exported so child swarm.sh processes inherit it)
init_run_log

if ! ls "$FEATURES_DIR"/*.md >/dev/null 2>&1; then
  echo "Error: No feature files found in $FEATURES_DIR/. Run prd-extract.sh first." >&2
  exit 1
fi

# Collect feature names
ALL_FEATURE_NAMES=()
for FEATURE in "$FEATURES_DIR"/*.md; do
  [[ "$(basename "$FEATURE")" == "dependencies.txt" ]] && continue
  FNAME="$(basename "$FEATURE" .md)"
  ALL_FEATURE_NAMES+=("$FNAME")
done

# Sort by dependency order if dependencies.txt exists
DEPS_FILE="$FEATURES_DIR/dependencies.txt"
FEATURE_NAMES=()

if [[ -f "$DEPS_FILE" ]] && [[ -s "$DEPS_FILE" ]] && command -v tsort >/dev/null 2>&1; then
  echo "Sorting features by dependency order..."
  # Build input for tsort: include self-edges for features with no deps
  TSORT_INPUT=$(mktemp "${TMPDIR:-/tmp}/hive-tsort.XXXXXX")
  cp "$DEPS_FILE" "$TSORT_INPUT"
  for FNAME in "${ALL_FEATURE_NAMES[@]}"; do
    if ! grep -q "$FNAME" "$TSORT_INPUT" 2>/dev/null; then
      echo "$FNAME $FNAME" >> "$TSORT_INPUT"
    fi
  done

  SORTED=$(tsort < "$TSORT_INPUT" 2>&1) || {
    echo "WARNING: Circular dependency detected. Falling back to filesystem order." >&2
    echo "$SORTED" >&2
    SORTED=""
  }
  rm -f "$TSORT_INPUT"

  if [[ -n "$SORTED" ]]; then
    # tsort output is one name per line in dependency order
    while IFS= read -r FNAME; do
      # Only include names that are actual feature files
      if [[ -f "$FEATURES_DIR/$FNAME.md" ]]; then
        FEATURE_NAMES+=("$FNAME")
      fi
    done <<< "$SORTED"
    echo "Feature order: ${FEATURE_NAMES[*]}"
  fi
fi

# Fallback to filesystem order if sorting didn't produce results
if [[ ${#FEATURE_NAMES[@]} -eq 0 ]]; then
  FEATURE_NAMES=("${ALL_FEATURE_NAMES[@]}")
fi

# Generate initial status.json for backward compatibility
generate_status_json "$STATUS_FILE"

HAS_FAILURE=false

if [[ "$MAX_PARALLEL" -le 1 ]]; then
  # --- Sequential execution (original behavior) ---
  for FNAME in "${FEATURE_NAMES[@]}"; do
    FEATURE="$FEATURES_DIR/$FNAME.md"

    # Skip features already completed in a previous run
    local_status=$(read_feature_status "$FNAME" "status")
    if [[ "$local_status" == "complete" ]]; then
      echo "=== Skipping (already complete): $FNAME ==="
      continue
    fi

    echo "=== Running swarm for: $FNAME ==="
    export HIVE_FEATURE_SLUG="$FNAME"

    # Check if there's a branch to resume
    existing_branch=$(read_feature_status "$FNAME" "branch")
    BRANCH_FLAG=""
    if [[ -n "$existing_branch" ]]; then
      BRANCH_FLAG="--branch $existing_branch"
    fi

    if "$HIVE_DIR/scripts/swarm.sh" --skip-design --feature-slug "$FNAME" $BRANCH_FLAG "$(cat "$FEATURE")"; then
      echo "=== Completed: $FNAME ==="
      notify "success" "Feature '$FNAME' completed successfully."
    else
      HAS_FAILURE=true
      echo "=== Failed: $FNAME ===" >&2
      notify "failure" "Feature '$FNAME' failed."
    fi
    generate_status_json "$STATUS_FILE"
  done
else
  # --- Parallel execution with git worktrees ---
  RUNNING_PIDS=()
  RUNNING_FEATURES=()
  RUNNING_WORKTREES=()

  # Wait for one running process to finish and clean up its worktree
  wait_for_one() {
    if [[ ${#RUNNING_PIDS[@]} -eq 0 ]]; then
      return
    fi

    # Wait for any child to finish (bash 4.3+)
    local finished_pid=0
    local finished_idx=-1

    # Use wait -n if available (bash 4.3+), otherwise poll
    if wait -n "${RUNNING_PIDS[@]}" 2>/dev/null; then
      # Find which PID finished
      for idx in "${!RUNNING_PIDS[@]}"; do
        if ! kill -0 "${RUNNING_PIDS[$idx]}" 2>/dev/null; then
          finished_idx=$idx
          break
        fi
      done
    else
      # wait -n returned non-zero — find the failed PID
      for idx in "${!RUNNING_PIDS[@]}"; do
        if ! kill -0 "${RUNNING_PIDS[$idx]}" 2>/dev/null; then
          finished_idx=$idx
          break
        fi
      done
    fi

    if [[ $finished_idx -ge 0 ]]; then
      local fname="${RUNNING_FEATURES[$finished_idx]}"
      local worktree="${RUNNING_WORKTREES[$finished_idx]}"
      local feat_status
      feat_status=$(read_feature_status "$fname" "status")

      if [[ "$feat_status" == "complete" ]]; then
        echo "=== Completed: $fname ==="
        notify "success" "Feature '$fname' completed successfully."
      else
        HAS_FAILURE=true
        echo "=== Failed: $fname ===" >&2
        notify "failure" "Feature '$fname' failed."
      fi

      # Cleanup worktree
      if [[ -n "$worktree" && -d "$worktree" ]]; then
        git -C "$PROJECT_ROOT" worktree remove "$worktree" --force 2>/dev/null || true
      fi

      # Remove from arrays
      unset "RUNNING_PIDS[$finished_idx]"
      unset "RUNNING_FEATURES[$finished_idx]"
      unset "RUNNING_WORKTREES[$finished_idx]"
      # Re-index arrays
      RUNNING_PIDS=("${RUNNING_PIDS[@]}")
      RUNNING_FEATURES=("${RUNNING_FEATURES[@]}")
      RUNNING_WORKTREES=("${RUNNING_WORKTREES[@]}")

      generate_status_json "$STATUS_FILE"
    fi
  }

  # Cleanup all worktrees on exit
  cleanup_worktrees() {
    for wt in "${RUNNING_WORKTREES[@]}"; do
      if [[ -n "$wt" && -d "$wt" ]]; then
        git -C "$PROJECT_ROOT" worktree remove "$wt" --force 2>/dev/null || true
      fi
    done
    git -C "$PROJECT_ROOT" worktree prune 2>/dev/null || true
  }
  trap cleanup_worktrees EXIT

  WORKTREE_BASE="$PROJECT_ROOT/.claude-hive-worktrees"
  mkdir -p "$WORKTREE_BASE"

  for FNAME in "${FEATURE_NAMES[@]}"; do
    FEATURE="$FEATURES_DIR/$FNAME.md"

    # Skip completed features
    local_status=$(read_feature_status "$FNAME" "status")
    if [[ "$local_status" == "complete" ]]; then
      echo "=== Skipping (already complete): $FNAME ==="
      continue
    fi

    # Wait if at MAX_PARALLEL
    while [[ ${#RUNNING_PIDS[@]} -ge $MAX_PARALLEL ]]; do
      wait_for_one
    done

    # Create worktree with unique branch
    local branch_name="ai-feature-${FNAME}-$(date +%s%N)"
    local worktree_path="$WORKTREE_BASE/$FNAME"

    # Remove stale worktree if it exists
    if [[ -d "$worktree_path" ]]; then
      git -C "$PROJECT_ROOT" worktree remove "$worktree_path" --force 2>/dev/null || true
    fi

    git -C "$PROJECT_ROOT" worktree add "$worktree_path" -b "$branch_name" "$BASE_BRANCH" 2>/dev/null

    echo "=== Launching parallel swarm for: $FNAME ==="

    # Launch swarm in background
    (
      export HIVE_FEATURE_SLUG="$FNAME"
      "$HIVE_DIR/scripts/swarm.sh" \
        --skip-design \
        --feature-slug "$FNAME" \
        --branch "$branch_name" \
        --project-root "$worktree_path" \
        "$(cat "$FEATURE")"
    ) &

    RUNNING_PIDS+=($!)
    RUNNING_FEATURES+=("$FNAME")
    RUNNING_WORKTREES+=("$worktree_path")
  done

  # Wait for all remaining
  while [[ ${#RUNNING_PIDS[@]} -gt 0 ]]; do
    wait_for_one
  done
fi

# Final status
generate_status_json "$STATUS_FILE"

if [[ "$HAS_FAILURE" == true ]]; then
  echo "ERROR: One or more features failed. See $STATUS_FILE for details." >&2
  notify "failure" "Pipeline completed with failures. See status.json for details."
  exit 1
else
  notify "success" "All features completed successfully."
fi
