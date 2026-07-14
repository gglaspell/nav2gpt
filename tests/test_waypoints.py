"""Unit tests for the waypoints feature: execution-mode classification from
phrasing and the spoken plan/summary for followWaypoints / goThroughPoses routes.

Pure logic — no ROS needed. Imports the helpers directly from the package source
by path (same convention as test_multi_step_nav.py).
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "nav2gpt_ws" / "src" / "ros2ai" / "ros2ai"
sys.path.insert(0, str(PKG))

from routing import (  # noqa: E402
    resolve_route, route_mode, waypoint_plan_phrase, waypoint_summary,
    travel_headings, through_fallback_phrase)

ROOMS = {
    "the kitchen": (-4.0, 4.0, 180.0),
    "the bedroom": (3.0, 4.0, 0.0),
    "the office": (1.0, -2.0, 90.0),
}


# --- mode classification --------------------------------------------------
def test_explicit_continuous_phrasing_is_through():
    # only an explicit "don't stop" asks for the continuous pass
    for phrase in ("go through the kitchen and the bedroom without stopping",
                   "pass through the kitchen and the bedroom",
                   "do the kitchen and the bedroom in one pass",
                   "drive straight through the kitchen and the bedroom"):
        assert route_mode(phrase) == "through", phrase


def test_visit_patrol_tour_are_waypoints():
    # visiting rooms wants a stop at each, so these use the waypoint follower
    for phrase in ("visit the kitchen and the bedroom",
                   "patrol the kitchen and the bedroom",
                   "take a tour of the kitchen and the bedroom",
                   "sweep the kitchen then the bedroom",
                   "follow the waypoints to the kitchen and the bedroom",
                   "hit the way points kitchen bedroom"):
        assert route_mode(phrase) == "waypoints", phrase


def test_plain_sequence_is_steps():
    assert route_mode("go to the kitchen, then the bedroom") == "steps"
    assert route_mode("the kitchen and the bedroom") == "steps"
    assert route_mode("") == "steps"


def test_throughout_does_not_false_match_through():
    # a word merely containing "through" must not trip the through mode
    assert route_mode("scan throughout the kitchen and the bedroom") == "steps"


def test_mode_composes_with_resolution():
    cmd = "go through the kitchen and the bedroom without stopping"
    route = resolve_route(cmd, ROOMS)
    assert [s["name"] for s in route] == ["the kitchen", "the bedroom"]
    assert route_mode(cmd) == "through"


def test_through_fallback_phrase_mentions_the_retry():
    phrase = through_fallback_phrase().lower()
    assert "continuous pass" in phrase and "in turn" in phrase


# --- spoken plan ----------------------------------------------------------
def test_plan_phrase_through_vs_waypoints():
    names = ["the kitchen", "the bedroom"]
    assert waypoint_plan_phrase(names, "through") == \
        "Going through the kitchen and the bedroom without stopping."
    assert waypoint_plan_phrase(names, "waypoints") == \
        "Following waypoints through the kitchen and the bedroom."


def test_plan_phrase_oxford_join_for_three():
    names = ["the kitchen", "the bedroom", "the office"]
    assert waypoint_plan_phrase(names, "through") == \
        "Going through the kitchen, the bedroom, and the office without stopping."


def test_plan_phrase_single_name():
    assert waypoint_plan_phrase(["the kitchen"], "through") == \
        "Going through the kitchen without stopping."


# --- spoken summary -------------------------------------------------------
def test_summary_success_through():
    assert waypoint_summary("SUCCEEDED", ["the kitchen", "the bedroom"], "through") == \
        "Tour complete — passed through the kitchen and the bedroom."


def test_summary_success_waypoints():
    assert waypoint_summary("SUCCEEDED", ["the kitchen", "the bedroom"], "waypoints") == \
        "Reached every waypoint: the kitchen and the bedroom."


def test_summary_reports_a_failure_status():
    assert waypoint_summary("CANCELED", ["the kitchen"], "through") == \
        "Route ended before finishing: status CANCELED."
    assert "FAILED" in waypoint_summary("FAILED", ["the kitchen"], "waypoints")


# --- pass-through heading correction --------------------------------------
def test_travel_headings_points_intermediate_at_next():
    # kitchen (-4,4, stored 180 deg) -> bedroom (3,4): the intermediate kitchen
    # should face east (0 deg, toward the bedroom), not its stored 180 deg.
    route = [{"name": "the kitchen", "x": -4.0, "y": 4.0, "theta": 180.0},
             {"name": "the bedroom", "x": 3.0, "y": 4.0, "theta": 0.0}]
    out = travel_headings(route)
    assert out[0]["theta"] == 0.0          # re-aimed toward the next stop
    assert out[1]["theta"] == 0.0          # final stop keeps its stored heading


def test_travel_headings_keeps_final_stored_heading():
    route = [{"name": "a", "x": 0.0, "y": 0.0, "theta": 10.0},
             {"name": "b", "x": 0.0, "y": 5.0, "theta": 123.0}]
    out = travel_headings(route)
    assert out[0]["theta"] == 90.0         # due north to b
    assert out[1]["theta"] == 123.0        # unchanged final heading


def test_travel_headings_does_not_mutate_input():
    route = [{"name": "a", "x": 0.0, "y": 0.0, "theta": 10.0},
             {"name": "b", "x": 5.0, "y": 0.0, "theta": 20.0}]
    travel_headings(route)
    assert route[0]["theta"] == 10.0       # original left intact

def test_travel_headings_single_stop_unchanged():
    route = [{"name": "a", "x": 1.0, "y": 2.0, "theta": 45.0}]
    assert travel_headings(route) == route
