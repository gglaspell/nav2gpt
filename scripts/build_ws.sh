#!/usr/bin/env bash
#
# build_ws.sh — build the ROS 2 workspace and capture a build report.
#
# Runs `colcon build` in nav2gpt_ws (the same command as the README), tees the
# full output to your terminal AND into reports/<branch>_build_<ts>.md so build
# failures travel back to GitHub with everything else.
#
#   ./scripts/build_ws.sh
#
# SKIPS cleanly (writes a SKIP report, exit 0) when it can't build — no colcon or
# no ROS install (e.g. on the Mac) — so it's safe inside the universal paste.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
HOSTNAME_STR="$(hostname 2>/dev/null || echo unknown)"

REPORT_DIR="$REPO_ROOT/reports"; mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/$(echo "$BRANCH" | tr '/ ' '__')_build_${TS}.md"
WS="$REPO_ROOT/nav2gpt_ws"

# --- resolve the ROS underlay -------------------------------------------------
if [ -n "${ROS_DISTRO:-}" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
  ROS_SETUP="/opt/ros/$ROS_DISTRO/setup.bash"
else
  ROS_SETUP="$(ls -1 /opt/ros/*/setup.bash 2>/dev/null | head -1)"
fi

write_skip_report() {   # write_skip_report <reason>
  {
    echo "# Build report — \`$BRANCH\`"
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
  echo "Build SKIPPED: $1"
  echo "Report: $REPORT"
}

command -v colcon >/dev/null 2>&1 || { write_skip_report "colcon not installed (not a ROS build machine)"; exit 0; }
[ -n "$ROS_SETUP" ] || { write_skip_report "no ROS 2 install found under /opt/ros/*"; exit 0; }
[ -d "$WS/src" ]   || { write_skip_report "no workspace src at $WS/src"; exit 0; }

# --- distro guard: this repo targets the distro in the devcontainer Dockerfile.
# Building against a different distro (e.g. Jazzy on the host instead of the
# Humble container) is the classic failure — flag it loudly and in the report.
EXPECTED_DISTRO="$(grep -oiE 'osrf/ros:[a-z]+' "$REPO_ROOT/.devcontainer/Dockerfile" 2>/dev/null | head -1 | sed 's#.*:##')"
[ -n "$EXPECTED_DISTRO" ] || EXPECTED_DISTRO="humble"
CUR_DISTRO="${ROS_DISTRO:-$(basename "$(dirname "$ROS_SETUP")")}"
DISTRO_ROW="\`$CUR_DISTRO\` (matches target)"
if [ "$CUR_DISTRO" != "$EXPECTED_DISTRO" ]; then
  DISTRO_ROW="⚠️ \`$CUR_DISTRO\` — but repo targets \`$EXPECTED_DISTRO\` (run in the devcontainer!)"
  echo "================================================================"
  echo " ⚠️  WRONG ROS DISTRO"
  echo " Building against '$CUR_DISTRO' but this repo targets '$EXPECTED_DISTRO'."
  echo " This will almost certainly fail. Open the Humble devcontainer and run"
  echo " the paste in its terminal. Building anyway so the log is captured..."
  echo "================================================================"
fi

# --- build -------------------------------------------------------------------
echo "Building workspace ($WS) against $ROS_SETUP ..."
LOG_FILE="$(mktemp)"
# Subshell so 'set +u' (ROS setup scripts reference unbound vars) and cd stay local.
( set +u; source "$ROS_SETUP"; cd "$WS"; colcon build ) 2>&1 | tee "$LOG_FILE"
BUILD_EXIT=${PIPESTATUS[0]}

if [ "$BUILD_EXIT" -eq 0 ]; then
  RESULT="PASS ✅"
else
  RESULT="FAIL ❌ (colcon exit $BUILD_EXIT)"
fi

# --- write the report (cap very long logs to keep reports readable) ----------
LOG_LINES="$(wc -l < "$LOG_FILE" | tr -d ' ')"
{
  echo "# Build report — \`$BRANCH\`"
  echo
  echo "| Field | Value |"
  echo "|-------|-------|"
  echo "| Result | **$RESULT** |"
  echo "| Branch | \`$BRANCH\` |"
  echo "| Commit | \`$SHA\` |"
  echo "| Run at (UTC) | $TS |"
  echo "| Host | $HOSTNAME_STR |"
  echo "| ROS underlay | $ROS_SETUP |"
  echo "| Distro check | $DISTRO_ROW |"
  echo "| colcon | $(colcon version-check 2>/dev/null | head -1 || echo present) |"
  echo
  echo "## colcon build output"
  echo
  echo '```'
  if [ "$LOG_LINES" -gt 500 ]; then
    echo "(log truncated to the last 500 of $LOG_LINES lines)"
    tail -n 500 "$LOG_FILE"
  else
    cat "$LOG_FILE"
  fi
  echo '```'
} > "$REPORT"

rm -f "$LOG_FILE"

echo
echo "----------------------------------------------------------------"
echo "Build result: $RESULT"
echo "Report: $REPORT"
echo "----------------------------------------------------------------"

exit "$BUILD_EXIT"
