#!/usr/bin/env bash
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

MAX_RESTARTS="${AUTONOMY_V2_MAX_RESTARTS:-8}"
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

health_dump() {
  "$PYTHON" -m reverend.autonomy_v2.cli health 2>/dev/null || true
}

emit_incident() {
  local severity="$1"
  local kind="$2"
  local message="$3"
  "$PYTHON" -m reverend.autonomy_v2.cli emit-incident \
    --severity "$severity" \
    --kind "$kind" \
    --message "$message" >/dev/null 2>&1 || true
}

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

  {
    echo "AUTONOMY_V2_CHILD_EXIT=$rc"
    echo "--- HEALTH SNAPSHOT ---"
    health_dump
    echo "-----------------------"
  } | tee -a "$LOG"

  case "$rc" in
    0)
      exit 0
      ;;
    20|30)
      message="autonomy stopped after exhausting deterministic recovery budget (rc=$rc)"
      echo "$message" | tee -a "$LOG"
      emit_incident "CRITICAL" "supervisor_blocked" "$message"
      exit "$rc"
      ;;
    75)
      # Another controller owns the lock. Never start a competing process.
      exit "$rc"
      ;;
    130)
      # Explicit Ctrl-C is authoritative and should not page the user.
      exit 130
      ;;
    70|1|137|143)
      if (( restarts >= MAX_RESTARTS )); then
        message="autonomy supervisor restart budget exhausted ($MAX_RESTARTS), last rc=$rc"
        echo "$message" | tee -a "$LOG"
        emit_incident "CRITICAL" "supervisor_restart_exhausted" "$message"
        exit "$rc"
      fi
      restarts=$((restarts + 1))
      emit_incident \
        "WARNING" \
        "supervisor_restart" \
        "controller exited rc=$rc; autonomous restart $restarts/$MAX_RESTARTS scheduled"
      sleep "$RESTART_DELAY"
      if [[ -s "$RUNTIME/latest-session" ]]; then
        command=("resume")
      else
        command=("${INITIAL[@]}")
      fi
      ;;
    *)
      message="unknown autonomy child exit code $rc; preserving evidence and stopping"
      echo "$message" | tee -a "$LOG"
      emit_incident "CRITICAL" "supervisor_unknown_exit" "$message"
      exit "$rc"
      ;;
  esac
done
