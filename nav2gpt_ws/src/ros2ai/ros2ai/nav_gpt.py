#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy, QoSHistoryPolicy)

from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseWithCovarianceStamped
from cv_bridge import CvBridge
from ros2ai_msgs.srv import Nav2Gpt, FollowRoute
from ros2ai.status_report import (
    status_message, where_am_i_message, saved_location_message, need_name_message)
from ros2ai.locations import (
    destination_label, load_locations, save_location, default_store_path,
    describe_rooms)
from ros2ai.intents import parse_intent
from ros2ai.pose_utils import yaw_degrees
from ros2ai.routing import (
    resolve_route, step_announcement, route_summary, followup_ack,
    route_mode, waypoint_plan_phrase, waypoint_summary, travel_headings,
    through_fallback_phrase)
from ros2ai.route_memory import RouteMemory
from ros2ai.speech import speak

from langchain_ollama import OllamaLLM
# from PIL import Image

import base64
from io import BytesIO

import sounddevice as sd
import scipy.io.wavfile as wav
import whisper

import time
import json


def parse_commands(text):
    """Extract a list of command dicts from an LLM response.

    Tolerates prose, ```json fences, or a single object instead of a list, so a
    valid goal isn't dropped by a bare json.loads() that requires a clean list.
    Returns a list (possibly empty).
    """
    if not text:
        return []
    # Try the whole thing first (clean case).
    for candidate in (text, _first_json_block(text)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return parsed
    return []


def _command_goal(command):
    """A ``{"x","y","theta"}`` goal from a parsed goToPose command, or None.

    Used to remember what the LLM path just drove to. Tolerant of a missing
    slash or malformed args so a stray command never crashes the remembering.
    """
    try:
        service = str(command.get("service", "")).strip().lstrip("/")
        if service != "goToPose":
            return None
        args = command["args"]
        return {"x": float(args["x"]), "y": float(args["y"]),
                "theta": float(args["theta"])}
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _first_json_block(text):
    """Return the first balanced [...] or {...} block found in text, or None."""
    start = None
    for i, ch in enumerate(text):
        if ch in "[{":
            start = i
            open_ch, close_ch = ch, "]" if ch == "[" else "}"
            break
    if start is None:
        return None
    depth = 0
    for j in range(start, len(text)):
        if text[j] == open_ch:
            depth += 1
        elif text[j] == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    return None


# --- DEV MODE -----------------------------------------------------------
# Lets you press 'x' at the recording prompt to skip the mic + Whisper and
# inject a known-good transcript instead (handy when you can't speak out
# loud, e.g. testing in a quiet office). MUST be flipped to False before
# merging this branch into main.
DEV_MODE_CANNED_TRANSCRIPT = True
CANNED_TRANSCRIPT = "Go to the kitchen"
# --------------------------------------------------------------------------


class NavGpt(Node):
    def __init__(self):
        super().__init__("nav_gpt")
        self.bridge = CvBridge()
        # self.img_sub = self.create_subscription("image_raw", Image, self.img_clbk, 10)
        self.cli = self.create_client(Nav2Gpt, 'goToPose')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')
        self.get_logger().info("connected to goToPose server")
        self.req = Nav2Gpt.Request()
        # Multi-stop routes (followWaypoints / goThroughPoses) go through a
        # separate list-of-poses service on the same server.
        self.route_cli = self.create_client(FollowRoute, 'followRoute')

        # Track the robot's estimated pose so "save this location" and "where am I"
        # can answer from the current position. AMCL publishes /amcl_pose latched
        # (TRANSIENT_LOCAL) and only republishes on motion, so we must match that
        # durability — otherwise a subscriber that joins while the robot is still
        # never receives the last pose.
        self.current_pose = None
        amcl_qos = QoSProfile(
            depth=1,
            history=QoSHistoryPolicy.KEEP_LAST,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._pose_clbk, amcl_qos)
        self.store_path = default_store_path()

        # Remembers the last route so "do that again" / "in reverse" can replay it.
        self.memory = RouteMemory()

        self.llm = OllamaLLM(
            model="llama3"
        )  # assuming you have Ollama installed and have llama3 model pulled with `ollama pull llama3 `

    def _pose_clbk(self, msg):
        self.current_pose = msg.pose.pose

    def get_current_pose(self, timeout_sec=5.0):
        """Spin briefly until an AMCL pose arrives; return (x, y, theta_deg) or None.

        Returns None if localization hasn't published a pose yet, so callers can
        say so instead of reporting a stale or made-up position.
        """
        deadline = self.get_clock().now().nanoseconds + int(timeout_sec * 1e9)
        while self.current_pose is None and \
                self.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self, timeout_sec=0.2)
        if self.current_pose is None:
            return None
        p = self.current_pose
        q = p.orientation
        return (p.position.x, p.position.y, yaw_degrees(q.x, q.y, q.z, q.w))

    def record_audio(self, filename, duration, fs=44100):
        print("Recording...")
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()  # Wait until recording is finished
        print("Recording finished.")
        wav.write(filename, fs, audio)  # Save as WAV file

    # Function to execute commands
    def execute_command(self, command):
        service = command["service"]
        args = command["args"]

        # Normalize: llama3 sometimes emits "goToPose" without the leading slash,
        # which would otherwise fall through to "Unknown service" and silently no-op.
        service_name = service.strip().lstrip("/")

        # Execute based on service
        if service_name == "goToPose":
            x = args["x"]
            y = args["y"]
            theta = args["theta"]
            print(f"Executing goToPose with x={x}, y={y}, theta={theta}")
            status = self._go_to_pose(x, y, theta)
            print(status_message(status, destination_label(x, y, path=self.store_path)))
        elif service_name == "wait":
            print("Executing wait")
            time.sleep(5)
            # Implement your logic to execute wait command
        else:
            print(f"Unknown service: {service}")

    def _go_to_pose(self, x, y, theta):
        """Send one goToPose goal and return the status string the server reports."""
        self.req.x = float(x)
        self.req.y = float(y)
        self.req.theta = float(theta)
        future = self.cli.call_async(self.req)
        rclpy.spin_until_future_complete(self, future)
        response = future.result()
        return response.status if response is not None else "NO_RESPONSE"

    def handle_route(self, route):
        """Drive an ordered list of stops as sequential goToPose goals.

        Announces each stop, stops early if one can't be reached (no point driving
        on to the next stop from an unknown position), and gives a spoken summary
        at the end. The route is remembered so a later "do that again" or "run it
        in reverse" can replay it.
        """
        self.memory.remember(route)
        total = len(route)
        reached = []
        for i, stop in enumerate(route, start=1):
            name = stop.get("name") or destination_label(
                stop["x"], stop["y"], path=self.store_path)
            self._say(step_announcement(i, total, name))
            status = self._go_to_pose(stop["x"], stop["y"], stop["theta"])
            if status != "SUCCEEDED":
                self._say(route_summary(reached, name, total))
                return
            reached.append(name)
        self._say(route_summary(reached, None, total))

    def handle_waypoint_route(self, route, mode):
        """Drive the whole route as a single Nav2 task — goThroughPoses ("through")
        or followWaypoints ("waypoints") — via the followRoute service. Nav2 owns
        the sequencing, so there's one outcome for the route rather than a
        per-stop tally. The route is remembered like any other."""
        self.memory.remember(route)
        names = [stop.get("name") or destination_label(
            stop["x"], stop["y"], path=self.store_path) for stop in route]
        self._say(waypoint_plan_phrase(names, mode))
        if mode == "through":
            # A continuous pass can't stop to reorient, so aim intermediate stops
            # along the travel direction.
            status = self._follow_route(travel_headings(route), "through")
            if status != "SUCCEEDED":
                # goThroughPoses wedges on routes that pop in and out of rooms
                # through tight doorways; fall back to the waypoint follower,
                # which stops and replans fresh at each stop, so the command
                # still finishes.
                self._say(through_fallback_phrase())
                mode = "waypoints"
                status = self._follow_route(route, "waypoints")
        else:
            # followWaypoints stops at each stop, so it keeps the rooms' stored
            # arrival headings.
            status = self._follow_route(route, mode)
        self._say(waypoint_summary(status, names, mode))

    def _follow_route(self, route, mode):
        """Call the followRoute service with the pose list; return its status."""
        if not self.route_cli.wait_for_service(timeout_sec=5.0):
            return "NO_SERVICE"
        req = FollowRoute.Request()
        req.xs = [float(stop["x"]) for stop in route]
        req.ys = [float(stop["y"]) for stop in route]
        req.thetas = [float(stop["theta"]) for stop in route]
        req.mode = mode
        future = self.route_cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        response = future.result()
        return response.status if response is not None else "NO_RESPONSE"

    def _say(self, message):
        """Print and speak a message so feedback shows in the log and aloud."""
        print(message)
        speak(message)

    def handle_save(self, name):
        """Record the robot's current pose under `name` and persist it."""
        if not name:
            self._say(need_name_message())
            return
        pose = self.get_current_pose()
        if pose is None:
            self._say("I can't tell where I am yet — no localization pose available.")
            return
        x, y, theta = pose
        save_location(name, x, y, theta, path=self.store_path)
        self._say(saved_location_message(name, x, y))

    def handle_whereami(self):
        """Answer "where am I?" by naming the nearest known room, or the coords."""
        pose = self.get_current_pose()
        if pose is None:
            self._say("I can't tell where I am yet — no localization pose available.")
            return
        x, y, _ = pose
        self._say(where_am_i_message(destination_label(x, y, path=self.store_path)))

    def handle_navigate(self, transcript_text):
        """Turn a spoken command into navigation, cheapest path first.

        1. A multi-stop route over known rooms ("the kitchen, then the bedroom")
           resolves against the store and is driven directly — deterministic, no
           model round-trip. How it's driven depends on the phrasing: "patrol" /
           "go through" runs one continuous pass (goThroughPoses), "visit" /
           "waypoints" uses the waypoint follower, and the default arrives at
           each stop in turn (sequential goToPose).
        2. A bare follow-up ("do that again", "in reverse") with no room named
           replays the last route from memory.
        3. Anything else (a single goal, a novel place, a specific heading) goes
           to the LLM, exactly as before.
        """
        route = resolve_route(transcript_text, load_locations(self.store_path))
        if len(route) >= 2:
            mode = route_mode(transcript_text)
            if mode == "steps":
                self.handle_route(route)
            else:
                self.handle_waypoint_route(route, mode)
            return

        if not route:
            followup = self.memory.resolve_followup(transcript_text)
            if followup:
                self._say(followup_ack(followup["mode"]))
                self.handle_route(followup["route"])
                return

        self._llm_navigate(transcript_text)

    def _llm_navigate(self, transcript_text):
        """The LLM path: turn a spoken command into goToPose goals via llama3.

        The room coordinates come from the live store (describe_rooms) rather than
        two hardcoded lines, so a location saved at runtime can be a nav target.
        """
        rooms = describe_rooms(load_locations(self.store_path))
        prompt = """
        Use this JSON schema to achieve the user's goals:\n\
                {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "default": "/goToPose"
            },
            "args": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "min": -6,
                        "max": 10
                    },
                    "y": {
                        "type": "number",
                        "min": -6,
                        "max": 7
                    },
                    "theta": {
                        "type": "number",
                        "min": -180,
                        "max": 180
                    }
                },
                "required": [
                    "x",
                    "y",
                    "theta"
                ]
            }
        },
        "required": [
            "service",
            "args"
        ]
    }
    \n\
                Respond as a list of JSON objects.\
                Do not include explanations or conversation in the response


    "role": "user",
                    "content": f"\
                    remember these """ + rooms + """


        """

        prompt += transcript_text

        prompt += """



                            Respond only with the output in the exact format specified in the system prompt, with no explanation or conversation.\
                        ",
        """

        result = self.llm.invoke(prompt)
        print("LLM raw output:", result)

        # llama3 sometimes wraps the JSON in prose or ```json fences. Extract the
        # first [...] array (or {...} object) so a valid goal isn't lost to a
        # bare json.loads() that only accepts a clean list.
        commands = parse_commands(result)
        if not commands:
            print("ERROR: could not parse a command list from the LLM output above.")
        goals = []
        for command in commands:
            self.execute_command(command)
            goal = _command_goal(command)
            if goal:
                goals.append(goal)
        # Remember the goals so a later "do that again" works after an LLM command
        # too, not only after a deterministic multi-stop route.
        self.memory.remember(goals)

    def convert_to_base64(self, pil_image):
        """
        Convert PIL images to Base64 encoded strings

        :param pil_image: PIL image
        :return: Re-sized Base64 string
        """

        buffered = BytesIO()
        pil_image.save(buffered, format="JPEG")  # You can change the format if needed
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_str
    
    def plt_img_base64(self, img_base64):
        """
        Display base64 encoded string as image

        :param img_base64:  Base64 string
        """
        # Create an HTML img tag with the base64 string as the source
        image_html = f'<img src="data:image/jpeg;base64,{img_base64}" />'
        # Display the image by rendering the HTML
        # display(HTML(image_html))

    def img_clbk(self, msg: Image):
        try:
            self.img = self.bridge.imgmsg_to_cv2(msg)
            
        except:
            self.get_logger().error("cannot convert the msg to cv2")

    # def execute_command(self, msg: str):
    #     image_b64 = self.convert_to_base64(self.img)
    #     llm_with_image_context = self.bakllava.bind(images=[image_b64])
    #     llm_with_image_context.invoke("What do you see in the image")
    

