#!/usr/bin/env bash
#
# ci.sh — local build/test/report driver (run INSIDE the Humble container).
#
#   bash scripts/ci.sh                     # test the current branch (working tree as-is)
#   bash scripts/ci.sh test/main-baseline  # switch to a local branch first, then test
#
# Runs every phase against the local checkout and leaves the reports under
# reports/ for review on this machine. Nothing is fetched from or pushed to a
# remote — the whole loop stays local.
#   1. build_ws.sh          colcon build (+ build report)
#   2. run_tests.sh         pytest + branch-vs-main comparison
#   3. integration_test.sh  guided live run (Gazebo/Nav2/…) + integration report
#
# NOTE: the body is wrapped in main() and called on the last line, so bash parses
# the whole script into memory before running. That keeps it safe for the branch
# switch below to rewrite this very file mid-run — the in-memory copy keeps going.

set -uo pipefail

main() {
  local SCRIPT_DIR REPO_ROOT B
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  cd "$REPO_ROOT"

  # Test an explicit branch if named, otherwise whatever is already checked out.
  # No network: a named branch is taken from a local ref, or created from the
  # cached origin/<branch> tracking ref if that's all we have.
  if [ -n "${1:-}" ]; then
    B="$1"
    if git rev-parse --verify "refs/heads/$B" >/dev/null 2>&1; then
      echo ">> switching to branch: $B"
      git checkout "$B"
    elif git rev-parse --verify "refs/remotes/origin/$B" >/dev/null 2>&1; then
      echo ">> creating local branch $B from cached origin/$B"
      git checkout -b "$B" "origin/$B"
    else
      echo "No local branch '$B' (and no cached origin/$B to base it on)." >&2
      return 2
    fi
  else
    B="$(git rev-parse --abbrev-ref HEAD)"
  fi
  echo ">> testing branch: $B"

  # Phases — each runs regardless of the previous one's result (no set -e), so a
  # build failure still produces its report.
  bash scripts/build_ws.sh
  bash scripts/run_tests.sh
  bash scripts/integration_test.sh

  echo
  echo ">> done — reports are under reports/ (logs under reports/logs/) on this machine."
}

main "$@"; exit $?
