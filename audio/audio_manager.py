"""
Audio Manager - Handles microphone input and speaker output with muting.
"""

import sounddevice as sd
import numpy as np
import wave
import subprocess
from threading import Lock
from typing import Optional


def _find_device_by_name(name_substring: str, kind: str) -> int:
    """Find a sounddevice device index by name substring.

    Args:
        name_substring: Partial device name to match, e.g. "USB PnP Sound Device"
        kind: "input" or "output"

    Returns:
        Device index, or raises RuntimeError if not found.
    """
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"

    for i, d in enumerate(devices):
        if name_substring.lower() in d["name"].lower() and d[channel_key] > 0:
            return i

    raise RuntimeError(
        "Audio device matching '{}' ({}) not found. Available: {}".format(
            name_substring,
            kind,
            [(i, d["name"]) for i, d in enumerate(devices)]
        )
    )


def _find_alsa_card_by_name(name_substring: str) -> str:
    """Find ALSA card number by name, returns 'plughw:N,0' string."""
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            check=True
        )

        for line in result.stdout.splitlines():
            if line.startswith("card ") and name_substring in line:
                card_num = line.split(":")[0].replace("card ", "").strip()
                return "plughw:{},0".format(card_num)

    except Exception:
        pass

    return "plughw:0,0"


# Device name substrings for lookup
MIC_NAME = "USB PnP Sound Device"
SPEAKER_NAME = "UACDemoV1.0"


class AudioManager:
    """Manages microphone input and speaker output with muting."""

    def __init__(
        self,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        channels: int = 1,
        dtype: str = "int16"
    ):
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.channels = channels
        self.dtype = dtype

        self.is_muted = False
        self._mute_lock = Lock()
        self._recording = False
        self._audio_buffer = []

        # Resolve device indices at init time
        self.mic_device = _find_device_by_name(MIC_NAME, "input")
        self.speaker_alsa = _find_alsa_card_by_name(SPEAKER_NAME)

        print("    Mic: device {} ({})".format(self.mic_device, MIC_NAME))
        print("    Speaker: {} ({})".format(self.speaker_alsa, SPEAKER_NAME))

    def mute(self):
        """Mute microphone input during TTS playback."""
        with self._mute_lock:
            self.is_muted = True

    def unmute(self):
        """Unmute microphone input."""
        with self._mute_lock:
            self.is_muted = False

    def _normalize(self, audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
        """Apply gain normalization for weak USB mics."""
        if audio.size == 0:
            return audio.astype(np.int16)

        peak = np.max(np.abs(audio.astype(np.float64)))

        # Avoid boosting pure silence / very tiny noise
        if peak < 50:
            return audio.astype(np.int16)

        gain = (target_peak * 32767) / peak
        normalized = audio.astype(np.float64) * gain

        return np.clip(normalized, -32768, 32767).astype(np.int16)

    def _resample_to_target_rate(self, audio: np.ndarray) -> np.ndarray:
        """Properly resample mic audio to the target sample rate for Whisper."""
        if self.mic_sample_rate == self.sample_rate:
            return audio.astype(np.int16)

        try:
            from scipy.signal import resample_poly

            resampled = resample_poly(
                audio.astype(np.float32),
                self.sample_rate,
                self.mic_sample_rate
            )

            return np.clip(resampled, -32768, 32767).astype(np.int16)

        except Exception as e:
            print("Resample failed, falling back to simple decimation:", e)

            # Fallback for exact 48kHz -> 16kHz
            if self.mic_sample_rate == 48000 and self.sample_rate == 16000:
                return audio[::3].astype(np.int16)

            return audio.astype(np.int16)

    def record_until_silence(
        self,
        silence_threshold: float = 0.004,
        silence_duration: float = 2.5,
        max_duration: float = 30.0
    ) -> Optional[np.ndarray]:
        """
        Record audio until silence is detected.

        Records at mic_sample_rate, then resamples properly to sample_rate.
        The returned audio is what gets sent to Whisper.
        """
        if self.is_muted:
            return None

        self._audio_buffer = []
        self._recording = True

        silence_blocks = 0
        blocks_needed_for_silence = int(silence_duration * self.mic_sample_rate / 4096)
        max_blocks = int(max_duration * self.mic_sample_rate / 4096)
        total_blocks = 0

        def callback(indata, frames, time, status):
            if status:
                # Ignore non-fatal overflow on USB mic
                pass

            if self.is_muted or not self._recording:
                return

            self._audio_buffer.append(indata.copy())

        stream = sd.InputStream(
            device=self.mic_device,
            samplerate=self.mic_sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=8192,
            latency="high",
            callback=callback
        )


        stream.start()

        try:
            print("Fixed STT recording test: recording 7 seconds...")
            sd.sleep(7000)

        finally:
            stream.stop()
            stream.close()

        self._recording = False

        if len(self._audio_buffer) == 0:
            return None

        raw_audio = np.concatenate(self._audio_buffer, axis=0).flatten()
        normalized = raw_audio.astype(np.int16)        
        resampled = self._resample_to_target_rate(normalized)

        # Debug: save exactly what Whisper receives
        try:
            self.save_to_wav(resampled, "debug_last_stt.wav")
            print("Saved debug_last_stt.wav")
        except Exception as e:
            print("Failed to save debug STT wav:", e)

        return resampled

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        """Save audio array to WAV file."""
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.astype(np.int16).tobytes())

    def play_wav(self, filepath: str):
        """Play a WAV file through speakers."""
        self.mute()

        try:
            subprocess.run(
                ["paplay", filepath],
                check=True,
                capture_output=True
            )

        except FileNotFoundError:
            import wave as wav_mod

            with wav_mod.open(filepath, "rb") as wf:
                audio_data = np.frombuffer(
                    wf.readframes(wf.getnframes()),
                    dtype=np.int16
                )

                sd.play(audio_data, wf.getframerate())
                sd.wait()

        except Exception as e:
            print("Playback error: {}".format(e))

        finally:
            self.unmute()

    def play_audio(self, audio: np.ndarray):
        """Play audio array through speakers."""
        self.mute()

        try:
            sd.play(audio, self.sample_rate)
            sd.wait()

        finally:
            self.unmute()
