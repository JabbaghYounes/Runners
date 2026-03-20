#!/bin/bash
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$HIVE_DIR/.." && pwd)"

# Source config
CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

DESIGN_AGENTS="${DESIGN_AGENTS:-system-architect db-designer api-designer ux-designer}"
CLAUDE_PERMISSIONS="${CLAUDE_PERMISSIONS:---dangerously-skip-permissions}"
DESIGN_MODEL="${DESIGN_MODEL:-claude-sonnet-4-6}"
MAX_TURNS="${MAX_TURNS:-25}"
RATE_LIMIT_WAIT="${RATE_LIMIT_WAIT:-600}"
ENABLE_INTEGRATION_TEST="${ENABLE_INTEGRATION_TEST:-false}"
ENABLE_RETROSPECTIVE="${ENABLE_RETROSPECTIVE:-false}"
ENABLE_PRD_EVOLUTION="${ENABLE_PRD_EVOLUTION:-false}"

# Source shared functions (rate-limit retry, logging, etc.)
source "$HIVE_DIR/scripts/lib.sh"

# Parse flags
INCREMENTAL=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --incremental) INCREMENTAL=true; shift ;;
    *) break ;;
  esac
done

# Initialize logging and cost tracking for this pipeline run
init_run_log
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

# Validate
if [[ ! -f "$HIVE_DIR/prd/prd.md" ]] || [[ ! -s "$HIVE_DIR/prd/prd.md" ]]; then
  echo "Error: No PRD found at claude-hive/prd/prd.md" >&2
  exit 1
fi

command -v claude >/dev/null || { echo "Error: claude CLI not found" >&2; exit 1; }

echo "=========================================="
echo " CLAUDE HIVE: Full product pipeline"
echo "=========================================="

# Step 1: Extract features from PRD
echo ""
echo "--- Step 1: Extracting features from PRD ---"
if [[ "$INCREMENTAL" == true ]]; then
  "$HIVE_DIR/scripts/prd-extract.sh" --incremental
else
  "$HIVE_DIR/scripts/prd-extract.sh"
fi

# Step 2: Product-level design (runs once, not per-feature)
SKIP_DESIGN=false
if [[ "$DESIGN_AGENTS" == "none" ]]; then
  SKIP_DESIGN=true
