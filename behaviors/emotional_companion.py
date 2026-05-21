import random
import time


class EmotionalCompanion:
    def __init__(self):
        self.awaiting_reply = False
        self.last_question = ""

    SAD_WORDS = [
        "sad", "i am sad", "i'm sad", "i feel sad", "feeling sad",
        "i am upset", "i'm upset", "i feel low", "i feel down",
        "bad day", "not feeling good", "not okay", "lonely"
    ]

    HAPPY_WORDS = [
        "happy", "i am happy", "i'm happy", "i feel happy", "feeling good",
        "i am excited", "i'm excited", "good mood"
    ]

    TIRED_WORDS = [
        "i am tired", "i'm tired", "sleepy", "exhausted", "worn out"
    ]

    ANGRY_WORDS = [
        "i am angry", "i'm angry", "annoyed", "irritated", "frustrated"
    ]

    ASK_ME_WORDS = [
        "ask me something", "talk to me", "ask me a question"
    ]

    CRISIS_WORDS = [
        "hurt myself", "kill myself", "end my life", "suicide"
    ]

    JOKES = [
        "Tiny joke: Why did the robot sit down? Because it had a hard drive.",
        "Tiny joke: I tried to catch fog yesterday. I mist.",
        "Tiny joke: Why was the computer cold? It left its Windows open.",
        "Tiny joke: I told my camera a joke, but it could not focus.",
    ]

    QUESTIONS = [
        "What happened?",
        "Do you want to tell me about it?",
        "Should I try to cheer you up?",
        "Want another tiny joke?"
    ]

    def _contains_any(self, text, phrases):
        t = text.lower()
        return any(p in t for p in phrases)

    def handle(self, text):
        lowered = text.lower().strip()

        if self._contains_any(lowered, self.CRISIS_WORDS):
            return {
                "faces": ["sad", "emotional_cry"],
                "response": (
                    "I am really sorry you feel this way. Please contact someone you trust or emergency help now."
                )
            }

        if self._contains_any(lowered, self.SAD_WORDS):
            joke = random.choice(self.JOKES)
            question = random.choice(self.QUESTIONS)
            self.awaiting_reply = True
            self.last_question = question
            return {
                "faces": ["sad", "surprised", "winking", "happy_eye_glistening"],
                "response": (
                    f"I am sorry you feel sad. {joke} {question}"
                )
            }

        if self._contains_any(lowered, self.HAPPY_WORDS):
            self.awaiting_reply = True
            self.last_question = "What made you happy?"
            return {
                "faces": ["surprised", "happy_eye_glistening", "winking"],
                "response": (
                    "That is good to hear. What made you happy?"
                )
            }

        if self._contains_any(lowered, self.TIRED_WORDS):
            return {
                "faces": ["idle", "thinking", "happy"],
                "response": (
                    "You sound tired. Want me to keep things calm for a bit?"
                )
            }

        if self._contains_any(lowered, self.ANGRY_WORDS):
            return {
                "faces": ["irritated", "thinking", "happy"],
                "response": (
                    "That sounds frustrating. Want to tell me what annoyed you?"
                )
            }

        if self._contains_any(lowered, self.ASK_ME_WORDS):
            self.awaiting_reply = True
            self.last_question = "What is one small thing that made today better or worse?"
            return {
                "faces": ["thinking", "winking"],
                "response": (
                    "Okay. What is one small thing that made today better or worse?"
                )
            }

        return None

    def play_faces(self, ui, faces):
        if not ui or not hasattr(ui, "show_face"):
            return

        for face in faces:
            try:
                ui.show_face(face)
                print(f"[emotion face] {face}")
                time.sleep(0.45)
            except Exception as e:
                print(f"[emotion face error] {e}")
                break
