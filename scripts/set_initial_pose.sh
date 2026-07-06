#!/usr/bin/env bash
#
# set_initial_pose.sh — give AMCL an initial pose so Nav2 actually localizes.
#
# Without this, AMCL never publishes map->odom: RViz shows "frame [map] does not
# exist" / "Localization: unknown", the costmap is offset from reality, and the
# robot plans paths around walls that aren't there.
#
#   ./scripts/set_initial_pose.sh [x] [y] [qz] [qw]
#
# Pose source, in priority order:
#   1. Explicit x/y[/qz/qw] passed as arguments (manual override).
#   2. AUTO-DETECTED live from Gazebo via get_spawn_pose.py — the real spawn
#      pose, not a guess. This is the default path.
#   3. A measured fallback (x=-0.07, y=-0.56) if auto-detect can't reach Gazebo.
#
# After resolving the pose it waits for AMCL, publishes, and retries until AMCL
# reports /amcl_pose (accepted) or it times out.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

X="${1:-}"; Y="${2:-}"; QZ="${3:-}"; QW="${4:-}"
SOURCE="arguments"

# 2. Auto-detect from the running simulation unless the pose was given explicitly.
if [ -z "$X" ]; then
  echo "Auto-detecting the robot's spawn pose from Gazebo..."
  if OUT="$(python3 "$SCRIPT_DIR/get_spawn_pose.py" 2>/tmp/get_spawn_pose.err)"; then
    read -r X Y QZ QW <<< "$OUT"
    SOURCE="Gazebo (live)"
  else
    echo "  auto-detect failed:"; sed 's/^/    /' /tmp/get_spawn_pose.err 2>/dev/null
  fi
fi

# 3. Measured fallback.
if [ -z "$X" ]; then
  X="-0.07"; Y="-0.56"; QZ="0.0"; QW="1.0"
  SOURCE="measured fallback"
fi
# Fill any missing orientation with "facing +x".
QZ="${QZ:-0.0}"; QW="${QW:-1.0}"

echo "Initial pose source: $SOURCE  ->  x=$X y=$Y qz=$QZ qw=$QW"

POSE="{header: {frame_id: 'map'}, pose: {pose: {position: {x: $X, y: $Y, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: $QZ, w: $QW}}}}"

echo "Waiting for the amcl node to come up..."
for _ in $(seq 1 30); do
  ros2 node list 2>/dev/null | grep -q '/amcl' && break
  sleep 1
done

echo "Seeding AMCL initial pose in 'map' frame..."
localized=0
for attempt in $(seq 1 8); do
  ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "$POSE" >/dev/null 2>&1
  sleep 1
  if timeout 2 ros2 topic echo --once /amcl_pose >/dev/null 2>&1; then
    localized=1
    echo "AMCL is publishing /amcl_pose — localized (attempt $attempt)."
    break
  fi
  echo "  ...not localized yet, retrying ($attempt/8)"
done

if [ "$localized" = "1" ]; then
  echo "Done. RViz's 'frame [map] does not exist' should clear and the robot should sit on the map correctly."
else
  echo "WARNING: AMCL did not confirm localization. Set the pose by hand in RViz"
  echo "         ('2D Pose Estimate'), or pass corrected x/y to this script."
fi