elif [[ "$INCREMENTAL" == true ]]; then
  SPECS_DIR="$HIVE_DIR/prd/specs"
  if [[ -d "$SPECS_DIR" ]] && ls "$SPECS_DIR"/*.md >/dev/null 2>&1; then
    # Verify specs are non-empty (failed runs may leave truncated files from redirects)
    _specs_valid=true
    for _sf in "$SPECS_DIR"/*.md; do
      if [[ ! -s "$_sf" ]]; then
        echo "Removing empty spec from failed run: $_sf" >&2
        rm -f "$_sf"
        _specs_valid=false
      fi
    done
    if [[ "$_specs_valid" == true ]]; then
      SKIP_DESIGN=true
      echo ""
      echo "--- Step 2: Skipping design (specs already exist, --incremental) ---"
    fi
  fi
fi

if [[ "$SKIP_DESIGN" == false ]]; then
  echo ""
  echo "--- Step 2: Product-level design ---"
  cd "$PROJECT_ROOT"
  SPECS_DIR="$HIVE_DIR/prd/specs"
  mkdir -p "$SPECS_DIR"

  export HIVE_FEATURE_SLUG="design"

  for AGENT in $DESIGN_AGENTS; do
    if resolve_agent "$AGENT" >/dev/null 2>&1; then
      SPEC_FILE="$SPECS_DIR/$(spec_filename "$AGENT")"
      echo "Running design agent: $AGENT"

      TURNS_FLAG=""
      if [[ "$MAX_TURNS" -gt 0 ]]; then
        TURNS_FLAG="--max-turns $MAX_TURNS"
      fi

      # Set up logging and cost tracking for this agent
      local_log=$(_agent_log_path "$AGENT")
      if [[ -n "$local_log" ]]; then
        export HIVE_AGENT_LOG="$local_log"
      fi
      export HIVE_AGENT_NAME="$AGENT"
      export HIVE_AGENT_MODEL="$DESIGN_MODEL"

      AGENT_FILE=$(resolve_agent "$AGENT")
      run_claude \
        --system-prompt "$(cat "$AGENT_FILE")" \
        --print \
        $CLAUDE_PERMISSIONS \
        --model "$DESIGN_MODEL" \
        $TURNS_FLAG \
        "Design based on the PRD at $HIVE_DIR/prd/prd.md" > "$SPEC_FILE"

      unset HIVE_AGENT_LOG HIVE_AGENT_NAME HIVE_AGENT_MODEL
      echo "Wrote spec: $SPEC_FILE"
    else
      echo "Warning: agent $AGENT not found, skipping" >&2
    fi
  done
fi

# Step 3: Run per-feature swarms (design already done above)
echo ""
echo "--- Step 3: Running feature swarms ---"
"$HIVE_DIR/scripts/prd-swarm.sh"

# Step 4: Integration test pass (optional)
if [[ "$ENABLE_INTEGRATION_TEST" == "true" ]]; then
  echo ""
  echo "--- Step 4: Integration test pass ---"
  "$HIVE_DIR/scripts/integration-test.sh" || {
    echo "WARNING: Integration tests failed. Feature PRs were still created." >&2
    notify "failure" "Pipeline completed but integration tests failed."
  }
fi

# Step 5: Retrospective (optional)
if [[ "${ENABLE_RETROSPECTIVE}" == "true" ]]; then
  echo ""
  echo "--- Step 5: Retrospective analysis ---"
  export HIVE_FEATURE_SLUG="retrospective"

  TURNS_FLAG=""
  if [[ "$MAX_TURNS" -gt 0 ]]; then
    TURNS_FLAG="--max-turns $MAX_TURNS"
  fi

  local_log=$(_agent_log_path "retrospective")
  if [[ -n "$local_log" ]]; then
    export HIVE_AGENT_LOG="$local_log"
  fi
  export HIVE_AGENT_NAME="retrospective"
  export HIVE_AGENT_MODEL="$DESIGN_MODEL"

  AGENT_FILE=$(resolve_agent "retrospective")
  RETRO_FILE="$HIVE_DIR/prd/retrospective.md"

  run_claude \
    --system-prompt "$(cat "$AGENT_FILE")" \
    --print \
    $CLAUDE_PERMISSIONS \
    --model "$DESIGN_MODEL" \
    $TURNS_FLAG \
    "Analyze the completed pipeline run. Read the PRD at $HIVE_DIR/prd/prd.md, specs in $HIVE_DIR/prd/specs/, and feature files in $HIVE_DIR/prd/features/. Use git log and git diff to examine feature branches." > "$RETRO_FILE" || {
    echo "WARNING: Retrospective agent failed. Continuing." >&2
    rm -f "$RETRO_FILE"
  }

  unset HIVE_AGENT_LOG HIVE_AGENT_NAME HIVE_AGENT_MODEL

  if [[ -s "$RETRO_FILE" ]]; then
    echo "Wrote retrospective: $RETRO_FILE"
  fi
fi

# Step 6: PRD Evolution (optional, requires retrospective)
if [[ "${ENABLE_PRD_EVOLUTION}" == "true" ]]; then
  RETRO_FILE="$HIVE_DIR/prd/retrospective.md"
  if [[ ! -s "$RETRO_FILE" ]]; then
    echo "WARNING: Skipping PRD evolution — no retrospective report found." >&2
    echo "Set ENABLE_RETROSPECTIVE=true to generate one." >&2
  else
    echo ""
    echo "--- Step 6: PRD evolution ---"
    export HIVE_FEATURE_SLUG="prd-evolution"

    TURNS_FLAG=""
    if [[ "$MAX_TURNS" -gt 0 ]]; then
      TURNS_FLAG="--max-turns $MAX_TURNS"
    fi

    local_log=$(_agent_log_path "prd-evolver")
    if [[ -n "$local_log" ]]; then
      export HIVE_AGENT_LOG="$local_log"
    fi
    export HIVE_AGENT_NAME="prd-evolver"
    export HIVE_AGENT_MODEL="$DESIGN_MODEL"

    AGENT_FILE=$(resolve_agent "prd-evolver")
    EVOLVED_FILE="$HIVE_DIR/prd/prd-evolved.md"

    # Back up current PRD
    cp "$HIVE_DIR/prd/prd.md" "$HIVE_DIR/prd/prd.md.bak"

    run_claude \
      --system-prompt "$(cat "$AGENT_FILE")" \
      --print \
      $CLAUDE_PERMISSIONS \
      --model "$DESIGN_MODEL" \
      $TURNS_FLAG \
      "Evolve the PRD. Read the current PRD at $HIVE_DIR/prd/prd.md, the retrospective at $HIVE_DIR/prd/retrospective.md, and feature files in $HIVE_DIR/prd/features/." > "$EVOLVED_FILE" || {
      echo "WARNING: PRD evolution agent failed. Continuing." >&2
      rm -f "$EVOLVED_FILE"
    }

    unset HIVE_AGENT_LOG HIVE_AGENT_NAME HIVE_AGENT_MODEL

    if [[ -s "$EVOLVED_FILE" ]]; then
      echo "Wrote evolved PRD: $EVOLVED_FILE"
      echo "Previous PRD backed up to: $HIVE_DIR/prd/prd.md.bak"
      echo "To apply: cp $HIVE_DIR/prd/prd-evolved.md $HIVE_DIR/prd/prd.md"
    fi
  fi
fi

echo ""
echo "=========================================="
echo " CLAUDE HIVE: Pipeline complete"
echo " Logs: ${HIVE_RUN_LOG_DIR:-N/A}"
echo "=========================================="

# Print cost report if cost data exists
if [[ -f "${HIVE_COST_LOG:-}" ]]; then
  echo ""
  "$HIVE_DIR/scripts/cost-report.sh" "$HIVE_COST_LOG"
fi

notify "success" "Full product pipeline completed successfully."
