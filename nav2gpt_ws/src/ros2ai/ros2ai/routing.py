"""Multi-stop route resolution and spoken route feedback (pure; no ROS imports).

Turns one spoken command that names several destinations in order ("go to the
kitchen, then the bedroom") into an ordered list of goals resolved against the
known-room store, and phrases the per-stop and end-of-route announcements.

Kept ROS-free on purpose so it unit-tests without a running robot
(see tests/test_multi_step_nav.py); the node supplies the room store and drives
goToPose for each stop.
"""
import math
import re


def _keyword(name):
    """The part of a room name to match in speech: the name with a leading
    'the ' dropped ('the kitchen' -> 'kitchen'), lowercased and space-collapsed.
    Matching the keyword rather than the full name lets "kitchen" resolve whether
    the speaker says "kitchen" or "the kitchen"."""
    n = " ".join(str(name).lower().split())
    return n[4:] if n.startswith("the ") else n


def resolve_route(transcript, rooms):
    """Ordered list of goal dicts for the known rooms named in `transcript`.

    `rooms` is ``name -> (x, y[, theta])`` from the location store. Each room
    whose keyword is spoken becomes a stop ``{"name", "x", "y", "theta"}``, in
    the order the names appear; an immediate repeat of the same room is collapsed
    (so "stay in the kitchen" after "the kitchen" is one stop, but a genuine
    revisit later in the route is kept). Unknown words are ignored. Returns [] if
    no known room is named.

    When two rooms match the same span — a saved "living room" versus a "room" —
    the longer name claims it, so the more specific room wins.
    """
    text = (transcript or "").lower()
    matches = []
    for name, pose in rooms.items():
        kw = _keyword(name)
        if not kw:
            continue
        for m in re.finditer(r"\b" + re.escape(kw) + r"\b", text):
            matches.append((m.start(), m.end(), name, pose))
    # Earliest first; on a tie the longer keyword wins the overlapping span.
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    claimed = []
    route = []
    for start, end, name, pose in matches:
        if any(start < c_end and end > c_start for c_start, c_end in claimed):
            continue
        claimed.append((start, end))
        if route and route[-1]["name"] == name:
            continue
        theta = pose[2] if len(pose) > 2 else 0.0
        route.append({"name": name, "x": pose[0], "y": pose[1], "theta": theta})
    return route


def travel_headings(route):
    """Copy of `route` with each intermediate stop's heading pointing at the next
    stop (direction of travel); the final stop keeps its own stored heading.

    goThroughPoses passes *through* intermediate poses without stopping, so a
    stored arrival heading there (e.g. the kitchen's 180 deg, facing back the way
    the robot came) forces an infeasible cusp — arrive facing west, then reverse
    to head east to the next room. Facing travel direction keeps the pass smooth.
    Sequential goToPose and followWaypoints stop and reorient at each stop, so
    they keep the stored headings; only the pass-through mode needs this.
    """
    out = [dict(stop) for stop in route]
    for i in range(len(out) - 1):
        dx = out[i + 1]["x"] - out[i]["x"]
        dy = out[i + 1]["y"] - out[i]["y"]
        if dx or dy:
            out[i]["theta"] = math.degrees(math.atan2(dy, dx))
    return out


def step_announcement(index, total, name):
    """What to say when starting a stop. `index` is 1-based. A single-stop route
    doesn't need the "stop 1 of 1" bookkeeping."""
    if total <= 1:
        return f"Heading to {name}."
    return f"Heading to {name}, stop {index} of {total}."


def route_summary(reached, failed, total):
    """Spoken wrap-up for a route.

    `reached` are the stop names reached, in order; `failed` is the stop that
    could not be reached (or None if the route finished); `total` is how many
    stops were planned.
    """
    if failed is None:
        if not reached:
            return "Nothing to do."
        if len(reached) == 1:
            return f"Done — reached {reached[0]}."
        return f"Route complete — visited {_join_stops(reached)}."
    if reached:
        return f"Stopped at {reached[-1]} — couldn't reach {failed}."
    return f"Couldn't reach {failed}."


def followup_ack(mode):
    """What to say when replaying a remembered route (see route_memory)."""
    if mode == "reverse":
        return "Retracing the last route in reverse."
    return "Running the last route again."


# Only an explicit "don't stop" phrasing asks for the continuous pass
# (goThroughPoses). Visiting rooms — even "patrol"/"tour" — wants a stop at each,
# so those go to the waypoint follower, which is reliable through the house
# doorways where a continuous pass wedges.
_THROUGH_RE = re.compile(
    r"\b(?:go(?:ing)? through|pass(?:ing)? through|without stopping|non-?stop|"
    r"continuous(?:ly)?|in one (?:pass|go)|straight through)\b", re.IGNORECASE)
# "waypoints / visit / patrol / tour" -> Nav2's waypoint follower (followWaypoints).
_WAYPOINTS_RE = re.compile(
    r"\b(?:way\s?points?|visit|patrol|tour|sweep|one by one|stop at each|"
    r"follow the route)\b", re.IGNORECASE)


def route_mode(transcript):
    """Which Nav2 execution mode a multi-room command asks for:

      'through'   -> goThroughPoses  (one continuous pass, don't fully stop) —
                     only for an explicit "go through ... without stopping".
      'waypoints' -> followWaypoints (Nav2 visits each in turn) — "visit ...",
                     "patrol ...", "tour ...", "follow the waypoints ...".
      'steps'     -> sequential goToPose (arrive, then next) — the default, and
                     what a plain "the kitchen, then the bedroom" still gets.
    """
    text = transcript or ""
    if _THROUGH_RE.search(text):
        return "through"
    if _WAYPOINTS_RE.search(text):
        return "waypoints"
    return "steps"


def through_fallback_phrase():
    """Said when a continuous pass can't complete and we retry as a waypoint
    route (stopping at each), so the command still finishes."""
    return ("That didn't work as one continuous pass — "
            "visiting each stop in turn instead.")


def waypoint_plan_phrase(names, mode):
    """What to say when starting a followWaypoints / goThroughPoses route."""
    joined = _join_and(names)
    if mode == "through":
        return f"Going through {joined} without stopping."
    return f"Following waypoints through {joined}."


def waypoint_summary(status, names, mode):
    """Spoken wrap-up for a followWaypoints / goThroughPoses route. Nav2 drives
    the whole list as one task, so there's a single outcome rather than a
    per-stop tally."""
    if status == "SUCCEEDED":
        if mode == "through":
            return f"Tour complete — passed through {_join_and(names)}."
        return f"Reached every waypoint: {_join_and(names)}."
    return f"Route ended before finishing: status {status}."


def _join_stops(names):
    return ", then ".join(names)


def _join_and(names):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"
