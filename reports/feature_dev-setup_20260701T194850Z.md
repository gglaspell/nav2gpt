# Test report — `feature/dev-setup`

| Field | Value |
|-------|-------|
| Result | **PASS ✅** |
| Branch | `feature/dev-setup` |
| Commit | `5c2c17d` |
| Run at (UTC) | 20260701T194850Z |
| Host | bragg3d-Precision-7560 |
| ROS | ambient (ROS_DISTRO=jazzy) |
| Python | Python 3.13.9 |
| pytest | pytest 8.4.2 |
| Platform | `Linux bragg3d-Precision-7560 6.8.0-124-generic #124-Ubuntu SMP PREEMPT_DYNAMIC Tue May 26 13:00:45 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux` |

## pytest output

```
============================= test session starts ==============================
platform linux -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0 -- /home/bragg3d/anaconda3/bin/python3
cachedir: .pytest_cache
rootdir: /home/bragg3d/Desktop/nav2gpt-new
collecting ... collected 2 items

tests/test_smoke.py::test_repo_layout PASSED                             [ 50%]
tests/test_smoke.py::test_scripts_present PASSED                         [100%]

============================== 2 passed in 0.01s ===============================
```

## main-vs-branch functional comparison

```
================================================================
 compare: feature/dev-setup  vs  origin/main
================================================================

── Part 1: what changed vs main ─────────────────────────────────
Functional (robot/runtime) changes: 0
Tooling / docs changes: 15
    M  .gitignore
    M  README.md
    A  reports/.gitkeep
    A  reports/feature_dev-setup_20260701T190458Z.md
    A  reports/feature_dev-setup_20260701T190851Z.md
    A  reports/feature_dev-setup_20260701T193527Z.md
    A  requirements-dev.txt
    A  requirements.txt
    A  scripts/compare_with_main.sh
    A  scripts/debug_visual.sh
    A  scripts/integration_test.sh
    A  scripts/push_report.sh
    A  scripts/run_tests.sh
    A  tests/README.md
    A  tests/test_smoke.py
  => No functional changes — this branch is tooling-only (parity w/ main).

── Part 2: functional check (main vs branch) ────────────────────
  main   check: edfb0242cc0be9ed299c1b1282c65bd8ff20881d
  branch check: edfb0242cc0be9ed299c1b1282c65bd8ff20881d

VERDICT: PASS ✅  robot behavior identical to main (as expected for tooling-only).
```
