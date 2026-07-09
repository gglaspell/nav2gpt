"""Unit tests for the nav-feedback result-reporting logic.

Pure logic — no ROS needed, runs anywhere. Imports the status_report helper
directly from the package source by path.
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "nav2gpt_ws" / "src" / "ros2ai" / "ros2ai"
sys.path.insert(0, str(PKG))

from status_report import status_message  # noqa: E402


def test_success_reads_as_arrival():
    msg = status_message("SUCCEEDED", -4, 4)
    assert "reached" in msg.lower()
    assert "(-4, 4)" in msg


def test_failure_names_the_status():
    msg = status_message("FAILED", -4, 4)
    assert "could not reach" in msg.lower()
    assert "FAILED" in msg


def test_rejected_is_distinct_from_generic_failure():
    assert "rejected" in status_message("REJECTED", 1, 1).lower()


def test_canceled_is_distinct():
    assert "canceled" in status_message("CANCELED", 0, 0).lower()
