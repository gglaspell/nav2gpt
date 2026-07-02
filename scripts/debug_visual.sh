#!/usr/bin/env bash
#
# debug_visual.sh — bring the full stack up *visually* on the Linux box so you
# can watch the robot actually move and eyeball that the branch's feature works.
#
# This is a DEBUG / demo tool, not an automated test. It launches Gazebo + Nav2 +
# the API server in the background and runs the voice node in the foreground.
# Ctrl-C tears everything down.
#
#   ./scripts/debug_visual.sh
#
# ─────────────────────────────────────────────────────────────────────────────
# PER-FEATURE: each feature branch hones the FEATURE HOOK below to tell the
# operator exactly what to do and what to watch for to confirm *this* feature.
# ─────────────────────────────────────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
: "${TURTLEBOT3_MODEL:=waffle}"   # Nav2 launch uses the waffle urdf; override if needed
export TURTLEBOT3_MODEL

# ── FEATURE HOOK ─────────────────────────────────────────────────────────────
# Print what to demonstrate for this branch. dev-setup adds no robot behavior,
# so the goal here is a baseline: prove the stack still comes up and drives.
feature_demo_hint() {
  cat <<'EOF'
FEATURE: feature/dev-setup (baseline — no new robot behavior)
WHAT TO DO:   When prompted, press Enter and say e.g. "go to the kitchen".
WATCH FOR:    Gazebo shows the TurtleBot3 planning a path and driving to the
              goal, exactly as on main. This branch only adds tooling, so the
              robot must behave identically to main.
EOF
}
# ─────────────────────────────────────────────────────────────────────────────

# --- preconditions -----------------------------------------------------------
if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2 not found. This script must run on the Linux machine with ROS 2" >&2
  echo "sourced (source /opt/ros/<distro>/setup.bash) and the workspace built." >&2
  exit 1
fi
WS_SETUP="$REPO_ROOT/nav2gpt_ws/install/setup.bash"
if [ -f "$WS_SETUP" ]; then
  # shellcheck disable=SC1090
  source "$WS_SETUP"
else
  echo "Workspace not built ($WS_SETUP missing). Run:" >&2
  echo "  cd nav2gpt_ws && colcon build && source install/setup.bash" >&2
  exit 1
fi

LOG_DIR="$(mktemp -d)"
PIDS=()
cleanup() {
  echo
  echo "Shutting down stack..."
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null
  done
  wait 2>/dev/null
  echo "Logs kept in: $LOG_DIR"
}
trap cleanup EXIT INT TERM

launch_bg() {   # launch_bg <label> <command...>
  local label="$1"; shift
  echo "  starting $label  (log: $LOG_DIR/$label.log)"
  "$@" >"$LOG_DIR/$label.log" 2>&1 &
  PIDS+=("$!")
}

echo "================================================================"
echo " nav2gpt visual debug — branch: $BRANCH  (TURTLEBOT3_MODEL=$TURTLEBOT3_MODEL)"
echo "================================================================"
feature_demo_hint
echo "----------------------------------------------------------------"

# --- bring the stack up in dependency order ----------------------------------
launch_bg gazebo   ros2 launch ros2ai turtlebot3_navigation.launch.py
echo "  waiting for Gazebo to load..."; sleep 12
launch_bg nav2     ros2 launch ros2ai navigation2.launch.py
echo "  waiting for Nav2 to activate..."; sleep 12
launch_bg apiserver ros2 run ros2ai nav2_api_server
sleep 3

echo "----------------------------------------------------------------"
echo " Stack is up. Starting the voice node in the foreground."
echo " (Ctrl-C here tears the whole stack down.)"
echo "----------------------------------------------------------------"

# Voice node is interactive (waits for Enter, records, transcribes) — foreground.
ros2 run ros2ai Nav2Gpt
