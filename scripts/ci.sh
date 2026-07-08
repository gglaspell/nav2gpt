#!/usr/bin/env bash
#
# ci.sh — the "run every time we push" driver (run INSIDE the Humble container).
#
#   bash scripts/ci.sh                     # test the newest-pushed branch (default)
#   bash scripts/ci.sh test/main-baseline  # test a SPECIFIC branch (e.g. main's baseline)
#
# Hard-syncs to the target branch, then runs all phases and pushes every report:
#   1. build_ws.sh          colcon build (+ build report)
#   2. run_tests.sh         pytest + main-vs-branch comparison
#   3. integration_test.sh  guided live run (Gazebo/Nav2/…) + integration report
#   4. push_report.sh       commit + push all new reports
#
# NOTE: the whole body is wrapped in main() and called on the last line, so bash
# parses the entire script into memory before running. That makes it safe for
# `git checkout` (below) to rewrite this very file mid-run — the in-memory copy
# keeps executing, and each phase is launched as a fresh process afterwards.

set -uo pipefail

main() {
  local SCRIPT_DIR REPO_ROOT B
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  cd "$REPO_ROOT"

  # Sync to the target branch: an explicit arg if given, else the newest pushed.
  git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
  git fetch --prune origin
  if [ -n "${1:-}" ]; then
    B="$1"
  else
    B="$(git for-each-ref --sort=-committerdate --format='%(refname:short)' refs/remotes/origin \
          | grep -vE '^origin$|/HEAD$' | head -n1 | sed 's#^origin/##')"
  fi
  if [ -z "$B" ]; then
    echo "Could not determine a branch to test." >&2
    return 2
  fi
  if ! git rev-parse --verify "origin/$B" >/dev/null 2>&1; then
    echo "Branch 'origin/$B' does not exist." >&2
    return 2
  fi
  echo ">> testing branch: $B"
  git checkout -B "$B" "origin/$B"

  # Phases — each runs regardless of the previous one's result (no set -e), so a
  # build failure still produces and pushes its report.
  bash scripts/build_ws.sh
  bash scripts/run_tests.sh
  bash scripts/integration_test.sh
  bash scripts/push_report.sh
}

main "$@"; exit $?
