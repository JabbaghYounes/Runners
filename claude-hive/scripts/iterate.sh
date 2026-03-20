#!/bin/bash
# Automated iteration loop: run pipeline → retrospective → evolve PRD → repeat.
# Usage: iterate.sh [--max-iterations N] [--auto-apply]
#
# By default, pauses after each iteration for the user to review the evolved PRD.
# With --auto-apply, applies the evolved PRD automatically and continues.
#
# Stops when:
#   - Max iterations reached (default: 3)
#   - Retrospective has no actionable findings (convergence)
#   - No evolved PRD was produced
#   - Pipeline fails
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$HIVE_DIR/.." && pwd)"

# Source config
CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

# Source shared functions
source "$HIVE_DIR/scripts/lib.sh"

# Defaults
MAX_ITERATIONS=3
AUTO_APPLY=false
ENABLE_INTEGRATION_TEST_AFTER=2  # enable integration tests from iteration N

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations)     MAX_ITERATIONS="$2"; shift 2 ;;
    --auto-apply)         AUTO_APPLY=true; shift ;;
    --integrate-after)    ENABLE_INTEGRATION_TEST_AFTER="$2"; shift 2 ;;
    *) break ;;
  esac
done

# Validate
if [[ ! -f "$HIVE_DIR/prd/prd.md" ]] || [[ ! -s "$HIVE_DIR/prd/prd.md" ]]; then
  echo "Error: No PRD found at claude-hive/prd/prd.md" >&2
  exit 1
fi

echo "=========================================="
echo " CLAUDE HIVE: Iteration loop"
echo " Max iterations: $MAX_ITERATIONS"
echo " Auto-apply PRD: $AUTO_APPLY"
echo "=========================================="

for iteration in $(seq 1 "$MAX_ITERATIONS"); do
  echo ""
  echo "=========================================="
  echo " Iteration $iteration / $MAX_ITERATIONS"
  echo "=========================================="

  # Build run-product.sh flags
  RUN_FLAGS=""

  # First iteration: full run. Subsequent: incremental.
  if [[ $iteration -gt 1 ]]; then
    RUN_FLAGS="--incremental"
  fi

  # Enable integration tests after N iterations
  if [[ $iteration -ge $ENABLE_INTEGRATION_TEST_AFTER ]]; then
    export ENABLE_INTEGRATION_TEST=true
  fi

  # Always enable retrospective and PRD evolution for the loop
  export ENABLE_RETROSPECTIVE=true
  export ENABLE_PRD_EVOLUTION=true

  # Run the pipeline
  if ! "$HIVE_DIR/scripts/run-product.sh" $RUN_FLAGS; then
    echo ""
    echo "ERROR: Pipeline failed on iteration $iteration." >&2
    notify "failure" "Iteration loop failed on iteration $iteration."
    exit 1
  fi

  # Check if an evolved PRD was produced
  EVOLVED_FILE="$HIVE_DIR/prd/prd-evolved.md"
  if [[ ! -s "$EVOLVED_FILE" ]]; then
    echo ""
    echo "No evolved PRD produced. Stopping iteration loop."
    break
  fi

  # Check for convergence: if retrospective has no actionable findings
  RETRO_FILE="$HIVE_DIR/prd/retrospective.md"
  if [[ -s "$RETRO_FILE" ]]; then
    # Simple heuristic: if retrospective contains no improvement recommendations
    # beyond marking things as done, we've converged
    if ! grep -qiE "should|must|missing|gap|risk|concern|recommend|improve|fix|add|update" "$RETRO_FILE" 2>/dev/null; then
      echo ""
      echo "Retrospective has no actionable findings. Pipeline has converged."
      break
    fi
  fi

  # Last iteration — don't apply, just report
  if [[ $iteration -eq $MAX_ITERATIONS ]]; then
    echo ""
    echo "Reached max iterations ($MAX_ITERATIONS)."
    if [[ -s "$EVOLVED_FILE" ]]; then
      echo "Final evolved PRD available at: $EVOLVED_FILE"
    fi
    break
  fi

  # Apply the evolved PRD
  if [[ "$AUTO_APPLY" == true ]]; then
    echo ""
    echo "Auto-applying evolved PRD for next iteration..."
    cp "$EVOLVED_FILE" "$HIVE_DIR/prd/prd.md"
  else
    echo ""
    echo "=========================================="
    echo " Iteration $iteration complete."
    echo " Retrospective: $RETRO_FILE"
    echo " Evolved PRD:   $EVOLVED_FILE"
    echo "=========================================="
    echo ""
    echo "Review the evolved PRD, then:"
    echo "  - Press ENTER to apply and continue"
    echo "  - Type 'stop' to end the loop"
    echo "  - Edit $EVOLVED_FILE before pressing ENTER to make manual adjustments"
    echo ""
    read -r -p "> " user_input
    if [[ "$user_input" == "stop" ]]; then
      echo "Stopping iteration loop."
      break
    fi
    cp "$EVOLVED_FILE" "$HIVE_DIR/prd/prd.md"
    echo "Applied evolved PRD."
  fi

  # Clean up for next iteration: remove evolved file so we can detect if a new one is produced
  rm -f "$EVOLVED_FILE"
done

echo ""
echo "=========================================="
echo " CLAUDE HIVE: Iteration loop complete"
echo " Total iterations: $iteration"
echo "=========================================="

notify "success" "Iteration loop completed after $iteration iterations."
