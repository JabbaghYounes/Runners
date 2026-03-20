#!/bin/bash
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$HIVE_DIR/.." && pwd)"

# Source config
CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

PRD="$HIVE_DIR/prd/prd.md"
FEATURES_DIR="$HIVE_DIR/prd/features"

CLAUDE_PERMISSIONS="${CLAUDE_PERMISSIONS:---dangerously-skip-permissions}"
DESIGN_MODEL="${DESIGN_MODEL:-claude-sonnet-4-6}"
MAX_TURNS="${MAX_TURNS:-25}"
RATE_LIMIT_WAIT="${RATE_LIMIT_WAIT:-600}"

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

# Validate
if [[ ! -f "$PRD" ]] || [[ ! -s "$PRD" ]]; then
  echo "Error: PRD not found or empty at $PRD" >&2
  exit 1
fi

command -v claude >/dev/null || { echo "Error: claude CLI not found" >&2; exit 1; }

# Collect existing features (for incremental mode)
EXISTING_FEATURES=""
if [[ "$INCREMENTAL" == true ]] && ls "$FEATURES_DIR"/*.md >/dev/null 2>&1; then
  for f in "$FEATURES_DIR"/*.md; do
    slug=$(basename "$f" .md)
    if [[ -n "$EXISTING_FEATURES" ]]; then
      EXISTING_FEATURES="$EXISTING_FEATURES, $slug"
    else
      EXISTING_FEATURES="$slug"
    fi
  done
fi

if [[ "$INCREMENTAL" == true ]]; then
  mkdir -p "$FEATURES_DIR"
  if [[ -n "$EXISTING_FEATURES" ]]; then
    echo "Incremental mode: existing features: $EXISTING_FEATURES"
  else
    echo "Incremental mode: no existing features found"
  fi
else
  # Clean previous features
  rm -rf "$FEATURES_DIR"
  mkdir -p "$FEATURES_DIR"
fi

cd "$PROJECT_ROOT"

echo "Extracting features from PRD..."

TURNS_FLAG=""
if [[ "$MAX_TURNS" -gt 0 ]]; then
  TURNS_FLAG="--max-turns $MAX_TURNS"
fi

# Set up logging for product-manager agent
export HIVE_FEATURE_SLUG="extract"
local_log=$(_agent_log_path "product-manager")
if [[ -n "$local_log" ]]; then
  export HIVE_AGENT_LOG="$local_log"
fi

# Build extraction prompt
EXTRACT_PROMPT="Read the following PRD and extract features.

$(cat "$PRD")"

if [[ "$INCREMENTAL" == true ]] && [[ -n "$EXISTING_FEATURES" ]]; then
  EXTRACT_PROMPT="Read the following PRD and extract ONLY NEW features that are not already implemented.

The following features already exist and should NOT be re-extracted: $EXISTING_FEATURES

Only output features that are genuinely new. If there are no new features, output nothing.

$(cat "$PRD")"
fi

RAW=$(run_claude \
  --system-prompt "$(cat "$HIVE_DIR/agents/product-manager.md")" \
  --print \
  $CLAUDE_PERMISSIONS \
  --model "$DESIGN_MODEL" \
  $TURNS_FLAG \
  "$EXTRACT_PROMPT")

unset HIVE_AGENT_LOG

# Split on ---FEATURE--- delimiter and write individual files
echo "$RAW" | awk -v dir="$FEATURES_DIR" '
  /^---FEATURE---$/ {
    if (outfile) close(outfile)
    getline slug
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", slug)
    outfile = dir "/" slug ".md"
    next
  }
  outfile { print >> outfile }
'

COUNT=$(find "$FEATURES_DIR" -name "*.md" 2>/dev/null | wc -l)
echo "Extracted $COUNT feature(s) to $FEATURES_DIR/"

# Extract dependency graph from feature files
DEPS_FILE="$FEATURES_DIR/dependencies.txt"
> "$DEPS_FILE"
for FFILE in "$FEATURES_DIR"/*.md; do
  [[ -f "$FFILE" ]] || continue
  FSLUG="$(basename "$FFILE" .md)"
  # Parse "Depends on: slug1, slug2" lines
  DEPS=$(grep -i "^Depends on:" "$FFILE" 2>/dev/null | sed 's/^[Dd]epends on: *//' | tr ',' '\n' | tr -d ' ' || true)
  for DEP in $DEPS; do
    [[ -n "$DEP" ]] && echo "$DEP $FSLUG" >> "$DEPS_FILE"
  done
done

if [[ -s "$DEPS_FILE" ]]; then
  DEP_COUNT=$(wc -l < "$DEPS_FILE")
  echo "Found $DEP_COUNT dependency edge(s) in $DEPS_FILE"
else
  echo "No feature dependencies found."
fi
