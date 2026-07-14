#!/usr/bin/env bash
#
# run_tests.sh — run the project's tests and write a Markdown report.
#
# Meant to be run on the Linux test machine (the one with a full ROS 2 / Nav2 /
# Gazebo install). It is safe to run on a machine without ROS: pure-Python unit
# tests still run, and ROS-dependent checks are skipped and noted in the report.
#
# Usage:
#   ./scripts/run_tests.sh            # run everything, write reports/<branch>_<ts>.md
#   ./scripts/run_tests.sh -k pattern # forward extra args to pytest
#
# A report is always written, even when tests fail. The script exits non-zero
# if any test failed, so CI / a wrapper can react to it.

set -uo pipefail

# --- locate repo root (works no matter where the script is called from) ------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# A sourced ROS environment registers pytest plugins (e.g. launch_testing) via
# setuptools entry points. If pytest runs under a *different* Python than ROS's
# (e.g. Anaconda) with ROS on PYTHONPATH, autoloading those plugins crashes at
# startup (ModuleNotFoundError: lark) before any test is collected. We use no
# third-party pytest plugins, so disable autoload to stay isolated from ROS.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

# --- identity of this run ----------------------------------------------------
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
SANITIZED_BRANCH="$(echo "$BRANCH" | tr '/ ' '__')"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
HOSTNAME_STR="$(hostname 2>/dev/null || echo unknown)"

REPORT_DIR="$REPO_ROOT/reports"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/${SANITIZED_BRANCH}_${TS}.md"

# --- try to source a built ROS 2 workspace so ros2ai is importable -----------
ROS_STATUS="not sourced"
if [ -n "${ROS_DISTRO:-}" ]; then
  ROS_STATUS="ambient (ROS_DISTRO=$ROS_DISTRO)"
fi
WS_SETUP="$REPO_ROOT/nav2gpt_ws/install/setup.bash"
if [ -f "$WS_SETUP" ]; then
  # shellcheck disable=SC1090
  # colcon's setup.bash references unbound vars (e.g. COLCON_TRACE); relax
  # `set -u` around the source so it can't abort the run. build_ws.sh does the
  # same in a subshell — here the sourced env must persist for pytest, so the
  # toggle is inline.
  set +u
  source "$WS_SETUP" && ROS_STATUS="workspace sourced ($WS_SETUP)"
  set -u
fi

# --- collect environment info ------------------------------------------------
PY_VER="$(python3 --version 2>&1 || echo 'python3 not found')"
PYTEST_VER="$(python3 -m pytest --version 2>&1 | head -1 || echo 'pytest not found')"
UNAME_STR="$(uname -a 2>/dev/null || echo unknown)"

# --- run the tests -----------------------------------------------------------
LOG_FILE="$(mktemp)"
echo "Running tests on branch '$BRANCH' @ $SHA ..."
if [ -d "$REPO_ROOT/tests" ]; then
  python3 -m pytest "$REPO_ROOT/tests" -v "$@" 2>&1 | tee "$LOG_FILE"
  TEST_EXIT=${PIPESTATUS[0]}
else
  echo "no tests/ directory found — nothing to run" | tee "$LOG_FILE"
  TEST_EXIT=0
fi

# --- run the functional comparison against main ------------------------------
# Part of the default harness (honed per feature via feature_check()). Proves
# the branch's effect on robot behavior relative to main.
COMPARE_LOG="$(mktemp)"
if [ -x "$REPO_ROOT/scripts/compare_with_main.sh" ]; then
  echo
  echo "Comparing against main ..."
  "$REPO_ROOT/scripts/compare_with_main.sh" 2>&1 | tee "$COMPARE_LOG"
  COMPARE_EXIT=${PIPESTATUS[0]}
else
  echo "compare_with_main.sh not present — skipping comparison" | tee "$COMPARE_LOG"
  COMPARE_EXIT=0
fi

# --- overall result (pytest AND comparison must pass) ------------------------
if [ "$TEST_EXIT" -eq 0 ] && [ "$COMPARE_EXIT" -eq 0 ]; then
  RESULT="PASS ✅"
  OVERALL_EXIT=0
else
  RESULT="FAIL ❌ (pytest exit $TEST_EXIT, compare exit $COMPARE_EXIT)"
  OVERALL_EXIT=1
fi

# --- write the report --------------------------------------------------------
{
  echo "# Test report — \`$BRANCH\`"
  echo
  echo "| Field | Value |"
  echo "|-------|-------|"
  echo "| Result | **$RESULT** |"
  echo "| Branch | \`$BRANCH\` |"
  echo "| Commit | \`$SHA\` |"
  echo "| Run at (UTC) | $TS |"
  echo "| Host | $HOSTNAME_STR |"
  echo "| ROS | $ROS_STATUS |"
  echo "| Python | $PY_VER |"
  echo "| pytest | $PYTEST_VER |"
  echo "| Platform | \`$UNAME_STR\` |"
  echo
  echo "## pytest output"
  echo
  echo '```'
  cat "$LOG_FILE"
  echo '```'
  echo
  echo "## main-vs-branch functional comparison"
  echo
  echo '```'
  cat "$COMPARE_LOG"
  echo '```'
} > "$REPORT"

rm -f "$LOG_FILE" "$COMPARE_LOG"

echo
echo "----------------------------------------------------------------"
echo "Result:  $RESULT"
echo "Report:  $REPORT"
echo "Publish: ./scripts/push_report.sh   (optional — only if you want it on GitHub)"
echo "Visual:  ./scripts/debug_visual.sh  (watch the robot on the Linux box)"
echo "----------------------------------------------------------------"

exit "$OVERALL_EXIT"
