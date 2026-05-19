#!/bin/bash
# shellcheck disable=SC1090,SC1091
set -e

# Source ROS 2 setup
source /opt/ros/"$ROS_DISTRO"/setup.bash

# Source nav2gpt workspace
# The workspace lives at <workspaceFolder>/nav2gpt_ws which is bind-mounted from the host.
# COLCON_WS is set to the container's workspaceFolder path via containerEnv.
if [ -f "${COLCON_WS}/nav2gpt_ws/install/setup.bash" ]; then
    source "${COLCON_WS}/nav2gpt_ws/install/setup.bash"
fi

# Setup colcon_cd
source /usr/share/colcon_cd/function/colcon_cd.sh
export _colcon_cd_root=/opt/ros/humble/

# Setup colcon tab completion
source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash

# Switch to CycloneDDS
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# TurtleBot3 model for Gazebo simulation
export TURTLEBOT3_MODEL=burger

exec "$@"
