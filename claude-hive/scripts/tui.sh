#!/bin/bash
# Live progress dashboard for Claude Hive pipeline
# Usage: tui.sh [refresh_seconds] [pipeline_pid]

HIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

CONF="$HIVE_DIR/hive.conf"
[[ -f "$CONF" ]] && source "$CONF"

source "$HIVE_DIR/scripts/lib.sh"

HIVE_STATUS_DIR="${HIVE_STATUS_DIR:-$HIVE_DIR/prd/status}"
FEATURES_DIR="$HIVE_DIR/prd/features"
REFRESH="${1:-2}"
PIPELINE_PID="${2:-}"

# ANSI codes
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
GRAY='\033[90m'
BOLD='\033[1m'
RESET='\033[0m'

STAGES=(design architect implement test debug review commit)
STAGE_LABELS=("DESIGN" "ARCH  " "IMPL  " "TEST  " "DEBUG " "REVIEW" "COMMIT")

# Track start time
START_TIME=${HIVE_TUI_START:-$(date +%s)}

format_elapsed() {
  local elapsed=$1
  local mins=$((elapsed / 60))
  local secs=$((elapsed % 60))
  if [[ $mins -ge 60 ]]; then
    local hrs=$((mins / 60))
    mins=$((mins % 60))
    printf "%dh %dm %ds" "$hrs" "$mins" "$secs"
  else
    printf "%dm %ds" "$mins" "$secs"
  fi
}

# Print a colored symbol for a stage status
# Returns exactly 1 visible character (plus ANSI codes)
print_stage() {
  local status=$1
  case "$status" in
    complete)     printf "${GREEN}✓${RESET}" ;;
    in-progress)  printf "${YELLOW}●${RESET}" ;;
    failed)       printf "${RED}✗${RESET}" ;;
    skipped)      printf "${CYAN}~${RESET}" ;;
    *)            printf "${GRAY}·${RESET}" ;;
  esac
}

print_status() {
  local status=$1
  case "$status" in
    complete)     printf "${GREEN}complete${RESET}" ;;
    in-progress)  printf "${YELLOW}in-progress${RESET}" ;;
    failed)       printf "${RED}failed${RESET}" ;;
    *)            printf "${GRAY}pending${RESET}" ;;
  esac
}

render() {
  # Move cursor to top-left and clear screen
  printf '\033[2J\033[H'

  local now
  now=$(date +%s)
  local elapsed=$((now - START_TIME))

  # Collect features
  local features=()
  if [[ -d "$FEATURES_DIR" ]]; then
    for f in "$FEATURES_DIR"/*.md; do
      [[ -f "$f" ]] || continue
      features+=("$(basename "$f" .md)")
    done
  fi

  local total=${#features[@]}
  local n_complete=0 n_progress=0 n_failed=0 n_pending=0

  for feat in "${features[@]}"; do
    local s
    s=$(read_feature_status "$feat" "status")
    case "$s" in
      complete)     ((n_complete++)) ;;
      in-progress)  ((n_progress++)) ;;
      failed)       ((n_failed++)) ;;
      *)            ((n_pending++)) ;;
    esac
  done

  # Header
  printf "${BOLD}===========================================${RESET}\n"
  printf "${BOLD} CLAUDE HIVE: Pipeline Progress${RESET}\n"
  printf "${BOLD}===========================================${RESET}\n"
  printf " Elapsed: %s\n" "$(format_elapsed $elapsed)"

  # Summary line
  printf " Features: "
  printf "${GREEN}%d${RESET} done" "$n_complete"
  [[ $n_progress -gt 0 ]] && printf "  ${YELLOW}%d${RESET} running" "$n_progress"
  [[ $n_failed -gt 0 ]] && printf "  ${RED}%d${RESET} failed" "$n_failed"
  [[ $n_pending -gt 0 ]] && printf "  ${GRAY}%d${RESET} pending" "$n_pending"
  printf "  (%d total)\n" "$total"

  printf "${GRAY}-------------------------------------------${RESET}\n"

  if [[ $total -eq 0 ]]; then
    printf "\n ${GRAY}Waiting for feature extraction...${RESET}\n"
  else
    # Column header
    # Feature name: 20 chars, each stage: 7 chars, status: rest
    printf "\n ${BOLD}%-20s " "FEATURE"
    for label in "${STAGE_LABELS[@]}"; do
      printf " %s" "$label"
    done
    printf "  STATUS${RESET}\n"

    # Feature rows
    for feat in "${features[@]}"; do
      # Truncate long feature names
      local display_name="$feat"
      if [[ ${#display_name} -gt 19 ]]; then
        display_name="${display_name:0:18}…"
      fi
      printf " %-20s" "$display_name"

      for stage in "${STAGES[@]}"; do
        local ss
        ss=$(read_feature_status "$feat" "stage_${stage}")
        printf "   "
        print_stage "$ss"
        printf "   "
      done

      printf "  "
      local overall
      overall=$(read_feature_status "$feat" "status")
      overall="${overall:-pending}"
      print_status "$overall"
      printf "\n"
    done
  fi

  printf "\n${GRAY}-------------------------------------------${RESET}\n"
  printf " ${GREEN}✓${RESET} complete  ${YELLOW}●${RESET} in-progress  ${RED}✗${RESET} failed  ${CYAN}~${RESET} skipped  ${GRAY}·${RESET} pending\n"

  if [[ -n "${HIVE_RUN_LOG_DIR:-}" ]]; then
    printf " Logs: %s\n" "$HIVE_RUN_LOG_DIR"
  fi

  if [[ -n "$PIPELINE_PID" ]]; then
    if kill -0 "$PIPELINE_PID" 2>/dev/null; then
      printf " Pipeline PID: %s (running)\n" "$PIPELINE_PID"
    else
      printf " Pipeline PID: %s ${BOLD}(finished)${RESET}\n" "$PIPELINE_PID"
    fi
  fi

  printf "\n Press Ctrl+C to exit"
  if [[ -n "$PIPELINE_PID" ]]; then
    printf " (pipeline continues in background)"
  fi
  printf "\n"
}

# Handle Ctrl+C gracefully
trap 'printf "\n"; exit 0' INT TERM

# Main loop
while true; do
  render

  # Auto-exit when pipeline finishes
  if [[ -n "$PIPELINE_PID" ]] && ! kill -0 "$PIPELINE_PID" 2>/dev/null; then
    sleep 1
    render  # Final render
    printf "\n Pipeline has finished.\n"
    break
  fi

  sleep "$REFRESH"
done
