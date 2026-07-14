#!/usr/bin/env bash
#
# nav_goal.sh — send a Nav2 goal DIRECTLY, bypassing the LLM/voice pipeline.
#
# This isolates Nav2: if the robot drives here but the voice command doesn't, the
# problem is the LLM/goToPose pipeline; if this fails too, it's Nav2/localization.
# Prints live feedback and the final result (SUCCEEDED / ABORTED + reason).
#
#   ./scripts/nav_goal.sh [x] [y] [yaw_deg]
#
# Defaults to the kitchen (-4, 4, facing 180 deg) — the same goal the voice
# command "go to the kitchen" produces.

set -uo pipefail

X="${1:--4.0}"
Y="${2:-4.0}"
YAWDEG="${3:-180}"

# yaw (deg) -> quaternion z,w about +z
read -r QZ QW < <(python3 -c "import math; y=math.radians($YAWDEG); print(math.sin(y/2.0), math.cos(y/2.0))")

# Let AMCL converge and the costmaps populate before planning. Sending a goal
# immediately after localization makes the global planner fail repeatedly on a
# half-built costmap (it burns recovery behaviours and can abort even though the
# route is clear once settled). Wait, then clear stale/phantom obstacle data.
echo "Letting localization + costmaps settle before planning..."
sleep 10
echo "Clearing costmaps for a clean start..."
ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap "{}" >/dev/null 2>&1 || true
ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap "{}" >/dev/null 2>&1 || true
sleep 2

# --- pre-goal diagnostics: prove the config actually took effect ------------
echo "=== pre-goal diagnostics ==="
echo "-- global_costmap robot_radius (want 0.12 = burger; 0.22 = params patch FAILED, would over-inflate):"
ros2 param get /global_costmap/global_costmap robot_radius 2>/dev/null || echo "   (could not read robot_radius)"
echo "-- map -> base_link transform (confirms the TF chain is complete + where the robot really is):"
timeout 4 ros2 run tf2_ros tf2_echo map base_link 2>/dev/null | grep -A5 -m1 "At time" \
  || echo "   (NO map->base_link transform — localization/TF is broken)"
echo "============================"
echo

echo "Sending NavigateToPose goal: x=$X y=$Y yaw=${YAWDEG}deg (map frame)"
echo "(bypasses the LLM — tests Nav2 planning + control directly)"
echo

ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}, pose: {position: {x: $X, y: $Y, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: $QZ, w: $QW}}}}" \
  --feedback

echo
echo "Goal finished. Look above for the result: 'Goal finished with status: SUCCEEDED'"
echo "means Nav2 pathed there. ABORTED/REJECTED means planning or control failed —"
echo "the lines above name the reason."
