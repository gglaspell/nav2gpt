#!/usr/bin/env bash
#
# set_initial_pose.sh — give AMCL an initial pose so Nav2 actually localizes.
#
# Without this, AMCL never publishes map->odom, RViz shows "Localization:
# unknown", and the costmap is offset from reality — the robot plans paths
# around walls that aren't there. This is the proper fix for that (the
# static-transform trick only faked a transform and left localization wrong).
#
#   ./scripts/set_initial_pose.sh [x] [y] [yaw_w]
#
# Defaults match the TurtleBot3 house spawn pose (x=-2.0, y=-0.5, facing +x),
# which is where turtlebot3_navigation.launch.py drops the robot. If your robot
# spawns elsewhere, pass x/y (and the quaternion w component) to match, or use
# RViz's "2D Pose Estimate" button instead.
#
# Publishes several times because a single --once can race AMCL's subscription.

set -uo pipefail

X="${1:--2.0}"
Y="${2:--0.5}"
QW="${3:-1.0}"

echo "Setting AMCL initial pose: x=$X y=$Y (quaternion w=$QW) in 'map' frame..."
ros2 topic pub --times 5 --rate 1 /initialpose \
  geometry_msgs/msg/PoseWithCovarianceStamped \
  "{header: {frame_id: 'map'}, pose: {pose: {position: {x: $X, y: $Y, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: $QW}}}}"
echo "Initial pose published. AMCL should now report localized and publish map->odom."
