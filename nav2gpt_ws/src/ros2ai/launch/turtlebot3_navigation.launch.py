#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
   # Spawn in mapped free space. The stock spawn (-2.0, -0.5) sits in an area the
   # map never covered, so AMCL has no features there and navigation can't start.
   turtlebot3_house = IncludeLaunchDescription(
      PythonLaunchDescriptionSource([os.path.join(
         get_package_share_directory('turtlebot3_gazebo'), 'launch'),
         '/turtlebot3_house.launch.py']),
      launch_arguments={'x_pose': '-1.0', 'y_pose': '1.0'}.items()
      )
#    turtlesim_world_2 = IncludeLaunchDescription(
#       PythonLaunchDescriptionSource([os.path.join(
#          get_package_share_directory('launch_tutorial'), 'launch'),
#          '/turtlesim_world_2_launch.py'])
#       )
#    rviz_node = IncludeLaunchDescription(
#       PythonLaunchDescriptionSource([os.path.join(
#          get_package_share_directory('launch_tutorial'), 'launch'),
#          '/turtlesim_rviz_launch.py'])
#       )

   return LaunchDescription([
      turtlebot3_house
   ])