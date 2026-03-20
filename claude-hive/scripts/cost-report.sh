#!/bin/bash
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Source config
CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

LOG_DIR="${LOG_DIR:-$HIVE_DIR/prd/logs}"

# Find the most recent run's cost log, or accept a specific path
COST_LOG="${1:-}"
if [[ -z "$COST_LOG" ]]; then
  # Find most recent cost.csv
  LATEST_RUN=$(ls -dt "$LOG_DIR"/run-* 2>/dev/null | head -1)
  if [[ -z "$LATEST_RUN" ]]; then
    echo "No run logs found in $LOG_DIR/" >&2
    exit 1
  fi
  COST_LOG="$LATEST_RUN/cost.csv"
fi

if [[ ! -f "$COST_LOG" ]]; then
  echo "No cost data found at $COST_LOG" >&2
  echo "Token tracking requires claude CLI --output-format json support." >&2
  exit 1
fi

echo "=========================================="
echo " CLAUDE HIVE: Cost & Token Report"
echo "=========================================="
echo " Source: $COST_LOG"
echo ""

# CSV format: agent,feature,input_tokens,output_tokens,model,timestamp

# Summary by agent
echo "--- Tokens by Agent ---"
printf "%-22s %12s %12s %12s\n" "AGENT" "INPUT" "OUTPUT" "TOTAL"
printf "%-22s %12s %12s %12s\n" "-----" "-----" "------" "-----"
awk -F, '
  NR>0 {
    agent=$1; input=$3; output=$4
    a_in[agent] += input
    a_out[agent] += output
    t_in += input
    t_out += output
  }
  END {
    for (a in a_in)
      printf "%-22s %12d %12d %12d\n", a, a_in[a], a_out[a], a_in[a]+a_out[a]
    printf "%-22s %12s %12s %12s\n", "-----", "-----", "------", "-----"
    printf "%-22s %12d %12d %12d\n", "TOTAL", t_in, t_out, t_in+t_out
  }
' "$COST_LOG"

echo ""

# Summary by feature
echo "--- Tokens by Feature ---"
printf "%-22s %12s %12s %12s\n" "FEATURE" "INPUT" "OUTPUT" "TOTAL"
printf "%-22s %12s %12s %12s\n" "-------" "-----" "------" "-----"
awk -F, '
  NR>0 {
    feat=$2; input=$3; output=$4
    f_in[feat] += input
    f_out[feat] += output
    t_in += input
    t_out += output
  }
  END {
    for (f in f_in)
      printf "%-22s %12d %12d %12d\n", f, f_in[f], f_out[f], f_in[f]+f_out[f]
    printf "%-22s %12s %12s %12s\n", "-------", "-----", "------", "-----"
    printf "%-22s %12d %12d %12d\n", "TOTAL", t_in, t_out, t_in+t_out
  }
' "$COST_LOG"

echo ""

# Cost estimate
echo "--- Estimated Cost ---"
# Default pricing (per million tokens)
COST_INPUT_SONNET="${COST_INPUT_SONNET:-3.00}"
COST_OUTPUT_SONNET="${COST_OUTPUT_SONNET:-15.00}"
COST_INPUT_OPUS="${COST_INPUT_OPUS:-15.00}"
COST_OUTPUT_OPUS="${COST_OUTPUT_OPUS:-75.00}"
COST_INPUT_HAIKU="${COST_INPUT_HAIKU:-0.25}"
COST_OUTPUT_HAIKU="${COST_OUTPUT_HAIKU:-1.25}"

awk -F, \
  -v ci_sonnet="$COST_INPUT_SONNET" -v co_sonnet="$COST_OUTPUT_SONNET" \
  -v ci_opus="$COST_INPUT_OPUS" -v co_opus="$COST_OUTPUT_OPUS" \
  -v ci_haiku="$COST_INPUT_HAIKU" -v co_haiku="$COST_OUTPUT_HAIKU" '
  NR>0 {
    input=$3; output=$4; model=$5
    if (model ~ /opus/) { cost += (input * ci_opus + output * co_opus) / 1000000 }
    else if (model ~ /haiku/) { cost += (input * ci_haiku + output * co_haiku) / 1000000 }
    else { cost += (input * ci_sonnet + output * co_sonnet) / 1000000 }
    total_in += input
    total_out += output
  }
  END {
    printf "Total input tokens:  %d\n", total_in
    printf "Total output tokens: %d\n", total_out
    printf "Estimated cost:      $%.2f\n", cost
  }
' "$COST_LOG"

echo ""
echo "Note: Cost estimates use default API pricing. Subscription plans may differ."
