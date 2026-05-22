"""
Wake word detection using openWakeWord.
"""

import time
import numpy as np
import sounddevice as sd
from queue import Queue, Empty
from typing import Callable, Optional
from threading import Thread, Event
from pathlib import Path

try:
    from openwakeword.model import Model
    import openwakeword
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False


MIC_NAME = "USB PnP Sound Device"


def _find_mic_device() -> int:
    """Find the USB mic device index by name."""
    devices = sd.query_devices()

    for i, d in enumerate(devices):
        if MIC_NAME.lower() in d["name"].lower() and d["max_input_channels"] > 0:
            return i

    raise RuntimeError(
        "Mic '{}' not found. Available: {}".format(
            MIC_NAME,
            [(i, d["name"]) for i, d in enumerate(devices)]
        )
    )


def _find_bundled_model(name: str) -> str:
    """Find a bundled openWakeWord model by name."""
    pkg_dir = Path(openwakeword.__file__).parent / "resources" / "models"

    for f in pkg_dir.glob("{}*.onnx".format(name)):
        return str(f)

    raise FileNotFoundError(
        "Bundled model {} not found in {}".format(name, pkg_dir)
    )


class WakeWordDetector:
    """Detects wake word using openWakeWord."""

    def __init__(
        self,
        model_path: str = "",
        threshold: float = 0.5,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        inference_framework: str = "onnx",
        gain_target_peak: float = 0.9
    ):
        if not OPENWAKEWORD_AVAILABLE:
            raise RuntimeError("openwakeword not installed. Run: pip install openwakeword")

        self.threshold = threshold
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.gain_target_peak = gain_target_peak

        if self.mic_sample_rate == 16000:
            self.mic_chunk_size = 1280
        elif self.mic_sample_rate == 48000:
            self.mic_chunk_size = 3840
        else:
            self.mic_chunk_size = int(self.mic_sample_rate * 0.08)

        self.mic_device = _find_mic_device()
        print("    Wake word mic: device {} ({})".format(self.mic_device, MIC_NAME))
        print("    Wake word mic sample rate: {}".format(self.mic_sample_rate))
        print("    Wake word threshold: {}".format(self.threshold))

        use_custom = model_path and Path(model_path).exists()

        if use_custom:
            print("    Wake word model: custom {}".format(model_path))
            self.model = Model(wakeword_model_paths=[model_path])
        else:
            jarvis_path = _find_bundled_model("hey_jarvis")
            print("    Wake word model: bundled {}".format(jarvis_path))
            self.model = Model(wakeword_model_paths=[jarvis_path])

        self._running = False
        self._stop_event = Event()
        self._resume_event = Event()
        self._thread: Optional[Thread] = None
        self._callback: Optional[Callable] = None
        self._paused = False
        self._audio_queue: Queue = Queue()
        self._gain = 4.0
        self._last_score_log = 0.0
        self._last_chunk_log = 0.0

    def start(self, callback: Callable[[], None]):
        """Start listening for wake word."""
        if self._running:
            print("[wake] start ignored; already running")
            return

        self._callback = callback
        self._running = True
        self._paused = False
        self._stop_event.clear()
        self._resume_event.set()

        self._thread = Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("[wake] detector thread started")

    def stop(self):
        """Stop listening."""
        print("[wake] stop requested")
        self._running = False
        self._paused = False
        self._stop_event.set()
        self._resume_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            print("[wake] detector thread stopped")

    def pause(self):
        """Pause detection and release the mic stream."""
        print("[wake] pause requested")
        self._paused = True
        self._resume_event.clear()

    def resume(self):
        """Resume detection and reopen mic stream."""
        print("[wake] resume requested")
        self._paused = False

        cleared = 0
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
                cleared += 1
            except Empty:
                break

        if cleared:
            print("[wake] cleared queued chunks: {}".format(cleared))

        try:
            self.model.reset()
            print("[wake] model reset")
        except Exception as e:
            print("[wake] model reset error: {}".format(e))

        self._resume_event.set()
        print("[wake] resume event set")

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Apply adaptive gain normalization for weak USB mics."""
        if audio.size == 0:
            return audio.astype(np.int16)

        peak = np.max(np.abs(audio))

        if peak < 50:
            return audio.astype(np.int16)

        target = self.gain_target_peak * 32767
        desired_gain = target / peak
        desired_gain = min(desired_gain, 8.0)

        self._gain = 0.3 * desired_gain + 0.7 * self._gain
        self._gain = min(self._gain, 8.0)

        gained = np.clip(audio * self._gain, -32768, 32767)
        return gained.astype(np.int16)

    def _to_16k(self, audio: np.ndarray) -> np.ndarray:
        """Convert mic audio chunk to 16kHz for openWakeWord."""
        if self.mic_sample_rate == 16000:
            return audio.astype(np.int16)

        if self.mic_sample_rate == 48000:
            return audio[::3].astype(np.int16)

        try:
            from scipy.signal import resample_poly

            resampled = resample_poly(
                audio.astype(np.float32),
                self.sample_rate,
                self.mic_sample_rate
            )

            return np.clip(resampled, -32768, 32767).astype(np.int16)

        except Exception as e:
            print("[wake] resample failed:", e)
            return audio.astype(np.int16)

    def _listen_loop(self):
        """Main listening loop. Reopens stream after each pause/resume cycle."""
        while self._running:
            print("[wake] waiting for resume event")
            self._resume_event.wait()
            print("[wake] resume event received")

            if not self._running:
                break

            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except Empty:
                    break

            def audio_callback(indata, frames, time_info, status):
                # Do not print every overflow from inside the audio callback.
                # Printing here can make overflows worse on Raspberry Pi.
                self._audio_queue.put(bytes(indata))

            stream = None

            try:
                stream = sd.RawInputStream(
                    device=self.mic_device,
                    samplerate=self.mic_sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=self.mic_chunk_size,
                    latency="high",
                    callback=audio_callback
                )
                stream.start()
                print("[wake] mic stream started")

            except Exception as e:
                print("[wake] stream error: {}".format(e))
                if stream:
                    try:
                        stream.close()
                    except Exception:
                        pass
                if self._running:
                    self._stop_event.wait(timeout=1.0)
                continue

            detected = False

            try:
                while self._running and not self._paused:
                    try:
                        raw = self._audio_queue.get(timeout=0.1)
                    except Empty:
                        now = time.time()
                        if now - self._last_chunk_log > 5:
                            print("[wake] alive but no audio chunks; paused={} queue={}".format(
                                self._paused,
                                self._audio_queue.qsize()
                            ))
                            self._last_chunk_log = now
                        continue

                    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
                    normalized = self._normalize(audio)
                    audio_16k = self._to_16k(normalized)

                    try:
                        predictions = self.model.predict(audio_16k)
                    except Exception as e:
                        print("[wake] prediction error: {}".format(e))
                        try:
                            self.model.reset()
                        except Exception:
                            pass
                        continue

                    now = time.time()
                    if now - self._last_score_log > 5:
                        best = max(predictions.values()) if predictions else 0.0
                        peak = int(np.max(np.abs(audio))) if audio.size else 0
                        print("[wake] alive paused={} queue={} peak={} best_score={:.3f}".format(
                            self._paused,
                            self._audio_queue.qsize(),
                            peak,
                            best
                        ))
                        self._last_score_log = now

                    for model_name, score in predictions.items():
                        if score >= self.threshold:
                            print(
                                "Wake word detected! ({}, score: {:.3f})".format(
                                    model_name,
                                    score
                                )
                            )
                            detected = True
                            break

                    if detected:
                        break

            finally:
                try:
                    stream.stop()
                    stream.close()
                    print("[wake] mic stream closed")
                except Exception as e:
                    print("[wake] stream close error: {}".format(e))

            if detected and self._callback:
                self._paused = True
                self._resume_event.clear()

                try:
                    self.model.reset()
                except Exception as e:
                    print("[wake] model reset before callback error: {}".format(e))

                try:
                    self._callback()
                except Exception as e:
                    print("[wake] callback error: {}".format(e))
                    self.resume()

        print("[wake] listen loop exited")