def main(args=None):
    rclpy.init(args=args)
    try:
        node = NavGpt()

        if DEV_MODE_CANNED_TRANSCRIPT:
            choice = input(
                "Enter to record; 'x' for the canned goal; or type a command to inject... ")
        else:
            choice = input("Press Enter to start recording...")

        if DEV_MODE_CANNED_TRANSCRIPT and choice.strip().lower() == "x":
            transcript_text = CANNED_TRANSCRIPT
            print(f"[DEV MODE] Using canned transcript: {transcript_text!r}")
        elif DEV_MODE_CANNED_TRANSCRIPT and choice.strip():
            transcript_text = choice.strip()
            print(f"[DEV MODE] Using typed transcript: {transcript_text!r}")
        else:
            filename = "recorded_audio.wav"
            duration = 10  # seconds
            node.record_audio(filename, duration)

            print("Transcribing...")
            model = whisper.load_model("base")
            transcription = model.transcribe(filename)
            transcript_text = transcription["text"]
            print("Transcription:", transcript_text)

        # "save this location" and "where am I" act on the current pose, so they
        # are intercepted here; anything else goes to the LLM as a nav goal.
        intent = parse_intent(transcript_text)
        if intent["kind"] == "whereami":
            node.handle_whereami()
        elif intent["kind"] == "save":
            node.handle_save(intent["name"])
        else:
            node.handle_navigate(transcript_text)

        # rclpy.spin(node)
    except Exception as e:
        print(f"Exception: {e}")
    rclpy.shutdown()
