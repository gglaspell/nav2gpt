"""Unit tests for the nav-feedback result-reporting, progress, and destination
labeling logic.

Pure logic — no ROS needed, runs anywhere. Imports the helpers directly from the
package source by path.
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "nav2gpt_ws" / "src" / "ros2ai" / "ros2ai"
sys.path.insert(0, str(PKG))

from status_report import status_message, progress_phrase  # noqa: E402
from locations import destination_label  # noqa: E402
from speech import speak  # noqa: E402


# --- destination labeling -------------------------------------------------
def test_known_room_is_named():
    assert destination_label(-4.0, 4.0) == "the kitchen"
    assert destination_label(3.0, 4.0) == "the bedroom"


def test_near_a_room_still_names_it():
    assert destination_label(-3.7, 4.2) == "the kitchen"   # within tolerance


def test_unknown_point_falls_back_to_coordinates():
    assert destination_label(0.0, 0.0) == "(0.0, 0.0)"


# --- result messages ------------------------------------------------------
def test_success_reads_as_arrival():
    assert "reached the kitchen" in status_message("SUCCEEDED", "the kitchen").lower()


def test_failure_names_status_and_destination():
    msg = status_message("FAILED", "the kitchen")
    assert "could not reach the kitchen" in msg.lower()
    assert "FAILED" in msg


def test_rejected_is_distinct():
    assert "rejected" in status_message("REJECTED", "(1, 1)").lower()


def test_canceled_is_distinct():
    assert "canceled" in status_message("CANCELED", "the bedroom").lower()


# --- spoken progress names the destination --------------------------------
def test_progress_announces_halfway_to_named_destination_once():
    seen = set()
    assert progress_phrase(4.0, 10.0, seen, "the kitchen") == "Halfway to the kitchen."
    assert progress_phrase(3.0, 10.0, seen, "the kitchen") is None   # already said


def test_progress_silent_before_halfway():
    assert progress_phrase(9.0, 10.0, set(), "the kitchen") is None


def test_progress_announces_near_at_90pct():
    assert progress_phrase(0.5, 10.0, {"half"}, "the kitchen") == "Almost at the kitchen."


def test_progress_handles_unknown_start_distance():
    assert progress_phrase(5.0, 0.0, set(), "the kitchen") is None
    assert progress_phrase(5.0, None, set(), "the kitchen") is None


# --- TTS is best-effort ---------------------------------------------------
def test_speak_returns_text_and_never_raises():
    assert speak("hello") == "hello"
    assert speak("") == ""
