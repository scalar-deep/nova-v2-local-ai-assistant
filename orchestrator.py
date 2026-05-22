#!/usr/bin/env python3
"""
Main orchestrator - ties all components together.
"""

import sys
import os
import signal
import time
import threading
import random
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from audio.audio_manager import AudioManager
from audio.tts_engine import PiperTTS
from audio.stt_engine import WhisperSTT
from brain.ollama_client import OllamaClient
from brain.local_client import LocalAIClient
from brain.router import Router, ToolType
from brain.response_cleaner import clean_response, clean_nova_tone
from emotions.emotion_manager import EmotionManager
from behaviors.face_controller import FaceController
from vision.presence_detector import PresenceDetector
from vision.snapshot_camera import SnapshotCamera
from vision.basic_vision import BasicVisionAnalyzer
from memory.companion_memory import CompanionMemory
from behaviors.idle_manager import IdleManager
from behaviors.emotional_companion import EmotionalCompanion
from brain.tools.time_tool import get_current_time
from brain.tools.weather_tool import WeatherTool
from brain.tools.news_tool import NewsTool
from brain.tools.system_tool import get_system_status
from brain.tools.joke_tool import get_joke
from senses.wake_word_detector import WakeWordDetector

# Pre-generated filler WAVs in assets/fillers/
FILLER_WAVS = {
    "On it!": "assets/fillers/filler_0.wav",
    "Thinking...": "assets/fillers/filler_1.wav",
    "Give me a sec.": "assets/fillers/filler_2.wav",
    "Let me check.": "assets/fillers/filler_3.wav",
    "Working on it.": "assets/fillers/filler_4.wav",
}


