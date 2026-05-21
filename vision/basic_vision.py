import cv2
from pathlib import Path


class BasicVisionAnalyzer:
    def __init__(self):
        cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade)

    def analyze(self, image_path: str) -> str:
        path = Path(image_path)

        if not path.exists():
            return "I could not find the captured image."

        img = cv2.imread(str(path))

        if img is None:
            return "I captured an image, but I could not read it."

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        brightness = gray.mean()

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=3,
            minSize=(40, 40),
        )

        face_count = len(faces)

        if brightness < 45:
            light_text = "It looks quite dark."
        elif brightness > 170:
            light_text = "It looks bright."
        else:
            light_text = "The lighting looks normal."

        if face_count == 0:
            if brightness < 60:
                return "It looks dark, and I cannot clearly make out your face."
            face_text = "I do not clearly see a face."
        elif face_count == 1:
            face_text = "I can see one face."
        else:
            face_text = f"I can see {face_count} faces."

        return f"{face_text} {light_text}"
