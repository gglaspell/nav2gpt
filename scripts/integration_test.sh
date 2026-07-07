#!/usr/bin/env bash
#
# integration_test.sh — a guided, interactive "automated README" run.
#
# Walks the README's "Running the Project" steps on the Linux box: opens a
# terminal window per stack component (Gazebo, Nav2, API server, voice node),
# pauses at each step with an instruction, snaps a screenshot when you confirm
# it, then asks you to confirm whether the robot actually did the right thing.
# The verdict + your notes + all screenshots are written under reports/ (pushed
# by push_report.sh, same as the automated suite) — handy documentation for
# writeups/slideshows, not just a pass/fail signal.
#
#   ./scripts/integration_test.sh
#
# It SKIPS cleanly (writing a SKIP report, exit 0) when it can't run — no display,
# no TTY, ROS not installed, or workspace not built — so it's safe inside the
# universal paste on any machine. Even when skipped, it still generates the
# branch-graph poster below (that one needs no display).
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
SLUG="$(echo "$BRANCH" | tr '/ ' '__')"
REPORT="$REPORT_DIR/${SLUG}_integration_${TS}.md"
SHOT_DIR="$REPORT_DIR/screenshots/${SLUG}_${TS}"
SHOTS=()          # captured screenshot paths (for the report + contact sheet)
SHOT_N=0

