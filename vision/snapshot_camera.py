import time
from pathlib import Path

from picamera2 import Picamera2


class SnapshotCamera:
    def __init__(self):
        self.output_dir = Path("vision/captures")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture(self):
        filename = f"capture_{int(time.time())}.jpg"
        path = self.output_dir / filename

        picam2 = None

        try:
            picam2 = Picamera2()

            config = picam2.create_preview_configuration(
                main={"size": (640, 480)}
            )

            picam2.configure(config)
            picam2.start()

            time.sleep(1.0)

            picam2.capture_file(str(path))

            print(f"[vision] captured {path}")

            return str(path)

        finally:
            try:
                if picam2:
                    picam2.stop()
                    picam2.close()
                    print("[vision] camera released")
            except Exception as e:
                print(f"[vision] release error: {e}")
