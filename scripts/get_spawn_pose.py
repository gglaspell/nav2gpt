#!/usr/bin/env python3
"""Print the robot's TRUE spawn pose, read live from Gazebo — no guessing.

Output (stdout, one line):  <x> <y> <qz> <qw>   in the Gazebo world frame, which
coincides with the Nav2 `map` frame for the TurtleBot3 house (same origin), so
it's usable directly as the AMCL initial pose.

Tries, in order:
  1. /gazebo/model_states           (gazebo_ros_state plugin, topic)
  2. /gazebo/get_entity_state       (gazebo_ros_state plugin, service)
  3. `gz model -m <name> -p`        (Gazebo Classic transport CLI)

On failure prints diagnostics (available gazebo topics/services) to stderr and
exits non-zero, so the caller can fall back and we can see what's available.
"""

import re
import subprocess
import sys
import time

ROBOT_HINTS = ("turtlebot", "burger", "waffle")


def _is_robot(name):
    n = name.lower()
    return any(h in n for h in ROBOT_HINTS)


def _emit(name, x, y, qz, qw):
    print(f"{x:.6f} {y:.6f} {qz:.6f} {qw:.6f}")
    print(f"# detected model '{name}'", file=sys.stderr)
    return 0


def from_model_states(node, timeout=5.0):
    try:
        from gazebo_msgs.msg import ModelStates
    except ImportError:
        return None
    import rclpy
    box = {}
    node.create_subscription(ModelStates, "/gazebo/model_states",
                             lambda m: box.__setitem__("m", m), 10)
    t0 = time.time()
    while time.time() - t0 < timeout and "m" not in box:
        rclpy.spin_once(node, timeout_sec=0.2)
    msg = box.get("m")
    if not msg:
        return None
    for name, pose in zip(msg.name, msg.pose):
        if _is_robot(name):
            p, o = pose.position, pose.orientation
            return (name, p.x, p.y, o.z, o.w)
    return None


def from_entity_state(node, timeout=5.0):
    try:
        from gazebo_msgs.srv import GetEntityState, GetModelList
    except ImportError:
        return None
    import rclpy
    lst = node.create_client(GetModelList, "/gazebo/get_model_list")
    if not lst.wait_for_service(timeout_sec=timeout):
        return None
    fut = lst.call_async(GetModelList.Request())
    rclpy.spin_until_future_complete(node, fut, timeout_sec=timeout)
    if not fut.result():
        return None
    name = next((n for n in fut.result().model_names if _is_robot(n)), None)
    if not name:
        return None
    get = node.create_client(GetEntityState, "/gazebo/get_entity_state")
    if not get.wait_for_service(timeout_sec=timeout):
        return None
    req = GetEntityState.Request()
    req.name = name
    fut = get.call_async(req)
    rclpy.spin_until_future_complete(node, fut, timeout_sec=timeout)
    res = fut.result()
    if not res or not getattr(res, "success", False):
        return None
    p, o = res.state.pose.position, res.state.pose.orientation
    return (name, p.x, p.y, o.z, o.w)


def from_gz_cli(timeout=5.0):
    """Gazebo Classic transport — works even without the ROS state plugin."""
    import math
    try:
        listing = subprocess.run(["gz", "model", "--list"], capture_output=True,
                                 text=True, timeout=timeout).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    name = None
    for line in listing.splitlines():
        tok = line.strip().lstrip("-").strip()
        if _is_robot(tok):
            name = tok.split()[-1] if tok.split() else tok
            break
    if not name:
        return None
    try:
        out = subprocess.run(["gz", "model", "-m", name, "-p"],
                             capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.SubprocessError:
        return None
    nums = [float(t) for t in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", out)]
    if len(nums) < 6:
        return None
    x, y, _z, _r, _p, yaw = nums[:6]   # gz prints x y z roll pitch yaw
    return (name, x, y, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def diagnostics():
    for what, cmd in (("topics", ["ros2", "topic", "list"]),
                      ("services", ["ros2", "service", "list"])):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
            hits = [l for l in out.splitlines() if "gazebo" in l.lower()]
            print(f"# available gazebo {what}: {hits or 'none'}", file=sys.stderr)
        except subprocess.SubprocessError:
            pass


def main():
    import rclpy
    rclpy.init()
    node = rclpy.create_node("get_spawn_pose")
    try:
        for method in (from_model_states, from_entity_state):
            try:
                r = method(node)
            except Exception as e:                       # noqa: BLE001
                print(f"# {method.__name__} error: {e}", file=sys.stderr)
                r = None
            if r:
                return _emit(*r)
    finally:
        node.destroy_node()
        rclpy.shutdown()

    r = from_gz_cli()
    if r:
        return _emit(*r)

    print("ERROR: could not read robot pose from Gazebo (state plugin/gz CLI unavailable)",
          file=sys.stderr)
    diagnostics()
    return 1


if __name__ == "__main__":
    sys.exit(main())
