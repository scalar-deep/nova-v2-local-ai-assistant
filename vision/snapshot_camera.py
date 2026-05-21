import subprocess
import time
from pathlib import Path


class SnapshotCamera:
    def __init__(self):
        self.output_dir = Path("vision/captures")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture(self):
        filename = f"capture_{int(time.time())}.jpg"
        path = self.output_dir / filename

        cmd = [
            "rpicam-still",
            "-o", str(path),
            "--width", "640",
            "--height", "480",
            "--timeout", "1000",
            "--nopreview",
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"[vision] captured {path}")
            print("[vision] camera released")
            return str(path)
        except Exception as e:
            print(f"[vision error] {e}")
            return None
