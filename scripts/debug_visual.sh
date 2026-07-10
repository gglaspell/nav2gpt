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
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SLUG="$(echo "$BRANCH" | tr '/ ' '__')"
# FORCE burger: Nav2 loads the burger URDF + burger-tuned params, and the burger
# fits the house doorways (the waffle wedges in them).
TURTLEBOT3_MODEL=burger
export TURTLEBOT3_MODEL

# ── FEATURE HOOK ─────────────────────────────────────────────────────────────
# Print what to demonstrate for this branch. dev-setup adds no robot behavior,
# so the goal here is a baseline: prove the stack still comes up and drives.
feature_demo_hint() {
  cat <<'EOF'
FEATURE: feature/dynamic-locations (save this location + where am I?)
WHAT TO DO:   At the voice prompt you can now type a command instead of speaking
              (dev aid). Try, in order:
                1. "where am I"                     -> names the nearest room
                2. "save this location as the desk" -> records the current pose
                3. drive elsewhere, then "where am I" and "go to the desk"
              Saved rooms live in ~/.nav2gpt/locations.json (NAV2GPT_LOCATIONS).
WATCH FOR:    - "where am I" answers with a room name (or coordinates) and speaks it.
              - After saving, "go to <name>" navigates there — the saved room is
                fed into the LLM prompt, so it's a real nav target now.
              - locations.json gains the new entry alongside the kitchen/bedroom.
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

# Persistent, timestamped log dir: debug output survives a reboot and sits with
# the other reports (single-machine flow — no hunting in /tmp).
LOG_DIR="$REPO_ROOT/reports/logs/debug_${SLUG}_${TS}"; mkdir -p "$LOG_DIR"
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
# Localize via AMCL: seed the initial pose so map->odom is published correctly.
# (A fake static map->odom lets goals plan but with wrong localization — the
# robot then paths around phantom walls. Seeding AMCL is the real fix.)
bash "$REPO_ROOT/scripts/set_initial_pose.sh" >/dev/null 2>&1 &
sleep 3
launch_bg apiserver ros2 run ros2ai nav2_api_server
sleep 3

echo "----------------------------------------------------------------"
echo " Stack is up. Starting the voice node in the foreground."
echo " (Ctrl-C here tears the whole stack down.)"
echo "----------------------------------------------------------------"

# Voice node is interactive (waits for Enter, records, transcribes) — foreground.
ros2 run ros2ai Nav2Gpt
