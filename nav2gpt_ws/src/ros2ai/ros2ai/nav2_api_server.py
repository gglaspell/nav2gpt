#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from nav2_simple_commander.robot_navigator import BasicNavigator
from std_srvs.srv import SetBool
from geometry_msgs.msg import Pose, PoseStamped
from ros2ai_msgs.srv import Nav2Gpt
from ros2ai.status_report import status_message, progress_phrase
from ros2ai.speech import speak
from ros2ai.locations import destination_label
from tf_transformations import quaternion_from_euler

import numpy as np

class Nav2ApiServer(Node):
    def __init__(self):
        super().__init__("nav2_api_server")
        self.server = self.create_service(Nav2Gpt, "goToPose", self.service_clbk)
        self.nav2_client = BasicNavigator()
        # Cancel a goal that runs longer than this many seconds. Override with:
        #   ros2 run ros2ai nav2_api_server --ros-args -p nav_timeout_sec:=30.0
        self.declare_parameter("nav_timeout_sec", 120.0)
        # The node otherwise runs silently; announce readiness so operators know
        # the server came up (matches the "ready" line documented in the README).
        self.get_logger().info("Nav2 API Server is ready")

    
    def service_clbk(self, req, res):
        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = req.x
        pose.pose.position.y = req.y
        quat = quaternion_from_euler(0, 0, np.deg2rad(req.theta))
        pose.pose.orientation.x = quat[0]
        pose.pose.orientation.y = quat[1]
        pose.pose.orientation.z = quat[2]
        pose.pose.orientation.w = quat[3]
        # goToPose returns False if Nav2 REJECTS the goal (start/goal in a
        # lethal or inflated cell, server not active). Without checking this, a
        # rejected goal makes isTaskComplete() return True immediately and the
        # server would report a phantom success while the robot never moves.
        accepted = self.nav2_client.goToPose(pose)
        if not accepted:
            self.get_logger().error(
                f"goToPose REJECTED for ({req.x:.2f}, {req.y:.2f}) — goal likely "
                "in a lethal/inflated cell, or Nav2 is not active yet.")
            res.status = "REJECTED"
            return res

        self.get_logger().info(
            f"Navigating to ({req.x:.2f}, {req.y:.2f}, {req.theta:.0f} deg)...")
        timeout = self.get_parameter("nav_timeout_sec").value
        dest = destination_label(req.x, req.y)
        start_dist = None
        announced = set()
        canceled = False
        while not self.nav2_client.isTaskComplete():
            fb = self.nav2_client.getFeedback()
            if not fb:
                continue
            # Cancel once past the configured timeout, then let the loop finish so
            # getResult() reports the real CANCELED outcome (not a stale success).
            if not canceled and fb.navigation_time.sec > timeout:
                self.get_logger().warn(
                    f"Navigation exceeded {timeout:.0f}s — canceling the goal.")
                self.nav2_client.cancelTask()
                canceled = True
            # Spoken progress as the robot closes in on the goal.
            if start_dist is None and fb.distance_remaining > 0.0:
                start_dist = fb.distance_remaining
            phrase = progress_phrase(fb.distance_remaining, start_dist, announced, dest)
            if phrase:
                self.get_logger().info(phrase)
                speak(phrase)

        result = self.nav2_client.getResult()
        self.get_logger().info(f"goToPose result: {result}")
        # Report the real outcome name (SUCCEEDED / CANCELED / FAILED / UNKNOWN)
        # so the caller can say more than just "true/false", and announce it.
        res.status = result.name
        speak(status_message(res.status, dest))
        return res

def main(args=None):
    rclpy.init(args=args)
    try:
        node = Nav2ApiServer()
        rclpy.spin(node)
    except Exception as e:
        print(f"Exception: {e}")
    rclpy.shutdown()

if __name__ == '__main__':
    main()