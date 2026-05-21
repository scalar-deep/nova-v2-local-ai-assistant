import time
from dataclasses import dataclass


@dataclass
class EmotionSnapshot:
    mood: str
    face: str
    happiness: int
    curiosity: int
    energy: int
    loneliness: int


class EmotionManager:
    def __init__(self):
        self.happiness = 55
        self.curiosity = 50
        self.energy = 60
        self.loneliness = 10
        self.last_interaction = time.time()

    def _clamp(self):
        self.happiness = max(0, min(100, self.happiness))
        self.curiosity = max(0, min(100, self.curiosity))
        self.energy = max(0, min(100, self.energy))
        self.loneliness = max(0, min(100, self.loneliness))

    def on_user_spoke(self):
        self.last_interaction = time.time()
        self.happiness += 4
        self.curiosity += 6
        self.loneliness -= 8
        self._clamp()

    def on_nova_spoke(self):
        self.energy -= 1
        self._clamp()

    def on_error(self):
        self.happiness -= 4
        self.energy -= 4
        self._clamp()

    def tick(self):
        idle = time.time() - self.last_interaction
        if idle > 60:
            self.loneliness += 1
            self.energy -= 1
        if idle > 180:
            self.happiness -= 1
        self._clamp()

    def mood(self):
        if self.energy < 25:
            return "sleepy"
        if self.loneliness > 60:
            return "lonely"
        if self.happiness > 70:
            return "happy"
        if self.curiosity > 70:
            return "curious"
        return "calm"

    def face(self):
        return {
            "sleepy": "idle",
            "lonely": "cry_sad",
            "happy": "happy_eye_glistening",
            "curious": "winking",
            "calm": "happy",
        }.get(self.mood(), "happy")

    def snapshot(self):
        return EmotionSnapshot(
            mood=self.mood(),
            face=self.face(),
            happiness=self.happiness,
            curiosity=self.curiosity,
            energy=self.energy,
            loneliness=self.loneliness,
        )
