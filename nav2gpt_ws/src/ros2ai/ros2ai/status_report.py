"""Pure helpers for reporting navigation results.

No ROS imports on purpose, so the message logic can be unit-tested without a
running robot (see tests/test_result_reporting.py).
"""


def status_message(status, x, y):
    """Human-readable sentence for a goToPose result status.

    `status` is the string the goToPose service returns: SUCCEEDED, FAILED,
    CANCELED, REJECTED, UNKNOWN (or NO_RESPONSE if the service call failed).
    """
    where = f"({x}, {y})"
    if status == "SUCCEEDED":
        return f"Arrived: reached the goal at {where}."
    if status == "REJECTED":
        return f"Could not start toward {where}: the goal was rejected (unreachable or off the map)."
    if status == "CANCELED":
        return f"Navigation to {where} was canceled."
    return f"Could not reach {where}: navigation ended with status {status}."


def progress_phrase(distance_remaining, start_distance, announced):
    """Milestone phrase to announce as the robot closes in, or None.

    `announced` is a set of milestone keys already spoken; it is updated in place
    so each milestone is announced only once.
    """
    if not start_distance or start_distance <= 0:
        return None
    frac_done = 1.0 - (distance_remaining / start_distance)
    for threshold, key, phrase in ((0.5, "half", "Halfway to the goal."),
                                   (0.9, "near", "Almost at the goal.")):
        if frac_done >= threshold and key not in announced:
            announced.add(key)
            return phrase
    return None
