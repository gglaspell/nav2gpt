"""Smoke tests — prove the harness works before any feature tests exist.

These do not require ROS. They confirm the repo layout is intact so a report
generated on the Linux machine is meaningful even on the very first run.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repo_layout():
    """Core source files exist where the harness expects them."""
    pkg = REPO_ROOT / "nav2gpt_ws" / "src" / "ros2ai" / "ros2ai"
    assert (pkg / "nav2_api_server.py").is_file()
    assert (pkg / "nav_gpt.py").is_file()


def test_scripts_present():
    scripts = REPO_ROOT / "scripts"
    assert (scripts / "run_tests.sh").is_file()
    assert (scripts / "push_report.sh").is_file()
