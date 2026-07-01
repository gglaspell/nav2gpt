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
./scripts/run_tests.sh        # runs everything, writes reports/<branch>_<ts>.md
./scripts/push_report.sh      # commits + pushes that report to GitHub
```
