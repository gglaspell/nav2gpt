"""Named locations: a small persistent store plus reverse lookup (pure; no ROS).

Locations are ``name -> (x, y, theta)`` and persist to a JSON file so the set of
known rooms survives restarts and grows at runtime (the "save this location"
command). Seeded with the two rooms the project shipped with, so a fresh machine
with no saved file still knows the kitchen and the bedroom.

Kept ROS-free on purpose so it unit-tests without a running robot
(see tests/test_dynamic_locations.py).
"""
import json
import os

# name -> (x, y, theta). theta is the heading (degrees) to face on arrival.
DEFAULT_ROOMS = {
    "the kitchen": (-4.0, 4.0, 180.0),
    "the bedroom": (3.0, 4.0, 0.0),
}

# Back-compat: earlier code and tests import ROOMS as name -> (x, y). The live,
# possibly-larger set comes from the store via load_locations().
ROOMS = {name: (pose[0], pose[1]) for name, pose in DEFAULT_ROOMS.items()}


def default_store_path():
    """Where saved locations live. Override with the NAV2GPT_LOCATIONS env var."""
    return os.environ.get("NAV2GPT_LOCATIONS") or os.path.join(
        os.path.expanduser("~"), ".nav2gpt", "locations.json")


def normalize_name(name):
    """Lowercase and collapse whitespace so names compare predictably."""
    return " ".join(str(name).lower().split())


def load_locations(path=None):
    """Return ``name -> (x, y, theta)``, the shipped defaults merged with the
    saved file (the file wins on a name clash).

    With no path, or if the file is missing or unreadable, just the defaults are
    returned — so navigation never breaks on a fresh or corrupt store.
    """
    rooms = dict(DEFAULT_ROOMS)
    if not path:
        return rooms
    try:
        with open(path) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return rooms
    for name, pose in (saved or {}).items():
        try:
            theta = float(pose[2]) if len(pose) > 2 else 0.0
            rooms[normalize_name(name)] = (float(pose[0]), float(pose[1]), theta)
        except (TypeError, ValueError, IndexError):
            continue   # skip a malformed entry rather than failing the whole load
    return rooms


def save_location(name, x, y, theta=0.0, path=None):
    """Add or update a named location and persist it. Returns the updated dict.

    The write includes the defaults so the file is self-contained; loading merges
    them again, which is idempotent.
    """
    rooms = load_locations(path)
    rooms[normalize_name(name)] = (float(x), float(y), float(theta))
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump({n: list(p) for n, p in rooms.items()},
                      f, indent=2, sort_keys=True)
    return rooms


def nearest_room(rooms, x, y, tol=0.5):
    """Name of the room within ``tol`` metres of (x, y), else None."""
    for name, pose in rooms.items():
        if abs(x - pose[0]) <= tol and abs(y - pose[1]) <= tol:
            return name
    return None


def destination_label(x, y, tol=0.5, path=None):
    """Name of the known room near (x, y), else the coordinate pair as text.

    With no path only the shipped defaults are consulted, which keeps the unit
    tests hermetic; production callers pass the store path so saved rooms are
    named too.
    """
    name = nearest_room(load_locations(path), x, y, tol)
    return name if name else f"({x}, {y})"


def _num(v):
    """Render a coordinate for the prompt: rounded to 2 dp and without a trailing
    .0, so a saved pose reads '-1' not '-0.9999419778588633'. Only affects the
    prompt text; the stored value keeps full precision."""
    v = round(float(v), 2)
    return str(int(v)) if v.is_integer() else str(v)


def describe_rooms(rooms):
    """One line per room, in the phrasing the LLM prompt expects. Feeding this
    from the live store (instead of two hardcoded lines) lets the robot navigate
    to rooms saved at runtime.
    """
    return "\n".join(
        f"the coordinates of {name} is x: {_num(p[0])}, y: {_num(p[1])}, "
        f"theta: {_num(p[2] if len(p) > 2 else 0.0)}"
        for name, p in rooms.items())
