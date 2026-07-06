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
# Defaults are the measured TurtleBot3 house spawn pose (from /amcl_pose after a
# hand-aligned RViz "2D Pose Estimate"): x=-0.07, y=-0.56, yaw~=0. If your robot
# spawns elsewhere, pass x/y to match, or use RViz's "2D Pose Estimate" button
# and read the result with:  ros2 topic echo --once /amcl_pose
#
# It waits for AMCL to come up, then publishes the pose and retries until AMCL
# starts reporting /amcl_pose (i.e. it accepted the estimate) or it times out.

set -uo pipefail

X="${1:--0.07}"
Y="${2:--0.56}"
QZ="${3:-0.0}"
QW="${4:-1.0}"

POSE="{header: {frame_id: 'map'}, pose: {pose: {position: {x: $X, y: $Y, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: $QZ, w: $QW}}}}"

echo "Waiting for the amcl node to come up..."
for _ in $(seq 1 30); do
  ros2 node list 2>/dev/null | grep -q '/amcl' && break
  sleep 1
done

echo "Seeding AMCL initial pose: x=$X y=$Y (qz=$QZ qw=$QW) in 'map' frame..."
localized=0
for attempt in $(seq 1 8); do
  ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "$POSE" >/dev/null 2>&1
  sleep 1
  # AMCL publishes /amcl_pose once it has accepted an initial pose.
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
