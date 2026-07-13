"""Multi-stop route resolution and spoken route feedback (pure; no ROS imports).

Turns one spoken command that names several destinations in order ("go to the
kitchen, then the bedroom") into an ordered list of goals resolved against the
known-room store, and phrases the per-stop and end-of-route announcements.

Kept ROS-free on purpose so it unit-tests without a running robot
(see tests/test_multi_step_nav.py); the node supplies the room store and drives
goToPose for each stop.
"""
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


def _join_stops(names):
    return ", then ".join(names)
