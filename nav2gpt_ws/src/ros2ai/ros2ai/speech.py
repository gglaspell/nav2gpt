"""Best-effort text-to-speech via espeak.

No ROS imports, so it's safe to unit-test. Speaking is best-effort: on a
headless machine with no audio device espeak just makes no sound, and any
failure is swallowed so navigation is never blocked by TTS.
"""
import shutil
import subprocess


def speak(text):
    """Speak `text` aloud via espeak if it's available. Never raises; returns text."""
    if text and shutil.which("espeak"):
        try:
            subprocess.run(
                ["espeak", str(text)], check=False, timeout=10,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    return text
