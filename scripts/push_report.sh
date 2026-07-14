#!/usr/bin/env bash
#
# push_report.sh — OPTIONAL: publish the latest test report(s) to GitHub.
#
# Not part of the normal local loop (ci.sh no longer calls it). Run it by hand
# only when you actually want a report on the remote. It commits ONLY the report
# file(s) under reports/ (never your source changes) and pushes the current branch.
#
# Usage:
#   ./scripts/push_report.sh                 # push ALL new reports in reports/
#   ./scripts/push_report.sh reports/foo.md  # push a specific report

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Stage a specific report if given, otherwise every new/changed report. This
# picks up both the automated (run_tests.sh) and integration (integration_test.sh)
# reports in one commit.
if [ -n "${1:-}" ]; then
  [ -f "$1" ] || { echo "No such report: $1" >&2; exit 1; }
  git add "$1"
else
  git add reports/
fi

if git diff --cached --quiet; then
  echo "No new reports to push. Run ./scripts/run_tests.sh first."
  exit 0
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SHA="$(git rev-parse --short HEAD)"

# Human-style commit message: describe the change, no attribution.
git commit -m "test: add report(s) for ${BRANCH} @ ${SHA}"
git push origin "$BRANCH"

echo
echo "Pushed report(s) to origin/$BRANCH"
