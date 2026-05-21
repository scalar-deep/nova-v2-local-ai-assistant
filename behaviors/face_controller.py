class FaceController:
    @staticmethod
    def face_for_text(text: str, mood: str = "calm") -> str:
        t = text.lower()

        if any(x in t for x in ["sorry", "error", "wrong"]):
            return "irritated"

        if any(x in t for x in ["great", "glad", "happy", "nice"]):
            return "happy_eye_glistening"

        if any(x in t for x in ["hmm", "interesting", "maybe"]):
            return "thinking"

        if mood == "curious":
            return "winking"

        if mood == "lonely":
            return "cry_sad"

        if mood == "sleepy":
            return "idle"

        return "happy"
