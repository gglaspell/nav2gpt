#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from ros2ai_msgs.srv import Nav2Gpt

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

        self.llm = OllamaLLM(
            model="llama3"
        )  # assuming you have Ollama installed and have llama3 model pulled with `ollama pull llama3 `

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
            self.req.x = float(args["x"])
            self.req.y = float(args["y"])
            self.req.theta = float(args["theta"])
            self.future = self.cli.call_async(self.req)
            rclpy.spin_until_future_complete(self, self.future)
            print(self.future.result())
            # Implement your logic to execute goToPose command
        elif service_name == "wait":
            print("Executing wait")
            time.sleep(5)
            # Implement your logic to execute wait command
        else:
            print(f"Unknown service: {service}")



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
            choice = input("Press Enter to start recording, or 'x' to inject a canned transcript... ")
        else:
            choice = input("Press Enter to start recording...")

        if DEV_MODE_CANNED_TRANSCRIPT and choice.strip().lower() == "x":
            transcript_text = CANNED_TRANSCRIPT
            print(f"[DEV MODE] Using canned transcript: {transcript_text!r}")
        else:
            filename = "recorded_audio.wav"
            duration = 10  # seconds
            node.record_audio(filename, duration)

            print("Transcribing...")
            model = whisper.load_model("base")
            transcription = model.transcribe(filename)
            transcript_text = transcription["text"]
            print("Transcription:", transcript_text)

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
                    remember these the coordinates of the kitchen is x: -4, y: 4, theta: 180

        the coordinates of the bedroom is x: 3, y: 4, theta: 0
                        
                        
        """

        prompt += transcript_text

        prompt += """
        

                            
                            Respond only with the output in the exact format specified in the system prompt, with no explanation or conversation.\
                        ",
        """

        # print(prompt)

        result = node.llm.invoke(prompt)
        print("LLM raw output:", result)

        # llama3 sometimes wraps the JSON in prose or ```json fences. Extract the
        # first [...] array (or {...} object) so a valid goal isn't lost to a
        # bare json.loads() that only accepts a clean list.
        commands = parse_commands(result)
        if not commands:
            print("ERROR: could not parse a command list from the LLM output above.")
        # Iterate through each command and execute
        for command in commands:
            node.execute_command(command)


        # rclpy.spin(node)
    except Exception as e:
        print(f"Exception: {e}")
    rclpy.shutdown()