# --- resolve ROS + workspace setup files -------------------------------------
if [ -n "${ROS_DISTRO:-}" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
  ROS_SETUP="/opt/ros/$ROS_DISTRO/setup.bash"
else
  ROS_SETUP="$(ls -1 /opt/ros/*/setup.bash 2>/dev/null | head -1)"
fi
WS_SETUP="$REPO_ROOT/nav2gpt_ws/install/setup.bash"

# --- screenshot capture -------------------------------------------------------
# capture_screenshot <label> [wm-class candidates...]
# Best-effort: tries to grab the named window (by X11 WM_CLASS, most reliable
# for Gazebo/RViz), falls back to a full-screen grab, and silently no-ops if
# ImageMagick's `import` isn't installed. Never fails the run.
capture_screenshot() {
  local label="$1"; shift
  command -v import >/dev/null 2>&1 || { echo "   (screenshot skipped: install imagemagick for slideshow captures)"; return 0; }
  mkdir -p "$SHOT_DIR"
  SHOT_N=$((SHOT_N + 1))
  local out="$SHOT_DIR/$(printf '%02d' "$SHOT_N")-${label}.png"
  local win=""
  if command -v xdotool >/dev/null 2>&1; then
    for cls in "$@"; do
      win="$(xdotool search --onlyvisible --class "$cls" 2>/dev/null | head -1)"
      [ -n "$win" ] && break
    done
  fi
  if [ -n "$win" ] && import -window "$win" "$out" 2>/dev/null; then
    echo "   screenshot: ${out#$REPORT_DIR/}"
  elif import -window root "$out" 2>/dev/null; then
    echo "   screenshot (full desktop — target window not found): ${out#$REPORT_DIR/}"
  else
    echo "   (screenshot capture failed, continuing)"
    return 0
  fi
  SHOTS+=("$out")
}

# Bonus artifact: a "poster" of the branch-per-feature git graph. Needs no
# display/TTY/ROS, so it's generated unconditionally — nice slideshow material
# showing the actual branching workflow, not just a screenshot of the robot.
capture_branch_graph() {
  command -v convert >/dev/null 2>&1 || return 0
  local graph_txt graph_png font
  graph_txt="$(git log --all --graph --oneline --decorate -n 40 2>/dev/null)"
  [ -n "$graph_txt" ] || return 0
  mkdir -p "$SHOT_DIR"
  graph_png="$SHOT_DIR/00-branch-graph.png"
  # Font availability varies wildly by machine/ImageMagick build. Try common
  # registered names first (what a plain `apt install imagemagick` on Ubuntu
  # resolves), then a few likely absolute font file paths (Linux + macOS), then
  # ImageMagick's own default. First one that renders wins; if all fail, skip
  # the bonus silently — never breaks the run.
  for font in \
    "DejaVu-Sans-Mono" "Courier" "Courier-New" "Menlo" \
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf" \
    "/System/Library/Fonts/Supplemental/Courier New.ttf" \
    "none"
  do
    if [ "$font" = "none" ]; then
      convert -background '#1e1e2e' -fill '#a6e3a1' -pointsize 16 \
        -size 1400x -gravity NorthWest label:"$graph_txt" "$graph_png" 2>/dev/null
    else
      convert -background '#1e1e2e' -fill '#a6e3a1' -font "$font" -pointsize 16 \
        -size 1400x -gravity NorthWest label:"$graph_txt" "$graph_png" 2>/dev/null
    fi
    if [ $? -eq 0 ]; then
      echo "   branch graph poster: ${graph_png#$REPORT_DIR/}"
      SHOTS+=("$graph_png")
      return 0
    fi
  done
}

# Bonus artifact: one contact-sheet image combining every screenshot from this
# run — a single "hero image" that's easy to drop into a slide.
capture_contact_sheet() {
  command -v montage >/dev/null 2>&1 || return 0
  [ "${#SHOTS[@]}" -ge 2 ] || return 0
  local sheet="$SHOT_DIR/99-contact-sheet.png"
  montage "${SHOTS[@]:-}" -tile 2x -geometry 480x360+8+8 -background '#1e1e2e' "$sheet" 2>/dev/null \
    && { echo "   contact sheet: ${sheet#$REPORT_DIR/}"; SHOTS+=("$sheet"); }
}

write_skip_report() {   # write_skip_report <reason>
  capture_branch_graph
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
    if [ "${#SHOTS[@]}" -gt 0 ]; then
      echo
      echo "## Artifacts"
      echo
      for s in "${SHOTS[@]:-}"; do echo "![${s##*/}](${s#$REPORT_DIR/})"; done
    fi
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
LOG_DIR="$(mktemp -d)"   # live per-terminal logs (full, ephemeral)
LAUNCH_PATTERNS=()       # for teardown

# Every launched component tees its stdout+stderr to $LOG_DIR/<title>.log while
# still showing in its window, so the output of all four terminals (plus the
# localization step's autodetect diagnostics) is captured. finalize() copies a
# capped tail of each into the pushed report — no more retyping errors by hand.
open_stack_terminal() {   # open_stack_terminal <title> <ros2 command...>
  local title="$1"; shift
  local cmd="$*"
  LAUNCH_PATTERNS+=("$cmd")
  local log="$LOG_DIR/$title.log"
  local env="source '$ROS_SETUP'; source '$WS_SETUP'; export TURTLEBOT3_MODEL='$TURTLEBOT3_MODEL';"
  # stdbuf -oL keeps output flowing line-by-line into the log instead of getting
  # stuck in a block buffer when stdout is a pipe.
  local run="{ echo '=== $title ==='; stdbuf -oL -eL $cmd; } 2>&1 | tee '$log'"
  local inner="$env $run; echo; echo '[$title exited — you can close this window]'; exec bash"
  # </dev/null on every launch so a backgrounded component can't consume the
  # script's stdin (which would make the Enter prompts stop waiting).
  case "$TERM_EMU" in
    gnome-terminal)  gnome-terminal --title="$title" -- bash -c "$inner" </dev/null >/dev/null 2>&1 & ;;
    konsole)         konsole -p tabtitle="$title" -e bash -c "$inner" </dev/null >/dev/null 2>&1 & ;;
    xfce4-terminal)  xfce4-terminal --title="$title" -x bash -c "$inner" </dev/null >/dev/null 2>&1 & ;;
    xterm)           xterm -T "$title" -e bash -c "$inner" </dev/null >/dev/null 2>&1 & ;;
    "")              # no emulator: background, output straight to the log file
      bash -c "$env stdbuf -oL -eL $cmd" </dev/null >"$log" 2>&1 &
      echo "   (no terminal emulator; '$title' running in background, log: $log)" ;;
  esac
}

