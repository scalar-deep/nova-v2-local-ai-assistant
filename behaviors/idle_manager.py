import random
import time


class IdleManager:
    def __init__(self):
        self.last_idle_action = 0

    def should_trigger(self, cooldown=8):
        return (time.time() - self.last_idle_action) > cooldown

    def next_face(self, mood="calm"):
        self.last_idle_action = time.time()

        if mood == "sleepy":
            return random.choice([
                "idle",
                "cry_sad",
            ])

        if mood == "curious":
            return random.choice([
                "thinking",
                "winking",
            ])

        return random.choice([
            "happy",
            "thinking",
            "winking",
            "happy_eye_glistening",
        ])
