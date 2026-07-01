#!/usr/bin/env bash
#
# integration_test.sh — a guided, interactive "automated README" run.
#
# Walks the README's "Running the Project" steps on the Linux box: opens a
# terminal window per stack component (Gazebo, Nav2, API server, voice node),
# pauses at each step with an instruction, then asks you to confirm whether the
# robot actually did the right thing. The verdict + your notes are written to a
# report under reports/ (pushed by push_report.sh, same as the automated suite).
#
#   ./scripts/integration_test.sh
#
# It SKIPS cleanly (writing a SKIP report, exit 0) when it can't run — no display,
# no TTY, ROS not installed, or workspace not built — so it's safe inside the
# universal paste on any machine.
#
# ─────────────────────────────────────────────────────────────────────────────
# PER-FEATURE: hone feature_integration() below to add the checkpoints and the
# pass/fail question that prove THIS branch's feature live in the UI.
# ─────────────────────────────────────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
HOSTNAME_STR="$(hostname 2>/dev/null || echo unknown)"
: "${TURTLEBOT3_MODEL:=waffle}"; export TURTLEBOT3_MODEL

REPORT_DIR="$REPO_ROOT/reports"; mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/$(echo "$BRANCH" | tr '/ ' '__')_integration_${TS}.md"

# --- resolve ROS + workspace setup files -------------------------------------
if [ -n "${ROS_DISTRO:-}" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
  ROS_SETUP="/opt/ros/$ROS_DISTRO/setup.bash"
else
  ROS_SETUP="$(ls -1 /opt/ros/*/setup.bash 2>/dev/null | head -1)"
fi
WS_SETUP="$REPO_ROOT/nav2gpt_ws/install/setup.bash"

write_skip_report() {   # write_skip_report <reason>
  {
    echo "# Integration report — \`$BRANCH\`"
    echo
    echo "| Field | Value |"
    echo "|-------|-------|"
    echo "| Result | **SKIPPED ⏭️** |"
    echo "| Reason | $1 |"
    echo "| Branch | \`$BRANCH\` |"
    echo "| Commit | \`$SHA\` |"
    echo "| Run at (UTC) | $TS |"
    echo "| Host | $HOSTNAME_STR |"
  } > "$REPORT"
  echo "Integration test SKIPPED: $1"
  echo "Report: $REPORT"
}

# --- preconditions: skip (don't fail) if we can't do a live run --------------
[ -t 0 ] || { write_skip_report "no interactive terminal (stdin not a TTY)"; exit 0; }
[ -n "${DISPLAY:-}" ] || { write_skip_report "no DISPLAY (needs a graphical session for Gazebo/RViz)"; exit 0; }
[ -n "$ROS_SETUP" ] || { write_skip_report "no ROS 2 install found under /opt/ros/*"; exit 0; }
[ -f "$WS_SETUP" ]   || { write_skip_report "workspace not built (run: cd nav2gpt_ws && colcon build)"; exit 0; }

# --- detect a terminal emulator (fall back to background+logs) ---------------
TERM_EMU=""
for t in gnome-terminal konsole xfce4-terminal xterm; do
  command -v "$t" >/dev/null 2>&1 && { TERM_EMU="$t"; break; }
done
LOG_DIR="$(mktemp -d)"
LAUNCH_PATTERNS=()   # for teardown

open_stack_terminal() {   # open_stack_terminal <title> <ros2 command...>
  local title="$1"; shift
  local cmd="$*"
  LAUNCH_PATTERNS+=("$cmd")
  local inner="source '$ROS_SETUP'; source '$WS_SETUP'; export TURTLEBOT3_MODEL='$TURTLEBOT3_MODEL'; echo '=== $title ==='; $cmd; echo; echo '[$title exited — you can close this window]'; exec bash"
  case "$TERM_EMU" in
    gnome-terminal)  gnome-terminal --title="$title" -- bash -c "$inner" >/dev/null 2>&1 & ;;
    konsole)         konsole -p tabtitle="$title" -e bash -c "$inner" >/dev/null 2>&1 & ;;
    xfce4-terminal)  xfce4-terminal --title="$title" -x bash -c "$inner" >/dev/null 2>&1 & ;;
    xterm)           xterm -T "$title" -e bash -c "$inner" >/dev/null 2>&1 & ;;
    "")              # no emulator: background with a log file
      bash -c "source '$ROS_SETUP'; source '$WS_SETUP'; export TURTLEBOT3_MODEL='$TURTLEBOT3_MODEL'; $cmd" >"$LOG_DIR/$title.log" 2>&1 &
      echo "   (no terminal emulator; '$title' running in background, log: $LOG_DIR/$title.log)" ;;
  esac
}

