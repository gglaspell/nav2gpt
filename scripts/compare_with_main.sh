#!/usr/bin/env bash
#
# compare_with_main.sh — show what THIS feature branch changes relative to main,
# and run a per-feature functional check against both to prove it still works.
#
#   ./scripts/compare_with_main.sh
#
# Two parts:
#   1. STATIC — categorize the diff vs main into "functional" (robot code)
#      vs "tooling/docs". A tooling-only branch (like dev-setup) should show ZERO
#      functional changes  ->  functional parity with main.
#   2. FUNCTIONAL — run feature_check() against a clean checkout of main
#      and against this branch, then diff the results. Hone feature_check() per
#      feature so it exercises exactly the behavior this branch adds/changes.
#
# Appends its verdict to reports/ via run_tests.sh conventions is NOT done here;
# this script prints to stdout and exits non-zero if the functional check fails.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
BASE="main"   # local branch — the comparison stays offline

# Path prefixes that constitute actual robot/runtime behavior. Anything else
# (scripts/, tests/, reports/, README, requirements, .project) is tooling/docs.
FUNCTIONAL_PREFIXES=("nav2gpt_ws/" ".devcontainer/")

is_functional() {   # is_functional <path> -> 0 if it affects robot behavior
  local p="$1"
  for pre in "${FUNCTIONAL_PREFIXES[@]}"; do
    [[ "$p" == "$pre"* ]] && return 0
  done
  return 1
}

# ── FEATURE HOOK ─────────────────────────────────────────────────────────────
# Given a checked-out copy of the repo at $1, produce a normalized, deterministic
# description of the behavior under test on stdout. The script runs this once for
# main and once for this branch and diffs the two outputs.
#
# dev-setup adds no robot behavior, so its check just confirms the robot source
# is untouched — parity is already proven by Part 1. Later feature branches
# replace the body below with a real probe, e.g. for feature/nav-feedback:
#
#     # start the api server, call goToPose with an unreachable goal,
#     # print the returned status string:
#     ( cd "$1/nav2gpt_ws" && ... ros2 service call ... ) | grep -o 'status:.*'
#
feature_check() {
  local tree="$1"
  # Content hash of every FUNCTIONAL_PREFIXES path = a proxy for "does the
  # robot's actual runtime behavior differ?". Uses git's own tree object ids
  # (deterministic, portable, no sha1sum/shasum dependency). Must cover the
  # same paths as FUNCTIONAL_PREFIXES above, or a change there won't show up
  # here and Part 1/Part 2 will disagree.
  local pre id
  for pre in "${FUNCTIONAL_PREFIXES[@]:-}"; do
    [ -n "$pre" ] || continue
    id="$(git -C "$tree" rev-parse "HEAD:${pre%/}" 2>/dev/null)"
    [ -n "$id" ] && echo "$pre=$id"
  done
}
# ─────────────────────────────────────────────────────────────────────────────

echo "================================================================"
echo " compare: $BRANCH  vs  $BASE"
echo "================================================================"

if ! git rev-parse --verify "$BASE" >/dev/null 2>&1; then
  echo "Cannot resolve local branch '$BASE'. Create it, e.g.: git branch $BASE origin/$BASE" >&2
  exit 2
fi

# ── Part 1: static diff, categorized ─────────────────────────────────────────
echo
echo "── Part 1: what changed vs main ─────────────────────────────────"
FUNC_CHANGES=()
TOOL_CHANGES=()
while IFS=$'\t' read -r status path; do
  [ -z "${path:-}" ] && continue
  if is_functional "$path"; then
    FUNC_CHANGES+=("$status  $path")
  else
    TOOL_CHANGES+=("$status  $path")
  fi
done < <(git diff --name-status "$BASE"...HEAD)

echo "Functional (robot/runtime) changes: ${#FUNC_CHANGES[@]}"
for c in "${FUNC_CHANGES[@]:-}"; do [ -n "$c" ] && echo "    $c"; done
echo "Tooling / docs changes: ${#TOOL_CHANGES[@]}"
for c in "${TOOL_CHANGES[@]:-}"; do [ -n "$c" ] && echo "    $c"; done

if [ "${#FUNC_CHANGES[@]}" -eq 0 ]; then
  echo "  => No functional changes — this branch is tooling-only (parity w/ main)."
fi

# ── Part 2: functional check on both trees ───────────────────────────────────
echo
echo "── Part 2: functional check (main vs branch) ────────────────────"
WORKTREE="$(mktemp -d)"
cleanup() { git worktree remove --force "$WORKTREE" 2>/dev/null; rmdir "$WORKTREE" 2>/dev/null; }
trap cleanup EXIT

if git worktree add --quiet --detach "$WORKTREE" "$BASE" 2>/dev/null; then
  MAIN_RESULT="$(feature_check "$WORKTREE")"
else
  echo "  (could not create worktree for $BASE; skipping main-side check)"
  MAIN_RESULT="<unavailable>"
fi
BRANCH_RESULT="$(feature_check "$REPO_ROOT")"

echo "  main   check: $MAIN_RESULT"
echo "  branch check: $BRANCH_RESULT"

echo
if [ "${#FUNC_CHANGES[@]}" -eq 0 ]; then
  # Tooling-only branch: results MUST match (robot code identical).
  if [ "$MAIN_RESULT" = "$BRANCH_RESULT" ]; then
    echo "VERDICT: PASS ✅  robot behavior identical to main (as expected for tooling-only)."
    exit 0
  else
    echo "VERDICT: FAIL ❌  robot source differs from main but no functional diff was detected." >&2
    exit 1
  fi
else
  # Feature branch: results are EXPECTED to differ — the check documents how.
  if [ "$MAIN_RESULT" != "$BRANCH_RESULT" ]; then
    echo "VERDICT: PASS ✅  behavior changed vs main, as expected for this feature."
    echo "         (Review the two results above to confirm the change is correct.)"
    exit 0
  else
    echo "VERDICT: WARN ⚠️  functional files changed but feature_check() saw no"
    echo "         behavioral difference. Hone feature_check() to probe the new behavior." >&2
    exit 1
  fi
fi
