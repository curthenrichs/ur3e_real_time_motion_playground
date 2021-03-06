#!/usr/bin/env python

'''
Author: Curt Henrichs

Relaxed-IK UR driver interface node.

Interfaces with relaxed-ik's joint angle solutions topic to generate messages to
underlying UR driver. Additionally provides an easy to use interface for the
Robotiq gripper driver.

Adjust timing with the `arm_joint_step_delay` param. Set to a value that should be
safe and stable. Note smaller values will make the robot move faster at the expense
of stability and safety. Larger values will increase the time it takes to reach
target which may lead to large lag in respone to goal change.
'''

import yaml
import rospy

from relaxed_ik.msg import JointAngles
from std_msgs.msg import Empty, Bool, Float32
from robotiq_85_msgs.msg import GripperCmd, GripperStat
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


DEFAULT_ARM_JOINT_STEP_DELAY = 0.5
DEFAULT_START_ENABLED = False
DEFAULT_GRIPPER_SPEED = 0.1
DEFAULT_GRIPPER_EFFORT = 100


class RikUrHwInterfaceNode:

    def __init__(self, info_file_path, joint_step_delay, gripper_speed,
                 gripper_effort, start_enabled):
        self._joint_step_delay = joint_step_delay
        self._gripper_speed = gripper_speed
        self._gripper_effort = gripper_effort
        self._enabled = start_enabled

        # Hardware parameters
        fin = open(info_file_path,'r')
        y = yaml.load(fin, Loader=yaml.Loader)
        self._arm_joint_names = y['joint_ordering']
        self._starting_config = y['starting_config']
        fin.close()

        # ROS Publishers
        self._grip_cmd_pub = rospy.Publisher('gripper/cmd', GripperCmd, queue_size=10)
        self._traj_pub = rospy.Publisher('scaled_pos_traj_controller/command',JointTrajectory,queue_size=5)

        # ROS Subscribers
        self._enabled_sub = rospy.Subscriber('hw_interface/enable',Bool,self._enabled_cb)
        self._ja_sub = rospy.Subscriber('relaxed_ik/joint_angle_solutions',JointAngles, self._ja_cb)
        self._set_initial_pose_sub = rospy.Subscriber('hw_interface/set_initial_pose',Empty, self._set_initial_pose_cb)
        self._gripper_position_sub = rospy.Subscriber('hw_interface/gripper_position',Float32,self._gripper_position_cb)

    def _enabled_cb(self, msg):
        self._enabled = msg.data

    def _gripper_position_cb(self, msg):
        self._grip_cmd(msg.data)

    def _ja_cb(self, ja, enableOverride=False):
        if self._enabled or enableOverride:
            point = JointTrajectoryPoint()
            point.positions = ja.angles.data
            point.time_from_start = rospy.Duration.from_sec(self._joint_step_delay)
            self._arm_move(point)

    def _arm_move(self, p):
        traj = JointTrajectory()
        traj.header.stamp = rospy.Time.now()
        traj.header.frame_id = 'world'
        traj.joint_names = self._arm_joint_names
        traj.points = [p]
        self._traj_pub.publish(traj)

    def _grip_cmd(self, ja):
        cmd = GripperCmd()
        cmd.position = ja # value between 0 (closed) and 0.085 (open)
        cmd.speed = self._gripper_speed
        cmd.force = self._gripper_effort
        self._grip_cmd_pub.publish(cmd)

    def _set_initial_pose_cb(self, noop):
        ja = JointAngles()
        ja.angles.data = self._starting_config
        self._ja_cb(ja,True)


if __name__ == "__main__":
    rospy.init_node("rik_ur_hw_interface")

    info_file_path = rospy.get_param('~info_file_path')
    arm_joint_step_delay = rospy.get_param('~arm_joint_step_delay',DEFAULT_ARM_JOINT_STEP_DELAY)
    gripper_speed = rospy.get_param('~gripper_speed',DEFAULT_GRIPPER_SPEED)
    gripper_effort = rospy.get_param('~gripper_effort',DEFAULT_GRIPPER_EFFORT)
    start_enabled = rospy.get_param('~start_enabled',DEFAULT_START_ENABLED)

    node = RikUrHwInterfaceNode(info_file_path, arm_joint_step_delay, gripper_speed,
                              gripper_effort, start_enabled)
    rospy.spin()