pause() { read -r -p "   ↳ $1 [Enter to continue] "; }
ask_yn() {   # ask_yn <question> -> sets REPLY_YN to yes/no
  local a; read -r -p "   ↳ $1 [y/N] " a
  case "$a" in [yY]*) REPLY_YN=yes ;; *) REPLY_YN=no ;; esac
}

STEP_LOG=()   # human-readable record of what happened, for the report
record() { STEP_LOG+=("$1"); echo "   • $1"; }

# ── FEATURE HOOK ─────────────────────────────────────────────────────────────
# Extra checkpoints + the pass/fail question specific to this branch. dev-setup
# adds no robot behavior, so its "feature" is baseline parity with main.
feature_integration() {
  echo
  echo ">> FEATURE CHECK: feature/$BRANCH"
  echo "   dev-setup adds only tooling — the robot must behave exactly like main."
  echo "   In the VOICE NODE window: press Enter, then say \"go to the kitchen\"."
  pause "Watch Gazebo: the robot should plan a path and drive to the kitchen."
  ask_yn "Did the robot navigate to the goal correctly (same as main)?"
  FEATURE_VERDICT="$REPLY_YN"
  read -r -p "   ↳ Notes (optional, Enter to skip): " FEATURE_NOTES
}
# ─────────────────────────────────────────────────────────────────────────────

teardown() {
  echo
  read -r -p "Press Enter to shut the stack down... "
  echo "Tearing down..."
  for p in "${LAUNCH_PATTERNS[@]}"; do pkill -f "$p" 2>/dev/null; done
  pkill -f gzserver 2>/dev/null; pkill -f gzclient 2>/dev/null
  pkill -f 'nav2_api_server' 2>/dev/null; pkill -f 'nav_gpt' 2>/dev/null
  echo "Done. (Close any leftover terminal windows manually.)"
}
trap 'teardown' EXIT

echo "================================================================"
echo " nav2gpt guided integration — branch: $BRANCH  (model: $TURTLEBOT3_MODEL)"
echo " terminal: ${TERM_EMU:-none (background mode)}"
echo "================================================================"
echo "This walks the README launch steps. Follow each prompt, then confirm."
echo

record "Terminal 1 — Gazebo + TurtleBot3"
open_stack_terminal "1-gazebo" ros2 launch ros2ai turtlebot3_navigation.launch.py
pause "Wait until Gazebo (and RViz) fully load and the house + robot are visible."

record "Terminal 2 — Nav2"
open_stack_terminal "2-nav2" ros2 launch ros2ai navigation2.launch.py
pause "Wait until Nav2 lifecycle nodes are active (no more 'configuring' spam)."

record "Terminal 3 — Nav2 API server"
open_stack_terminal "3-apiserver" ros2 run ros2ai nav2_api_server
pause "Confirm the API server started without errors."

record "Terminal 4 — LLM voice node"
open_stack_terminal "4-voice" ros2 run ros2ai Nav2Gpt
pause "Wait until the voice node prints 'connected to goToPose server'."

feature_integration

# --- write the report --------------------------------------------------------
if [ "${FEATURE_VERDICT:-no}" = "yes" ]; then
  RESULT="PASS ✅"; EXIT=0
else
  RESULT="FAIL ❌"; EXIT=1
fi

{
  echo "# Integration report — \`$BRANCH\`"
  echo
  echo "| Field | Value |"
  echo "|-------|-------|"
  echo "| Result | **$RESULT** |"
  echo "| Branch | \`$BRANCH\` |"
  echo "| Commit | \`$SHA\` |"
  echo "| Run at (UTC) | $TS |"
  echo "| Host | $HOSTNAME_STR |"
  echo "| ROS setup | $ROS_SETUP |"
  echo "| Model | $TURTLEBOT3_MODEL |"
  echo "| Terminal | ${TERM_EMU:-background} |"
  echo
  echo "## Steps walked"
  echo
  for s in "${STEP_LOG[@]}"; do echo "- $s"; done
  echo
  echo "## Feature verdict"
  echo
  echo "- Robot navigated correctly: **${FEATURE_VERDICT:-no}**"
  echo "- Notes: ${FEATURE_NOTES:-(none)}"
} > "$REPORT"

echo
echo "----------------------------------------------------------------"
echo "Integration result: $RESULT"
echo "Report: $REPORT"
echo "----------------------------------------------------------------"

exit "$EXIT"