# Read prompts from the controlling terminal (/dev/tty), NOT fd 0. A backgrounded
# stack component can otherwise leave the script's stdin at EOF, which made every
# `read` return instantly and launch all terminals at once without waiting.
pause() { read -r -p "   ↳ $1 [Enter to continue] " </dev/tty; }
ask_yn() {   # ask_yn <question> -> sets REPLY_YN to yes/no
  local a; read -r -p "   ↳ $1 [y/N] " a </dev/tty
  case "$a" in [yY]*) REPLY_YN=yes ;; *) REPLY_YN=no ;; esac
}

STEP_LOG=()   # human-readable record of what happened, for the report
record() { STEP_LOG+=("$1"); echo "   • $1"; }

# ── FEATURE HOOK ─────────────────────────────────────────────────────────────
# Extra checkpoints + the pass/fail question specific to this branch. dev-setup
# is tooling-only PLUS one opt-in dev convenience in nav_gpt.py: pressing 'x'
# at the recording prompt injects a canned transcript instead of using the mic
# (DEV_MODE_CANNED_TRANSCRIPT — must be flipped False before merging to main;
# tracked in .project/ROADMAP.md's merge checklist). The robot's actual
# navigation behavior is otherwise identical to main.
feature_integration() {
  echo
  echo ">> FEATURE CHECK: feature/$BRANCH"
  echo "   dev-setup is tooling-only plus a dev-mode canned-transcript shortcut."
  echo "   In the VOICE NODE window: press 'x' + Enter for the canned transcript"
  echo "   (\"go to the kitchen\"), or press Enter then speak it yourself."
  pause "Watch Gazebo: the robot should plan a path and drive to the kitchen."
  ask_yn "Did the robot navigate to the goal correctly (same as main)?"
  FEATURE_VERDICT="$REPLY_YN"
  read -r -p "   ↳ Notes (optional, Enter to skip): " FEATURE_NOTES </dev/tty
}
# ─────────────────────────────────────────────────────────────────────────────

COMPLETED=0     # set to 1 once feature_integration returns a verdict
FINALIZED=0     # guard so finalize() only runs once

