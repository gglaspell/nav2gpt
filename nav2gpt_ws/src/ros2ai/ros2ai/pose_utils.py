"""Pure pose helpers (no ROS imports).

Just enough quaternion math to turn an AMCL orientation into a heading, so the
"save this location" command can record theta the same way goToPose consumes it
(degrees). Pure so it unit-tests without tf or a running robot.
"""
import math


def yaw_degrees(qx, qy, qz, qw):
    """Yaw (rotation about Z) in degrees from a quaternion.

    Standard z-y-x extraction reduced to the yaw term; matches
    tf_transformations.euler_from_quaternion()[2] converted to degrees.
    """
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.degrees(math.atan2(siny_cosp, cosy_cosp))
