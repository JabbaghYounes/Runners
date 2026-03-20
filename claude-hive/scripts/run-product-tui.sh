#!/bin/bash
# Wrapper that runs the full product pipeline with a live TUI dashboard.
# Usage: run-product-tui.sh [run-product.sh flags...]
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Record start time for TUI elapsed display
export HIVE_TUI_START=$(date +%s)

# Create a log file for pipeline output
PIPELINE_LOG=$(mktemp "${TMPDIR:-/tmp}/hive-pipeline.XXXXXX.log")

echo "Starting pipeline (log: $PIPELINE_LOG)..."

# Launch the pipeline in the background
"$HIVE_DIR/scripts/run-product.sh" "$@" > "$PIPELINE_LOG" 2>&1 &
PIPELINE_PID=$!

# Cleanup on exit — don't kill the pipeline, just inform
cleanup() {
  if kill -0 "$PIPELINE_PID" 2>/dev/null; then
    echo ""
    echo "TUI closed. Pipeline still running (PID: $PIPELINE_PID)."
    echo "Pipeline log: $PIPELINE_LOG"
    echo "Re-attach TUI: $HIVE_DIR/scripts/tui.sh 2 $PIPELINE_PID"
  else
    echo ""
    echo "Pipeline finished. Log: $PIPELINE_LOG"
    # Show exit status
    wait "$PIPELINE_PID" 2>/dev/null
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
      echo "Pipeline completed successfully."
    else
      echo "Pipeline failed (exit code: $exit_code). Check log for details."
    fi
  fi
}
trap cleanup EXIT

# Give pipeline a moment to initialize (create features dir, etc.)
sleep 3

# Launch the TUI — it will auto-exit when pipeline PID dies
"$HIVE_DIR/scripts/tui.sh" 2 "$PIPELINE_PID"
