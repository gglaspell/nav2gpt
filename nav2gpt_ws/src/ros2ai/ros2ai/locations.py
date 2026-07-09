"""Known named locations and reverse lookup (pure; no ROS imports).

Mirrors the room coordinates in nav_gpt's prompt for now; the dynamic-locations
branch will replace this static table with a saved/loaded one.
"""

# name -> (x, y)
ROOMS = {
    "the kitchen": (-4.0, 4.0),
    "the bedroom": (3.0, 4.0),
}


def destination_label(x, y, tol=0.5):
    """Name of the known room near (x, y), else the coordinate pair as text."""
    for name, (rx, ry) in ROOMS.items():
        if abs(x - rx) <= tol and abs(y - ry) <= tol:
            return name
    return f"({x}, {y})"
