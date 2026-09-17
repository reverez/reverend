#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

RUNTIME="$ROOT/.autonomy/v2-production"
mkdir -p "$RUNTIME"
SESSION_NAME="${AUTONOMY_V2_TMUX_SESSION:-reverend-v2}"
PID_FILE="$RUNTIME/daemon.pid"
LOG="$RUNTIME/daemon.log"
SUPERVISOR="$ROOT/scripts/autonomy-v2-supervisor.sh"

usage() {
  echo "usage:" >&2
  echo "  scripts/autonomy-v2-daemon.sh start run [run options...]" >&2
  echo "  scripts/autonomy-v2-daemon.sh start resume [resume options...]" >&2
  echo "  scripts/autonomy-v2-daemon.sh status" >&2
  echo "  scripts/autonomy-v2-daemon.sh stop" >&2
}

is_nohup_alive() {
  [[ -s "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE")"
  kill -0 "$pid" 2>/dev/null
}

status() {
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "RUNNING backend=tmux session=$SESSION_NAME"
    return 0
  fi
  if is_nohup_alive; then
    echo "RUNNING backend=nohup pid=$(cat "$PID_FILE")"
    return 0
  fi
  echo "STOPPED"
  return 1
}

stop() {
  local stopped=0
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
    stopped=1
  fi
  if is_nohup_alive; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    stopped=1
  fi
  rm -f "$PID_FILE"
  if (( stopped )); then
    echo "STOPPED"
  else
    echo "ALREADY_STOPPED"
  fi
}

start() {
  shift
  if [[ $# -lt 1 || ( "$1" != "run" && "$1" != "resume" ) ]]; then
    usage
    exit 2
  fi
  if status >/dev/null 2>&1; then
    echo "autonomy daemon is already running" >&2
    status || true
    exit 75
  fi

  if command -v tmux >/dev/null 2>&1; then
    local command_line
    printf -v command_line '%q ' "$SUPERVISOR" "$@"
    tmux new-session -d -s "$SESSION_NAME" "cd $(printf '%q' "$ROOT") && exec $command_line"
    echo "STARTED backend=tmux session=$SESSION_NAME"
    echo "watch: tmux attach -t $SESSION_NAME"
    return 0
  fi

  nohup "$SUPERVISOR" "$@" >>"$LOG" 2>&1 &
  echo $! > "$PID_FILE"
  echo "STARTED backend=nohup pid=$! log=$LOG"
}

case "${1:-}" in
  start)
    start "$@"
    ;;
  status)
    status
    ;;
  stop)
    stop
    ;;
  *)
    usage
    exit 2
    ;;
esac
