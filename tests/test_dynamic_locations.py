"""Unit tests for the dynamic-locations feature: intent parsing, the persistent
location store, pose math, and the spoken confirmations.

Pure logic — no ROS needed, runs anywhere. Imports the helpers directly from the
package source by path (same convention as test_result_reporting.py).
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "nav2gpt_ws" / "src" / "ros2ai" / "ros2ai"
sys.path.insert(0, str(PKG))

from intents import parse_intent, clean_name  # noqa: E402
from locations import (  # noqa: E402
    load_locations, save_location, nearest_room, destination_label,
    describe_rooms, DEFAULT_ROOMS)
from pose_utils import yaw_degrees  # noqa: E402
from status_report import (  # noqa: E402
    where_am_i_message, saved_location_message, need_name_message)


# --- intent parsing -------------------------------------------------------
def test_where_am_i_variants():
    for phrase in ("where am I?", "Where are we", "what room is this",
                   "which room am I in", "what is my location"):
        assert parse_intent(phrase)["kind"] == "whereami"


def test_save_with_name():
    intent = parse_intent("save this location as the office")
    assert intent == {"kind": "save", "name": "the office"}


def test_save_named_and_called_forms():
    assert parse_intent("save here called the lab")["name"] == "the lab"
    assert parse_intent("save the current spot named garage")["name"] == "garage"


def test_save_without_name_is_flagged():
    assert parse_intent("save this location") == {"kind": "save", "name": ""}


def test_plain_command_is_navigate():
    assert parse_intent("go to the kitchen")["kind"] == "navigate"
    assert parse_intent("")["kind"] == "navigate"


def test_clean_name_strips_punctuation_and_please():
    assert clean_name("The Office.") == "the office"
    assert clean_name("the  lab   please") == "the lab"


# --- persistent store -----------------------------------------------------
def test_load_defaults_when_no_file():
    rooms = load_locations(None)
    assert rooms["the kitchen"][:2] == (-4.0, 4.0)
    assert set(rooms) == set(DEFAULT_ROOMS)


def test_save_round_trip(tmp_path):
    path = str(tmp_path / "locations.json")
    save_location("the office", 1.5, -2.0, 90.0, path=path)
    rooms = load_locations(path)
    assert rooms["the office"] == (1.5, -2.0, 90.0)
    # defaults survive alongside the new entry
    assert "the kitchen" in rooms


def test_save_normalizes_name(tmp_path):
    path = str(tmp_path / "locations.json")
    save_location("  The  Office ", 1.0, 2.0, 0.0, path=path)
    assert "the office" in load_locations(path)


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "locations.json"
    path.write_text("{ not valid json ")
    assert set(load_locations(str(path))) == set(DEFAULT_ROOMS)


def test_nearest_room_within_tolerance():
    rooms = load_locations(None)
    assert nearest_room(rooms, -3.8, 4.1, tol=0.5) == "the kitchen"
    assert nearest_room(rooms, 0.0, 0.0, tol=0.5) is None


def test_destination_label_names_saved_room(tmp_path):
    path = str(tmp_path / "locations.json")
    save_location("the office", 1.5, -2.0, 90.0, path=path)
    assert destination_label(1.5, -2.0, path=path) == "the office"
    assert destination_label(9.0, 9.0, path=path) == "(9.0, 9.0)"


def test_destination_label_rounds_coordinate_fallback():
    # spoken aloud — a raw AMCL pose must not be read out to 15 decimals
    assert destination_label(-0.9999400283, 0.9999990005) == "(-1.0, 1.0)"


# --- LLM room description -------------------------------------------------
def test_describe_rooms_renders_clean_numbers():
    line = describe_rooms({"the kitchen": (-4.0, 4.0, 180.0)})
    assert line == "the coordinates of the kitchen is x: -4, y: 4, theta: 180"


def test_describe_rooms_rounds_noisy_floats():
    # a pose straight off AMCL shouldn't litter the prompt with 15 digits
    line = describe_rooms({"the desk": (-0.9999419778, 0.99999899, -2.76e-08)})
    assert line == "the coordinates of the desk is x: -1, y: 1, theta: 0"


# --- pose math ------------------------------------------------------------
def test_yaw_of_identity_is_zero():
    assert abs(yaw_degrees(0.0, 0.0, 0.0, 1.0)) < 1e-9


def test_yaw_of_quarter_turn_is_ninety():
    # quaternion for +90 deg about Z: (0,0,sin45,cos45)
    s = 2 ** -0.5
    assert abs(yaw_degrees(0.0, 0.0, s, s) - 90.0) < 1e-6


# --- spoken confirmations -------------------------------------------------
def test_where_am_i_names_a_room():
    assert where_am_i_message("the kitchen") == "You are in the kitchen."


def test_where_am_i_reads_coordinates():
    assert where_am_i_message("(1.0, 2.0)") == "You are at (1.0, 2.0)."


def test_saved_message_reports_name_and_position():
    msg = saved_location_message("the office", 1.234, -2.0)
    assert "the office" in msg
    assert "1.23" in msg


def test_need_name_message_is_actionable():
    assert "name" in need_name_message().lower()
