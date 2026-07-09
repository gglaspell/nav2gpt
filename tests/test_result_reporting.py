"""Unit tests for the nav-feedback result-reporting logic.

Pure logic — no ROS needed, runs anywhere. Imports the status_report helper
directly from the package source by path.
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "nav2gpt_ws" / "src" / "ros2ai" / "ros2ai"
sys.path.insert(0, str(PKG))

from status_report import status_message, progress_phrase  # noqa: E402
from speech import speak  # noqa: E402


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


def test_progress_announces_halfway_once():
    seen = set()
    assert progress_phrase(4.0, 10.0, seen) == "Halfway to the goal."   # 60% done
    assert progress_phrase(3.0, 10.0, seen) is None                     # already said


def test_progress_silent_before_halfway():
    assert progress_phrase(9.0, 10.0, set()) is None


def test_progress_announces_near_at_90pct():
    assert "almost" in (progress_phrase(0.5, 10.0, {"half"}) or "").lower()


def test_progress_handles_unknown_start_distance():
    assert progress_phrase(5.0, 0.0, set()) is None
    assert progress_phrase(5.0, None, set()) is None


def test_speak_returns_text_and_never_raises():
    assert speak("hello") == "hello"
    assert speak("") == ""
