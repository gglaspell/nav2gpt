"""Pure helpers for reporting navigation results.

No ROS imports on purpose, so the message logic can be unit-tested without a
running robot (see tests/test_result_reporting.py).
"""


def status_message(status, destination):
    """Human-readable sentence for a goToPose result.

    `status` is the string the goToPose service returns (SUCCEEDED, FAILED,
    CANCELED, REJECTED, UNKNOWN, or NO_RESPONSE); `destination` is a room name
    or a coordinate string (see locations.destination_label).
    """
    if status == "SUCCEEDED":
        return f"Arrived: reached {destination}."
    if status == "REJECTED":
        return f"Could not start toward {destination}: the goal was rejected (unreachable or off the map)."
    if status == "CANCELED":
        return f"Navigation to {destination} was canceled."
    return f"Could not reach {destination}: navigation ended with status {status}."


def where_am_i_message(label):
    """Spoken answer to "where am I?". `label` is a room name or a coordinate
    string from locations.destination_label; a coordinate string starts with "("."""
    if label.startswith("("):
        return f"You are at {label}."
    return f"You are in {label}."


def saved_location_message(name, x, y):
    """Confirmation spoken after "save this location as <name>"."""
    return f"Saved {name} at ({x:.2f}, {y:.2f})."


def need_name_message():
    """Asked when a save command arrives without a name."""
    return "I need a name for this location. Try: save this location as the office."


def progress_phrase(distance_remaining, start_distance, announced, destination):
    """Milestone phrase to announce as the robot closes in, or None.

    `announced` is a set of milestone keys already spoken; it is updated in place
    so each milestone is announced once. `destination` is named in the phrase.
    """
    if not start_distance or start_distance <= 0:
        return None
    frac_done = 1.0 - (distance_remaining / start_distance)
    for threshold, key, template in ((0.5, "half", "Halfway to {}."),
                                     (0.9, "near", "Almost at {}.")):
        if frac_done >= threshold and key not in announced:
            announced.add(key)
            return template.format(destination)
    return None
