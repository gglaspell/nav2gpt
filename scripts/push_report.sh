#!/usr/bin/env bash
#
# push_report.sh — commit the latest test report and push it to GitHub.
#
# Run this right after run_tests.sh, on the Linux machine. It commits ONLY the
# report file(s) under reports/ (never your source changes) and pushes to the
# current branch on origin.
#
# Usage:
#   ./scripts/push_report.sh                 # push the newest report in reports/
#   ./scripts/push_report.sh reports/foo.md  # push a specific report

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

REPORT="${1:-}"
if [ -z "$REPORT" ]; then
  # newest file under reports/ (portable: sort by name — timestamps are lexical)
  REPORT="$(ls -1 reports/*.md 2>/dev/null | sort | tail -1 || true)"
fi

if [ -z "$REPORT" ] || [ ! -f "$REPORT" ]; then
  echo "No report found to push. Run ./scripts/run_tests.sh first." >&2
  exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SHA="$(git rev-parse --short HEAD)"

git add "$REPORT"
if git diff --cached --quiet; then
  echo "Report '$REPORT' is already committed — nothing to push."
  exit 0
fi

# Human-style commit message: describe the change, no attribution.
git commit -m "test: add report for ${BRANCH} @ ${SHA}"
git push origin "$BRANCH"

echo
echo "Pushed $REPORT to origin/$BRANCH"
