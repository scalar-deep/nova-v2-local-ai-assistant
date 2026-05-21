import time
import cv2
from dataclasses import dataclass
from picamera2 import Picamera2


@dataclass
class PresenceState:
    present: bool
    face_count: int
    last_seen: float


class PresenceDetector:
    def __init__(self):
        self.picam2 = None
        self.last_seen = 0
        cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade)

    def start(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(1)
        return True

    def stop(self):
        if self.picam2:
            self.picam2.stop()

    def check(self):
        if not self.picam2:
            return PresenceState(False, 0, self.last_seen)

        frame = self.picam2.capture_array()
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=3,
            minSize=(40, 40),
        )

        present = len(faces) > 0
        if present:
            self.last_seen = time.time()

        return PresenceState(present, len(faces), self.last_seen)
