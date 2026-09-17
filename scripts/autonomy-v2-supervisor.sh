#!/usr/bin/env bash
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

MAX_RESTARTS="${AUTONOMY_V2_MAX_RESTARTS:-5}"
RESTART_DELAY="${AUTONOMY_V2_RESTART_DELAY:-5}"
RUNTIME="$ROOT/.autonomy/v2-production"
mkdir -p "$RUNTIME"
LOG="$RUNTIME/supervisor.log"

if [[ $# -eq 0 ]]; then
  echo "usage: scripts/autonomy-v2-supervisor.sh run [run options...]" >&2
  echo "       scripts/autonomy-v2-supervisor.sh resume [--session ID] [--retry-failed]" >&2
  exit 2
fi

INITIAL=("$@")
MODE="${1}"
if [[ "$MODE" != "run" && "$MODE" != "resume" ]]; then
  echo "supervisor only accepts run or resume as the first argument" >&2
  exit 2
fi

restarts=0
command=("${INITIAL[@]}")

while true; do
  {
    echo
    echo "============================================================"
    echo "AUTONOMY V2 SUPERVISOR $(date -Is)"
    echo "attempt=$((restarts + 1)) command=${command[*]}"
    echo "============================================================"
  } | tee -a "$LOG"

  "$PYTHON" -m reverend.autonomy_v2.cli "${command[@]}" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}

  echo "AUTONOMY_V2_CHILD_EXIT=$rc" | tee -a "$LOG"

  case "$rc" in
    0)
      exit 0
      ;;
    20|30)
      # Genuine blocker or failed milestone gate. Restarting would only repeat
      # a deterministically rejected state and could hide the evidence.
      exit "$rc"
      ;;
    75)
      # Another controller owns the lock. Do not start a competing process.
      exit "$rc"
      ;;
    130)
      # Explicit human interrupt is authoritative.
      exit 130
      ;;
    70|1|137)
      if (( restarts >= MAX_RESTARTS )); then
        echo "restart budget exhausted ($MAX_RESTARTS)" | tee -a "$LOG"
        exit "$rc"
      fi
      restarts=$((restarts + 1))
      sleep "$RESTART_DELAY"
      if [[ -s "$RUNTIME/latest-session" ]]; then
        command=("resume")
      else
        command=("${INITIAL[@]}")
      fi
      ;;
    *)
      # Unknown exit codes are not assumed transient.
      exit "$rc"
      ;;
  esac
done
