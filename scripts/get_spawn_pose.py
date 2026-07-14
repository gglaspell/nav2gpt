#!/usr/bin/env python3
"""Print the robot's TRUE spawn pose, read live from Gazebo — no guessing.

Output (stdout, one line):  <x> <y> <qz> <qw>   in the Gazebo world frame, which
coincides with the Nav2 `map` frame for the TurtleBot3 house (same origin), so
it's usable directly as the AMCL initial pose.

Tries, in order (first that works wins):
  1. /gazebo/model_states           (gazebo_ros_state plugin, topic)
  2. /gazebo/get_entity_state       (gazebo_ros_state plugin, service)
  3. `gz model -m <name> -p`        (Gazebo Classic transport CLI)
  4. spawn pose parsed from turtlebot3_house.launch.py  (static, deterministic)

On failure prints diagnostics (gz availability, gazebo topics/services, the
launch file's spawn lines) to stderr and exits non-zero.
"""

import os
import re
import subprocess
import sys
import time

ROBOT_HINTS = ("turtlebot", "burger", "waffle")
FLOAT = r"-?\d+\.?\d*(?:[eE]-?\d+)?"


def _model_candidates():
    m = os.environ.get("TURTLEBOT3_MODEL", "").strip().lower()
    names = []
    if m:
        names += [f"turtlebot3_{m}", m]
    names += ["turtlebot3_burger", "turtlebot3_waffle", "turtlebot3_waffle_pi",
              "burger", "waffle", "turtlebot3"]
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _is_robot(name):
    n = name.lower()
    return any(h in n for h in ROBOT_HINTS)


def _emit(name, x, y, qz, qw):
    print(f"{x:.6f} {y:.6f} {qz:.6f} {qw:.6f}")
    print(f"# source: {name}", file=sys.stderr)
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
            return (f"model_states '{name}'", p.x, p.y, o.z, o.w)
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
    return (f"get_entity_state '{name}'", p.x, p.y, o.z, o.w)


def from_gz_cli(timeout=5.0):
    """Gazebo Classic transport — query each candidate model name directly."""
    import math
    if not _which("gz"):
        return None
    for name in _model_candidates():
        try:
            out = subprocess.run(["gz", "model", "-m", name, "-p"],
                                 capture_output=True, text=True, timeout=timeout)
        except subprocess.SubprocessError:
            continue
        nums = [float(t) for t in re.findall(FLOAT, out.stdout)]
        if len(nums) >= 6:                 # gz prints x y z roll pitch yaw
            x, y, _z, _r, _p, yaw = nums[:6]
            return (f"gz model '{name}'", x, y, math.sin(yaw / 2), math.cos(yaw / 2))
    return None


def from_launch_file():
    """Read the spawn pose straight from turtlebot3_house.launch.py (static)."""
    path = _house_launch_path()
    if not path:
        return None
    try:
        txt = open(path).read()
    except OSError:
        return None
    xm = re.search(r"x_pose[^\n]*?default\s*=\s*['\"](%s)['\"]" % FLOAT, txt)
    ym = re.search(r"y_pose[^\n]*?default\s*=\s*['\"](%s)['\"]" % FLOAT, txt)
    if not (xm and ym):
        # fall back to `-x <n> -y <n>` style spawn args
        xm = re.search(r"['\"]-x['\"]\s*,\s*['\"](%s)['\"]" % FLOAT, txt)
        ym = re.search(r"['\"]-y['\"]\s*,\s*['\"](%s)['\"]" % FLOAT, txt)
    if xm and ym:
        return (f"launch file {os.path.basename(path)}",
                float(xm.group(1)), float(ym.group(1)), 0.0, 1.0)
    return None


def _which(cmd):
    try:
        return subprocess.run(["which", cmd], capture_output=True,
                              text=True, timeout=5).stdout.strip() or None
    except subprocess.SubprocessError:
        return None


def _house_launch_path():
    try:
        prefix = subprocess.run(["ros2", "pkg", "prefix", "turtlebot3_gazebo"],
                                capture_output=True, text=True, timeout=5).stdout.strip()
    except subprocess.SubprocessError:
        return None
    if not prefix:
        return None
    path = os.path.join(prefix, "share", "turtlebot3_gazebo", "launch",
                        "turtlebot3_house.launch.py")
    return path if os.path.isfile(path) else None


def diagnostics():
    print(f"# gz CLI: {_which('gz') or 'NOT FOUND'}", file=sys.stderr)
    print(f"# model candidates tried: {_model_candidates()}", file=sys.stderr)
    for what, cmd in (("topics", ["ros2", "topic", "list"]),
                      ("services", ["ros2", "service", "list"])):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
            hits = [l for l in out.splitlines() if "gazebo" in l.lower()]
            print(f"# gazebo {what}: {hits or 'none'}", file=sys.stderr)
        except subprocess.SubprocessError:
            pass
    path = _house_launch_path()
    if path:
        try:
            lines = [l.strip() for l in open(path) if re.search(r"x_pose|y_pose|spawn|['\"]-[xy]['\"]", l)]
            print(f"# {os.path.basename(path)} spawn lines: {lines[:12] or 'none found'}",
                  file=sys.stderr)
        except OSError:
            pass
    else:
        print("# turtlebot3_house.launch.py: not found", file=sys.stderr)


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

    for method in (from_gz_cli, from_launch_file):
        try:
            r = method()
        except Exception as e:                           # noqa: BLE001
            print(f"# {method.__name__} error: {e}", file=sys.stderr)
            r = None
        if r:
            return _emit(*r)

    print("ERROR: could not read robot pose from Gazebo", file=sys.stderr)
    diagnostics()
    return 1


if __name__ == "__main__":
    sys.exit(main())
