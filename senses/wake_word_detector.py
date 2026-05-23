"""
Wake word detection using openWakeWord.

Permanent reliability version:
- Opens the USB mic stream for wake-word listening.
- Automatically restarts the mic stream if audio chunks stop arriving.
- Periodically refreshes the stream even if it looks healthy.
- Drops old queued audio instead of letting the queue grow.
- Resets the wake-word model after detections and resumes.
"""

import time
import numpy as np
import sounddevice as sd
from queue import Queue, Empty, Full
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
    """Detects wake word using openWakeWord with self-healing audio stream."""

    def __init__(
        self,
        model_path: str = "",
        threshold: float = 0.5,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        inference_framework: str = "onnx",
        gain_target_peak: float = 0.9,
        no_audio_restart_seconds: float = 8.0,
        stream_refresh_seconds: float = 180.0,
    ):
        if not OPENWAKEWORD_AVAILABLE:
            raise RuntimeError("openwakeword not installed. Run: pip install openwakeword")

        self.threshold = threshold
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.gain_target_peak = gain_target_peak
        self.no_audio_restart_seconds = no_audio_restart_seconds
        self.stream_refresh_seconds = stream_refresh_seconds

        # openWakeWord expects 16 kHz chunks of 1280 samples.
        # At 48 kHz, collect 3840 samples and decimate to 16 kHz.
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
        print("    Wake watchdog: restart if no audio for {:.1f}s".format(self.no_audio_restart_seconds))
        print("    Wake watchdog: refresh stream every {:.1f}s".format(self.stream_refresh_seconds))

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

        # Small bounded queue prevents stale audio buildup.
        self._audio_queue: Queue = Queue(maxsize=30)

        self._gain = 4.0
        self._stream_restart_count = 0
        self._ignore_until = 0.0

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
        self._drain_queue()

        try:
            self.model.reset()
            print("[wake] model reset")
        except Exception as e:
            print("[wake] model reset error: {}".format(e))

        self._ignore_until = time.time() + 2.0
        print("[wake] ignoring wake detections for 2.0s after resume")

        self._resume_event.set()
        print("[wake] resume event set")

    def _drain_queue(self):
        cleared = 0
        while True:
            try:
                self._audio_queue.get_nowait()
                cleared += 1
            except Empty:
                break

        if cleared:
            print("[wake] cleared queued chunks: {}".format(cleared))

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
        """Convert mic audio chunk to 16 kHz for openWakeWord."""
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

    def _open_stream(self):
        def audio_callback(indata, frames, time_info, status):
            # Do not print inside this callback.
            # Printing here can cause more overflows on Raspberry Pi.
            try:
                self._audio_queue.put_nowait(bytes(indata))
            except Full:
                # Drop the oldest chunk and keep the newest one.
                try:
                    self._audio_queue.get_nowait()
                except Empty:
                    pass

                try:
                    self._audio_queue.put_nowait(bytes(indata))
                except Full:
                    pass

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
        return stream

    def _close_stream(self, stream):
        if not stream:
            return

        try:
            stream.stop()
        except Exception as e:
            print("[wake] stream stop error: {}".format(e))

        try:
            stream.close()
        except Exception as e:
            print("[wake] stream close error: {}".format(e))

    def _listen_loop(self):
        """Main listening loop. Self-heals by reopening the audio stream."""
        while self._running:
            print("[wake] waiting for resume event")
            self._resume_event.wait()
            print("[wake] resume event received")

            if not self._running:
                break

            self._drain_queue()

            try:
                self.model.reset()
            except Exception:
                pass

            stream = None
            detected = False
            restart_reason = ""

            try:
                stream = self._open_stream()
                stream_opened_at = time.time()
                last_audio_at = time.time()
                self._stream_restart_count += 1

                print("[wake] mic stream started/restarted count={}".format(
                    self._stream_restart_count
                ))

                while self._running and not self._paused:
                    now = time.time()

                    # Periodic refresh prevents long-running ALSA/sounddevice stalls.
                    if now - stream_opened_at >= self.stream_refresh_seconds:
                        restart_reason = "scheduled stream refresh"
                        break

                    try:
                        raw = self._audio_queue.get(timeout=0.25)
                        last_audio_at = time.time()
                    except Empty:
                        if time.time() - last_audio_at >= self.no_audio_restart_seconds:
                            restart_reason = "no audio chunks for {:.1f}s".format(
                                self.no_audio_restart_seconds
                            )
                            break
                        continue

                    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)

                    if audio.size == 0:
                        continue

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

                    if time.time() < self._ignore_until:
                        continue

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

            except Exception as e:
                restart_reason = "stream exception: {}".format(e)
                print("[wake] {}".format(restart_reason))

            finally:
                self._close_stream(stream)
                print("[wake] mic stream closed")

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

            elif self._running and not self._paused:
                if restart_reason:
                    print("[wake] restarting mic stream: {}".format(restart_reason))
                time.sleep(0.2)
                continue

        print("[wake] listen loop exited")
