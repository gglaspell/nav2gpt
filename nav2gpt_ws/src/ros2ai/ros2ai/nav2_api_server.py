#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from nav2_simple_commander.robot_navigator import BasicNavigator
from std_srvs.srv import SetBool
from geometry_msgs.msg import Pose, PoseStamped
from ros2ai_msgs.srv import Nav2Gpt, FollowRoute
from ros2ai.status_report import status_message, progress_phrase
from ros2ai.speech import speak
from ros2ai.locations import destination_label, default_store_path
from tf_transformations import quaternion_from_euler

import numpy as np


class Nav2ApiServer(Node):
    def __init__(self):
        super().__init__("nav2_api_server")
        self.server = self.create_service(Nav2Gpt, "goToPose", self.service_clbk)
        # Multi-stop routes: one Nav2 waypoint-follow / pass-through task for a
        # whole list of poses, rather than a goToPose per stop.
        self.route_server = self.create_service(
            FollowRoute, "followRoute", self.follow_route_clbk)
        self.nav2_client = BasicNavigator()
        # Cancel a goal that runs longer than this many seconds. Override with:
        #   ros2 run ros2ai nav2_api_server --ros-args -p nav_timeout_sec:=30.0
        self.declare_parameter("nav_timeout_sec", 120.0)
        # Announce arrivals by room name -- including rooms saved at runtime -- by
        # reading the same persistent store the voice node writes to.
        self.store_path = default_store_path()
        # The node otherwise runs silently; announce readiness so operators know
        # the server came up (matches the "ready" line documented in the README).
        self.get_logger().info("Nav2 API Server is ready")

    def _make_pose(self, x, y, theta_deg):
        """A map-frame PoseStamped from x, y and a heading in degrees."""
        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        quat = quaternion_from_euler(0, 0, np.deg2rad(float(theta_deg)))
        pose.pose.orientation.x = quat[0]
        pose.pose.orientation.y = quat[1]
        pose.pose.orientation.z = quat[2]
        pose.pose.orientation.w = quat[3]
        return pose

    def _run_to_completion(self, dest, timeout_scale=1.0):
        """Busy-wait for the active Nav2 task, canceling past the timeout and
        speaking progress, then return the TaskResult.

        Shared by goToPose, goThroughPoses, and followWaypoints. getattr guards
        the feedback fields because followWaypoints' feedback carries a current
        waypoint index rather than navigation_time / distance_remaining.

        `timeout_scale` multiplies the per-goal timeout: a multi-stop route is one
        long task, so it needs roughly one goal's budget per stop, not the single
        budget that fits one goToPose.
        """
        timeout = self.get_parameter("nav_timeout_sec").value * timeout_scale
        start_dist = None
        announced = set()
        canceled = False
        while not self.nav2_client.isTaskComplete():
            fb = self.nav2_client.getFeedback()
            if not fb:
                continue
            nav_time = getattr(fb, "navigation_time", None)
            # Cancel once past the configured timeout, then let the loop finish so
            # getResult() reports the real CANCELED outcome (not a stale success).
            if not canceled and nav_time is not None and nav_time.sec > timeout:
                self.get_logger().warn(
                    f"Navigation exceeded {timeout:.0f}s -- canceling the task.")
                self.nav2_client.cancelTask()
                canceled = True
            # Spoken progress as the robot closes in (goToPose / goThroughPoses).
            dist = getattr(fb, "distance_remaining", 0.0)
            if start_dist is None and dist > 0.0:
                start_dist = dist
            phrase = progress_phrase(dist, start_dist, announced, dest)
            if phrase:
                self.get_logger().info(phrase)
                speak(phrase)
        return self.nav2_client.getResult()

    def service_clbk(self, req, res):
        pose = self._make_pose(req.x, req.y, req.theta)
        # goToPose returns False if Nav2 REJECTS the goal (start/goal in a
        # lethal or inflated cell, server not active). Without checking this, a
        # rejected goal makes isTaskComplete() return True immediately and the
        # server would report a phantom success while the robot never moves.
        accepted = self.nav2_client.goToPose(pose)
        if not accepted:
            self.get_logger().error(
                f"goToPose REJECTED for ({req.x:.2f}, {req.y:.2f}) -- goal likely "
                "in a lethal/inflated cell, or Nav2 is not active yet.")
            res.status = "REJECTED"
            return res

        self.get_logger().info(
            f"Navigating to ({req.x:.2f}, {req.y:.2f}, {req.theta:.0f} deg)...")
        dest = destination_label(req.x, req.y, path=self.store_path)
        result = self._run_to_completion(dest)
        self.get_logger().info(f"goToPose result: {result}")
        # Report the real outcome name (SUCCEEDED / CANCELED / FAILED / UNKNOWN)
        # so the caller can say more than just "true/false", and announce it.
        res.status = result.name
        speak(status_message(res.status, dest))
        return res

    def follow_route_clbk(self, req, res):
        """Drive a whole pose list as a single Nav2 task: goThroughPoses (a
        continuous pass) or followWaypoints (visit each in turn)."""
        poses = [self._make_pose(x, y, t)
                 for x, y, t in zip(req.xs, req.ys, req.thetas)]
        if not poses:
            self.get_logger().error("followRoute called with no poses.")
            res.status = "REJECTED"
            return res
        mode = (req.mode or "through").strip().lower()
        # Label the route by its final stop, so progress/arrival name a room.
        dest = destination_label(req.xs[-1], req.ys[-1], path=self.store_path)

        if mode == "waypoints":
            self.get_logger().info(f"Following {len(poses)} waypoints...")
            # followWaypoints' return value is version-dependent: some Nav2
            # releases return None while the task is merely *starting* (not yet
            # known-accepted), others return a bool immediately. Treating only
            # an explicit False as rejection can let a truly-rejected goal on a
            # None-returning version fall through to _run_to_completion() and
            # spin forever waiting on a task that never started. Guard against
            # that by also bailing out if the task client reports no active
            # goal handle after the call.
            accepted = self.nav2_client.followWaypoints(poses)
            if accepted is False:
                self.get_logger().error(
                    "followWaypoints REJECTED -- a pose is unreachable or Nav2 is "
                    "not active yet.")
                res.status = "REJECTED"
                return res
            if accepted is None and getattr(
                    self.nav2_client, "goal_handle", None) is None:
                self.get_logger().error(
                    "followWaypoints did not start (no goal handle) -- treating "
                    "as REJECTED.")
                res.status = "REJECTED"
                return res
        else:
            accepted = self.nav2_client.goThroughPoses(poses)
            if not accepted:
                self.get_logger().error(
                    "goThroughPoses REJECTED -- a pose is unreachable or Nav2 is "
                    "not active yet.")
                res.status = "REJECTED"
                return res
            self.get_logger().info(f"Going through {len(poses)} poses...")

        # One long task over every stop -- give it a per-stop share of the budget.
        result = self._run_to_completion(dest, timeout_scale=len(poses))
        self.get_logger().info(f"followRoute ({mode}) result: {result}")
        res.status = result.name
        speak(status_message(res.status, dest))
        return res


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = Nav2ApiServer()
        rclpy.spin(node)
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