# finalize() writes the report + contact sheet and grabs a final screenshot.
# It runs from the EXIT trap, so the data for every stage reached so far is
# ALWAYS collected — whether you pressed Enter through the whole run, Ctrl-C'd
# partway, or a stage errored out. Idempotent.
finalize() {
  [ "$FINALIZED" = "1" ] && return 0
  FINALIZED=1

  # Grab whatever's on screen at exit, then a combined contact sheet.
  capture_screenshot "final-state" gzclient Gazebo rviz2 RViz
  capture_contact_sheet

  # Collect each terminal's output: copy a capped tail into the pushed report
  # dir (full live logs can be huge/noisy) so the logs travel to GitHub.
  local pushlog="$REPORT_DIR/logs/${SLUG}_${TS}"
  local f
  for f in "$LOG_DIR"/*.log; do
    [ -f "$f" ] || continue
    mkdir -p "$pushlog"
    tail -n 300 "$f" > "$pushlog/$(basename "$f")"
  done

  local result
  if [ "$COMPLETED" != "1" ]; then
    result="INCOMPLETE ⏹️ (run ended before the feature verdict)"
  elif [ "${FEATURE_VERDICT:-no}" = "yes" ]; then
    result="PASS ✅"
  else
    result="FAIL ❌"
  fi

  {
    echo "# Integration report — \`$BRANCH\`"
    echo
    echo "| Field | Value |"
    echo "|-------|-------|"
    echo "| Result | **$result** |"
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
    for s in "${STEP_LOG[@]:-}"; do [ -n "$s" ] && echo "- $s"; done
    echo
    echo "## Feature verdict"
    echo
    echo "- Robot navigated correctly: **${FEATURE_VERDICT:-(not reached)}**"
    echo "- Notes: ${FEATURE_NOTES:-(none)}"
    if [ "${#SHOTS[@]}" -gt 0 ]; then
      echo
      echo "## Artifacts (screenshots / posters — slideshow material)"
      echo
      for s in "${SHOTS[@]:-}"; do [ -n "$s" ] && echo "![${s##*/}](${s#$REPORT_DIR/})"; done
    fi
    if [ -d "$pushlog" ]; then
      echo
      echo "## Terminal logs (last 300 lines each)"
      echo
      for f in "$pushlog"/*.log; do
        [ -f "$f" ] || continue
        echo "<details><summary><code>$(basename "$f" .log)</code></summary>"
        echo
        echo '```'
        # strip ANSI colour codes so the log reads cleanly on GitHub
        sed 's/\x1b\[[0-9;]*[mGKHF]//g' "$f"
        echo '```'
        echo
        echo "</details>"
        echo
      done
    fi
  } > "$REPORT"

  echo
  echo "----------------------------------------------------------------"
  echo "Integration result: $result"
  echo "Report: $REPORT   (artifacts: ${#SHOTS[@]})"
  echo "----------------------------------------------------------------"
}

teardown() {
  for p in "${LAUNCH_PATTERNS[@]:-}"; do [ -n "$p" ] && pkill -f "$p" 2>/dev/null; done
  pkill -f gzserver 2>/dev/null; pkill -f gzclient 2>/dev/null
  pkill -f 'nav2_api_server' 2>/dev/null; pkill -f 'nav_gpt' 2>/dev/null
  pkill -f 'static_transform_publisher' 2>/dev/null
}

# Always finalize (collect data) first, then tear the stack down — even on Ctrl-C.
trap 'finalize; teardown' EXIT
# Turn Ctrl-C / kill into a clean exit so the EXIT trap always fires and the
# report + screenshots collected so far are never lost.
trap 'exit 130' INT TERM

echo "================================================================"
echo " nav2gpt guided integration — branch: $BRANCH  (model: $TURTLEBOT3_MODEL)"
echo " terminal: ${TERM_EMU:-none (background mode)}"
echo "================================================================"
echo "This walks the README launch steps. Follow each prompt, then confirm."
echo

capture_branch_graph

record "Terminal 1 — Gazebo + TurtleBot3"
open_stack_terminal "1-gazebo" ros2 launch ros2ai turtlebot3_navigation.launch.py
pause "Wait until Gazebo (and RViz) fully load and the house + robot are visible."
capture_screenshot "gazebo-loaded" gzclient Gazebo

record "Terminal 2 — Nav2"
open_stack_terminal "2-nav2" ros2 launch ros2ai navigation2.launch.py
pause "Wait until Nav2 lifecycle nodes are active (no more 'configuring' spam)."
capture_screenshot "nav2-active" rviz2 RViz rviz

# Localize: AMCL publishes map->odom only after it gets an initial pose. Without
# it, TF has no 'map' frame (goals hang) OR localization is wrong (robot plans
# around phantom walls). set_initial_pose.sh seeds AMCL at the robot's spawn.
record "Localization — seed AMCL initial pose"
open_stack_terminal "2b-initpose" bash "$REPO_ROOT/scripts/set_initial_pose.sh"
pause "In RViz, confirm 'Localization' is no longer 'unknown' and the robot sits on the map correctly. (Or use RViz '2D Pose Estimate' to nudge it.)"
capture_screenshot "localized" rviz2 RViz rviz

record "Terminal 3 — Nav2 API server"
open_stack_terminal "3-apiserver" ros2 run ros2ai nav2_api_server
pause "Wait for 'Nav2 API Server is ready'. (Little other output is normal — it then waits silently for goals.)"

record "Terminal 4 — LLM voice node"
open_stack_terminal "4-voice" ros2 run ros2ai Nav2Gpt
pause "Wait until the voice node prints 'connected to goToPose server'."
capture_screenshot "stack-up" gzclient Gazebo

feature_integration
capture_screenshot "feature-result" gzclient Gazebo
COMPLETED=1

echo
read -r -p "Run complete. Review the windows, then press Enter to tear the stack down... " </dev/tty

# The EXIT trap writes the report (with final screenshot + contact sheet) and
# tears the stack down — see finalize()/teardown() above.
if [ "${FEATURE_VERDICT:-no}" = "yes" ]; then exit 0; else exit 1; fi
