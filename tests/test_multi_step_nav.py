"""Unit tests for the multi-step navigation feature: multi-destination route
resolution, the spoken step/summary phrasing, and the short-term route memory.

Pure logic — no ROS needed, runs anywhere. Imports the helpers directly from the
package source by path (same convention as test_dynamic_locations.py).
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "nav2gpt_ws" / "src" / "ros2ai" / "ros2ai"
sys.path.insert(0, str(PKG))

from routing import (  # noqa: E402
    resolve_route, step_announcement, route_summary, followup_ack)
from route_memory import RouteMemory  # noqa: E402

ROOMS = {
    "the kitchen": (-4.0, 4.0, 180.0),
    "the bedroom": (3.0, 4.0, 0.0),
    "the office": (1.0, -2.0, 90.0),
}


def _names(route):
    return [stop["name"] for stop in route]


# --- route resolution -----------------------------------------------------
def test_two_stops_in_order():
    route = resolve_route("go to the kitchen, then the bedroom", ROOMS)
    assert _names(route) == ["the kitchen", "the bedroom"]
    # coordinates and heading come through from the store
    assert (route[0]["x"], route[0]["y"], route[0]["theta"]) == (-4.0, 4.0, 180.0)


def test_wording_order_drives_route_order():
    route = resolve_route("go to the bedroom and then the kitchen", ROOMS)
    assert _names(route) == ["the bedroom", "the kitchen"]


def test_three_stops():
    route = resolve_route(
        "kitchen, then the office, and finally the bedroom", ROOMS)
    assert _names(route) == ["the kitchen", "the office", "the bedroom"]


def test_matches_with_or_without_the():
    assert _names(resolve_route("kitchen then bedroom", ROOMS)) == \
        ["the kitchen", "the bedroom"]


def test_unknown_words_are_ignored():
    route = resolve_route("go to the attic then the kitchen", ROOMS)
    assert _names(route) == ["the kitchen"]


def test_no_known_room_is_empty():
    assert resolve_route("take me to the garden", ROOMS) == []
    assert resolve_route("", ROOMS) == []
    assert resolve_route(None, ROOMS) == []


def test_immediate_repeat_is_collapsed():
    route = resolve_route("go to the kitchen and stay in the kitchen", ROOMS)
    assert _names(route) == ["the kitchen"]


def test_genuine_revisit_is_kept():
    route = resolve_route(
        "kitchen, then bedroom, then back to the kitchen", ROOMS)
    assert _names(route) == ["the kitchen", "the bedroom", "the kitchen"]


def test_longer_name_wins_overlapping_span():
    rooms = {"the room": (0.0, 0.0, 0.0), "the living room": (2.0, 2.0, 0.0)}
    assert _names(resolve_route("go to the living room", rooms)) == \
        ["the living room"]


def test_saved_room_is_routable():
    rooms = dict(ROOMS)
    rooms["the lab"] = (5.0, 5.0, 45.0)
    assert _names(resolve_route("the lab then the kitchen", rooms)) == \
        ["the lab", "the kitchen"]


def test_room_without_theta_defaults_to_zero():
    route = resolve_route("go to the dock then the kitchen",
                          {"the dock": (1.0, 1.0)})
    assert route[0]["theta"] == 0.0


# --- spoken step + summary phrasing ---------------------------------------
def test_step_announcement_single_vs_multi():
    assert step_announcement(1, 1, "the kitchen") == "Heading to the kitchen."
    assert step_announcement(2, 3, "the office") == \
        "Heading to the office, stop 2 of 3."


def test_summary_all_stops_reached():
    assert route_summary(["the kitchen", "the bedroom"], None, 2) == \
        "Route complete — visited the kitchen, then the bedroom."


def test_summary_stops_on_failure_names_both():
    msg = route_summary(["the kitchen"], "the bedroom", 2)
    assert "the kitchen" in msg and "couldn't reach the bedroom" in msg


def test_summary_first_stop_fails():
    assert route_summary([], "the kitchen", 2) == "Couldn't reach the kitchen."


def test_followup_ack_wording():
    assert "again" in followup_ack("repeat").lower()
    assert "reverse" in followup_ack("reverse").lower()


# --- route memory ---------------------------------------------------------
def test_memory_empty_returns_none():
    assert RouteMemory().resolve_followup("do that again") is None


def test_memory_repeat_returns_same_route():
    mem = RouteMemory()
    mem.remember(resolve_route("kitchen then bedroom", ROOMS))
    fu = mem.resolve_followup("do that again")
    assert fu["mode"] == "repeat"
    assert _names(fu["route"]) == ["the kitchen", "the bedroom"]


def test_memory_reverse_flips_order():
    mem = RouteMemory()
    mem.remember(resolve_route("kitchen then bedroom", ROOMS))
    fu = mem.resolve_followup("now do it in reverse")
    assert fu["mode"] == "reverse"
    assert _names(fu["route"]) == ["the bedroom", "the kitchen"]


def test_memory_ignores_a_non_followup():
    mem = RouteMemory()
    mem.remember(resolve_route("kitchen then bedroom", ROOMS))
    assert mem.resolve_followup("go to the office") is None


def test_memory_remember_ignores_empty():
    mem = RouteMemory()
    mem.remember(resolve_route("kitchen then bedroom", ROOMS))
    mem.remember([])  # a failed parse must not wipe usable memory
    assert mem.resolve_followup("again") is not None


def test_memory_returns_a_copy():
    mem = RouteMemory()
    mem.remember(resolve_route("kitchen then bedroom", ROOMS))
    fu = mem.resolve_followup("again")
    fu["route"][0]["x"] = 999.0
    # mutating the handed-out route must not corrupt what's remembered
    assert mem.resolve_followup("again")["route"][0]["x"] == -4.0