class Orchestrator:
    """Main system orchestrator."""

    def __init__(self, config: Config):
        self.config = config
        self.emotions = EmotionManager()
        self.presence = PresenceDetector()
        self.snapshot_camera = SnapshotCamera()
        self.vision_analyzer = BasicVisionAnalyzer()
        self.idle_manager = IdleManager()
        self.emotional_companion = EmotionalCompanion()
        self.memory = CompanionMemory()
        self._running = False
        self._busy = False
        self.ui = None

        # Used to avoid accidental rapid duplicate processing
        self._last_wake_time = 0
        self._wake_cooldown_seconds = 2.0

        # Initialize components
        print("Initializing Nova-V2...")

        # Audio
        print("  - Audio manager")
        self.audio = AudioManager(
            sample_rate=config.target_sample_rate,
            mic_sample_rate=config.mic_sample_rate
        )

        print("  - TTS engine")
        self.tts = PiperTTS(model_path=config.piper_voice)

        print("  - STT engine")
        self.stt = WhisperSTT(
            whisper_path=config.whisper_path,
            model_path=config.whisper_model
        )

        # Brain
        print("  - Ollama router client")
        self.ollama = OllamaClient(model=config.chat_model)

        print("  - Local AI client")
        self.local_ai = LocalAIClient(
            base_url="http://localhost:11434",
            model="smollm2:135m"
        )

        print("  - Router")
        self.router = Router(self.ollama)

        # Tools
        self.weather = None
        self.news = None

        if config.openweather_api_key:
            print("  - Weather tool")
            try:
                self.weather = WeatherTool(api_key=config.openweather_api_key)
            except Exception as e:
                print(f"    Warning: Weather tool unavailable: {e}")

        if config.newsapi_key:
            print("  - News tool")
            try:
                self.news = NewsTool(api_key=config.newsapi_key)
            except Exception as e:
                print(f"    Warning: News tool unavailable: {e}")

        print("  - System status tool")
        print("  - Joke tool")

        # Senses
        print("  - Wake word detector")
        self.wake_word = WakeWordDetector(
            model_path=config.wake_word_model,
            threshold=config.wake_word_threshold,
            mic_sample_rate=config.mic_sample_rate
        )

        # UI optional
        if config.enable_ui:
            try:
                from ui.ui_manager import UIManager, UIState
                print("  - UI manager")
                self.ui = UIManager(
                    width=config.display_width,
                    height=config.display_height,
                    assets_path=config.assets_path,
                    use_framebuffer=config.use_framebuffer
                )
                self.UIState = UIState
            except Exception as e:
                print(f"    Warning: UI unavailable: {e}")
                try:
                    import pygame
                    pygame.quit()
                except Exception:
                    pass
                self.ui = None

        # Load pre-generated filler WAVs
        self._filler_wavs = {}
        for phrase, rel_path in FILLER_WAVS.items():
            abs_path = os.path.join(config.project_root, rel_path)
            if os.path.exists(abs_path):
                self._filler_wavs[phrase] = abs_path
            else:
                print(f"    Warning: Filler WAV missing: {rel_path}")

        if self._filler_wavs:
            print(f"  - Loaded {len(self._filler_wavs)} filler phrases")

        # Warm local model once so first real answer is less painful
        self._warm_local_ai()

        print("Initialization complete!")

    def _warm_local_ai(self):
        """Warm up Ollama local model at startup."""
        try:
            print("  - Warming local AI model")
            self.local_ai.ask("Reply with one word: ready")
            print("    Local AI ready")
        except Exception as e:
            print(f"    Warning: Local AI warmup failed: {e}")

    def start(self):
        """Start the assistant."""
        self._running = True

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start UI if available
        if self.ui:
            self.ui.start()

        # Presence detector disabled in Vision Safe Mode.
        # Camera is used only by SnapshotCamera/rpicam-still on demand.
            self.ui.set_state(self.UIState.IDLE)

        # Speak startup message BEFORE starting wake word detection
        self._speak(
            "Hello! I am Nova version two, an integrated robotic system "
            "initialized and ready for deployment. Say Hey Jarvis to activate me."
        )

        # Start wake word detection after greeting finishes
        self.wake_word.start(callback=self._on_wake_word)

        print("Nova-V2 is running. Say 'Hey Jarvis' to activate.")
        print("Press Ctrl+C to exit.")

        # Main loop
        while self._running:
            time.sleep(0.1)

        self._cleanup()

        # Force exit to kill lingering daemon threads such as sounddevice streams
        os._exit(0)

    def _presence_loop(self):
        last_present = False
        seen_count = 0
        missing_count = 0
        last_reaction = 0

        while self._running:
            try:
                # Do not touch camera while Nova is listening/thinking/speaking.
                if hasattr(self, "_busy") and self._busy:
                    time.sleep(3)
                    continue

                # Presence check disabled in Vision Safe Mode.
                time.sleep(3)
                continue
                now = time.time()

                if state.present:
                    seen_count += 1
                    missing_count = 0
                else:
                    missing_count += 1
                    seen_count = 0

                stable_present = seen_count >= 3
                stable_missing = missing_count >= 8

                if stable_present and not last_present and now - last_reaction > 20:
                    print(f"[presence] user appeared faces={state.face_count}")
                    self.emotions.happiness += 5
                    self.emotions.curiosity += 3
                    self.emotions.loneliness -= 8
                    self.emotions._clamp()

                    if self.ui and hasattr(self.ui, "show_face"):
                        self.ui.show_face("surprised")
                        time.sleep(0.6)
                        self.ui.show_face("happy_eye_glistening")

                    last_reaction = now
                    last_present = True

                elif stable_missing and last_present:
                    print("[presence] user left")
                    last_present = False

                # autonomous idle behavior
                if not state.present and self.idle_manager.should_trigger():
                    snap = self.emotions.snapshot()

                    if self.ui and hasattr(self.ui, "show_face"):
                        idle_face = self.idle_manager.next_face(snap.mood)
                        self.ui.show_face(idle_face)
                        print(f"[idle] face={idle_face}")

            except Exception as e:
                print(f"[presence loop error] {e}")

            time.sleep(3)


    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\nShutting down...")
        self._running = False

    def _cleanup(self):
        """Clean up resources."""
        try:
            self.wake_word.stop()
        except Exception as e:
            print(f"Wake word cleanup error: {e}")

        if self.ui:
            try:
                self.ui.stop()
            except Exception as e:
                print(f"UI cleanup error: {e}")

    def _on_wake_word(self):
        """Called when wake word is detected."""
        if not self._running:
            return

        now = time.time()
        if now - self._last_wake_time < self._wake_cooldown_seconds:
            print("Ignoring duplicate wake word")
            return
        self._last_wake_time = now

        print("Wake word detected!")
        self._busy = True

        try:
            # Clear conversation history — each wake word is a fresh interaction
            self.router.clear_history()

            # Pause wake word detection while STT/TTS uses audio
            try:
                self.wake_word.pause()
            except Exception as e:
                print(f"Wake word pause error: {e}")

            # Wake-cycle presence check disabled in Vision Safe Mode.

            if self.ui:
                self.ui.set_state(self.UIState.LISTENING)

            # Record user speech
            print("Listening...")
            audio = self.audio.record_until_silence(
                silence_duration=1.5,
                max_duration=15.0
            )

            if audio is None or len(audio) == 0:
                print("No speech detected")
                return

            if self.ui:
                self.ui.set_state(self.UIState.THINKING)

            # Transcribe
            print("Transcribing...")
            try:
                text = self.stt.transcribe_audio_array(audio)
                print(f"User said: {text}")
                self.memory.set_last_user_message(text)
                self.emotions.on_user_spoke()
            except Exception as e:
                print(f"Transcription error: {e}")
                self._speak("Sorry, I didn't catch that.")
                return

            if not text.strip():
                print("Blank transcription")
                self._speak("I didn't hear anything.")
                return

            # Speak a random filler phrase before processing
            text_lower = text.lower()
            if "on camera" not in text_lower:
                self._speak_filler()

            # Route and respond
            try:
                self._process_query(text)
            except Exception as e:
                print(f"Processing error: {e}")
                self.emotions.on_error()
                self._speak("Sorry, something went wrong.")
                if self.ui:
                    self.ui.set_state(self.UIState.ERROR)
                time.sleep(1)

        finally:
            self._busy = False

            if self.ui:
                try:
                    self.ui.set_state(self.UIState.IDLE)
                except Exception as e:
                    print(f"UI idle error: {e}")

            try:
                self.wake_word.resume()
            except Exception as e:
                print(f"Wake word resume error: {e}")

    def _speak_filler(self):
        """Play a random pre-generated filler phrase."""
        if not self._filler_wavs:
            return

        phrase = random.choice(list(self._filler_wavs.keys()))
        wav_path = self._filler_wavs[phrase]
        print(f"Filler: {phrase}")

        try:
            self.audio.play_wav(wav_path)
        except Exception as e:
            print(f"Filler playback error: {e}")

    def _process_query(self, text: str):
        """Process user query through router."""

        text_lower = text.lower()

        # Custom action: "on camera" introduction
        if "on camera" in text_lower:
            print("[custom] on camera introduction")
            self._speak(
                "Hey all, I am Nova version two, Arun's personal AI assistant, "
                "running locally on this Raspberry Pi. It is great to meet you all."
            )
            return

        lowered = text.lower().strip()

        remember_triggers = [
            "remember what i said last",
            "remember my last message",
            "remember that",
            "save that",
            "save this",
            "keep that in memory",
            "store that",
            "don't forget that",
            "do not forget that",
            "make a note of that",
            "note that down",
            "remember this",
            "remember what i just said",
            "keep this for later",
        ]

        recall_triggers = [
            "what do you remember",
            "what did i tell you to remember",
            "tell me what you remember",
            "recall my memory",
            "recall what i said",
            "what did i say earlier",
            "what was the last thing you remembered",
            "show your memory",
            "list your memories",
        ]

        if any(trigger in lowered for trigger in remember_triggers):

            # Favorite color extraction
            if "favorite color is" in lowered or "favourite color is" in lowered:

                if "favorite color is" in lowered:
                    value = lowered.split("favorite color is", 1)[-1]
                else:
                    value = lowered.split("favourite color is", 1)[-1]

                for trigger in remember_triggers:
                    value = value.replace(trigger, "")

                value = value.strip(" .!?,")

                response = self.memory.remember_fact("favorite_color", value)

            # Name extraction
            elif "my name is" in lowered:

                value = lowered.split("my name is", 1)[-1]

                for trigger in remember_triggers:
                    value = value.replace(trigger, "")

                value = value.strip(" .!?,")

                response = self.memory.remember_fact("name", value)

            else:
                response = self.memory.remember_last()

            self._speak(response)
            return

        if any(trigger in lowered for trigger in recall_triggers):
            response = self.memory.recall_memories()
            self._speak(response)
            return

        if "favorite color" in lowered or "favourite color" in lowered:
            response = self.memory.recall_fact("favorite_color")
            self._speak(response)
            return

        if "what is my name" in lowered or "do you know my name" in lowered:
            response = self.memory.recall_fact("name")
            self._speak(response)
            return

        if "take a picture" in lowered or "take photo" in lowered or "capture image" in lowered or "what do you see" in lowered:
            try:
                path = self.snapshot_camera.capture()
                print(f"[vision] snapshot saved: {path}")

                if self.ui and hasattr(self.ui, "show_image"):
                    self.ui.show_image(path, duration=3.0)
                    time.sleep(3.0)

                    if self.ui:
                        self.ui.set_state(self.UIState.IDLE)
                else:
                    print("[ui] show_image not available")

                if "what do you see" in lowered:
                    response = self.vision_analyzer.analyze(path)
                    self._speak(response)
                else:
                    self._speak("I captured an image.")

            except Exception as e:
                print(f"[vision error] {e}")
                self._speak("Sorry, I could not access the camera.")
            return

        # If Nova asked an emotional question, treat the next user reply as the answer.
        if getattr(self.emotional_companion, "awaiting_reply", False):
            self.emotional_companion.awaiting_reply = False
            lowered_reply = lowered.strip().lower()

            if not lowered_reply:
                self._speak("That's okay. We can talk later.")
                return

            if "bad" in lowered_reply or "sad" in lowered_reply or "worse" in lowered_reply:
                self._speak("I understand. I will stay with you quietly for a bit.")
                return

            if "happy" in lowered_reply or "good" in lowered_reply or "better" in lowered_reply:
                self._speak("I am glad to hear that. I like when things get a little better.")
                return

            self._speak("Thank you for telling me.")
            return

        emotional = self.emotional_companion.handle(text)
        if emotional:
            self.emotional_companion.play_faces(self.ui, emotional["faces"])
            self._speak(emotional["response"])
            return

        result = self.router.route(text)

        if result.tool == ToolType.NONE:
            print("[local ollama router] Direct chat response")
            self._speak(clean_response(result.response))

        elif result.tool == ToolType.TIME:
            print("[tool] get_current_time")
            response = get_current_time()
            self._speak(response)

        elif result.tool == ToolType.WEATHER:
            if self.weather:
                location = result.arguments.get("location") or self.config.local_location
                print(f"[tool] get_weather → {location}")
                response = self.weather.get_weather(location)
                self._speak(response)
            else:
                self._speak("Sorry, weather lookup is not configured.")

        elif result.tool == ToolType.NEWS:
            if self.news:
                category = result.arguments.get("category", "")
                print(f"[tool] get_news → {category or 'general'}")
                response = self.news.get_news(category)
                self._speak(response)
            else:
                self._speak("Sorry, news lookup is not configured.")

        elif result.tool == ToolType.SYSTEM_STATUS:
            print("[tool] get_system_status")
            response = get_system_status()
            self._speak(response)

        elif result.tool == ToolType.JOKE:
            print("[tool] get_joke")
            response = get_joke()
            self._speak(response)

        elif result.tool == ToolType.CLOUD:
            print("[local smollm2:135m] Replacing cloud handoff with local AI")
            query = result.arguments.get("query", text)
            self._handle_local_ai_query(query)

        else:
            print(f"[unknown route] {result.tool}")
            self._handle_local_ai_query(text)

    def _handle_local_ai_query(self, query: str):
        """Handle general AI query using local Ollama model."""
        try:
            response = self.local_ai.ask(query)
            print(f"Local AI: {response}")
            self._speak(response)
        except Exception as e:
            print(f"Local AI error: {e}")
            self._speak("Sorry, the local AI model is not responding.")

    def _speak(self, text: str):
        """Speak text through TTS."""
        text = clean_nova_tone(text)
        if not text:
            return

        print(f"Speaking: {text}")
        self.emotions.on_nova_spoke()

        try:
            snap = self.emotions.snapshot()
            face = FaceController.face_for_text(text, snap.mood)

            if self.ui and hasattr(self.ui, "show_face"):
                self.ui.show_face(face)
            elif self.ui and hasattr(self.ui, "set_face"):
                self.ui.set_face(face)

            print(f"[face] {face}")

        except Exception as e:
            print(f"[face error] {e}")

        if self.ui:
            self.ui.set_state(self.UIState.SPEAKING)

        try:
            audio_path = self.tts.synthesize(text)
            self.audio.play_wav(audio_path)
        except Exception as e:
            print(f"TTS error: {e}")

        if self.ui:
            self.ui.set_state(self.UIState.IDLE)


def main():
    """Main entry point."""
    config = Config.load()
    orchestrator = Orchestrator(config)
    orchestrator.start()


if __name__ == "__main__":
    main()
