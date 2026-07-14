# Tests

Plain `pytest` tests that run on the Linux test machine (and, where possible,
anywhere — pure-Python logic tests don't need ROS).

## Convention

- One test module per feature branch: `test_<feature>.py`
  (e.g. `test_result_reporting.py`, `test_dynamic_locations.py`).
- Tests that need a live ROS graph / Nav2 / Gazebo should be guarded so they
  **skip** (not fail) when ROS isn't available, e.g.:

  ```python
  import pytest
  pytest.importorskip("rclpy")
  ```

- Prefer factoring pure logic (parsing, status strings, JSON persistence,
  coordinate lookup) out of the ROS nodes so it can be unit-tested without a
  running robot.

## Running

```bash
./scripts/run_tests.sh        # pytest + main-vs-branch comparison -> reports/<branch>_<ts>.md
./scripts/push_report.sh      # commits + pushes that report to GitHub
./scripts/debug_visual.sh     # (Linux) bring the stack up and watch the robot move
```

## Per-feature harness parts

Three things get honed on every feature branch so the harness actually exercises
the new behavior:

1. `tests/test_<feature>.py` — automated assertions for the feature's logic.
2. `feature_check()` in `scripts/compare_with_main.sh` — a functional probe run
   against both `main` and the branch; their outputs are diffed to show the
   change (or prove parity for tooling-only branches).
3. `feature_demo_hint()` in `scripts/debug_visual.sh` — what to do and watch for
   when eyeballing the feature live in Gazebo.
