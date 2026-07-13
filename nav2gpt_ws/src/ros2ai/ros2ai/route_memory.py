"""Short-term memory of the last route so a follow-up command can act on it
without naming the destinations again (pure; no ROS imports).

This is the conversational memory in the Whisper -> LLM -> Nav2 loop: after any
navigation the ordered goals are remembered, so "do that again" replays them and
"run it in reverse" walks them the other way. Kept ROS-free so it unit-tests
without a running robot (see tests/test_multi_step_nav.py).
"""
import re

_REVERSE_RE = re.compile(
    r"\b(?:reverse|backwards?|in reverse|opposite order|other way(?: a?round)?)\b",
    re.IGNORECASE)
_REPEAT_RE = re.compile(
    r"\b(?:again|repeat|same (?:route|thing|trip|places)|do that again|"
    r"once more|one more time)\b", re.IGNORECASE)


class RouteMemory:
    """Remembers the most recent route and resolves follow-up references to it."""

    def __init__(self):
        self.last_route = None

    def remember(self, route):
        """Store a route (list of goal dicts) as the most recent one. An empty or
        missing route is ignored, so a failed parse doesn't wipe usable memory."""
        if route:
            self.last_route = [dict(stop) for stop in route]

    def resolve_followup(self, transcript):
        """If `transcript` refers back to the last route, return
        ``{"mode": "repeat"|"reverse", "route": [...]}``; otherwise None.

        Returns None when nothing has been remembered yet, so the caller falls
        back to normal navigation. The returned route is a copy — mutating it
        can't corrupt what's remembered.
        """
        if not self.last_route:
            return None
        text = transcript or ""
        if _REVERSE_RE.search(text):
            return {"mode": "reverse",
                    "route": [dict(s) for s in reversed(self.last_route)]}
        if _REPEAT_RE.search(text):
            return {"mode": "repeat",
                    "route": [dict(s) for s in self.last_route]}
        return None
