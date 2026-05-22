"""
Audio Manager - Handles microphone input and speaker output with muting.
"""

import sounddevice as sd
import numpy as np
import wave
import subprocess
import time
from threading import Lock
from typing import Optional


def _find_device_by_name(name_substring: str, kind: str) -> int:
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
                return "plughw:{},0"

    except Exception:
        pass

    return "default"


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

        self.mic_device = _find_device_by_name(MIC_NAME, "input")
        self.speaker_alsa = _find_alsa_card_by_name(SPEAKER_NAME)

        print("    Mic: device {} ({})".format(self.mic_device, MIC_NAME))
        print("    Speaker: {} ({})".format(self.speaker_alsa, SPEAKER_NAME))

    def mute(self):
        with self._mute_lock:
            self.is_muted = True

    def unmute(self):
        with self._mute_lock:
            self.is_muted = False

    def _resample_to_target_rate(self, audio: np.ndarray) -> np.ndarray:
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

            if self.mic_sample_rate == 48000 and self.sample_rate == 16000:
                return audio[::3].astype(np.int16)

            return audio.astype(np.int16)

    def record_until_silence(
        self,
        silence_threshold: float = 0.008,
        silence_duration: float = 1.5,
        max_duration: float = 15.0,
        min_duration: float = 0.8
    ) -> Optional[np.ndarray]:
        """
        Record speech until silence is detected.

        Records at mic_sample_rate and returns 16kHz audio for Whisper.
        """
        if self.is_muted:
            print("[audio] recording blocked because mic is muted")
            return None

        self._audio_buffer = []
        self._recording = True

        blocksize = 1024
        silence_blocks = 0
        speech_seen = False
        total_blocks = 0

        blocks_needed_for_silence = max(1, int(silence_duration * self.mic_sample_rate / blocksize))
        min_blocks = max(1, int(min_duration * self.mic_sample_rate / blocksize))
        max_blocks = max(1, int(max_duration * self.mic_sample_rate / blocksize))

        def callback(indata, frames, time_info, status):
            if status:
                # Keep this quiet. Printing every overflow causes more trouble.
                pass

            if self.is_muted or not self._recording:
                return

            self._audio_buffer.append(indata.copy())

        stream = None

        try:
            stream = sd.InputStream(
                device=self.mic_device,
                samplerate=self.mic_sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=blocksize,
                latency="high",
                callback=callback
            )

            stream.start()
            print("[audio] listening for speech...")

            while total_blocks < max_blocks:
                time.sleep(blocksize / self.mic_sample_rate)
                total_blocks += 1

                if len(self._audio_buffer) == 0:
                    continue

                latest = self._audio_buffer[-1].astype(np.float32).flatten()
                rms = float(np.sqrt(np.mean(latest * latest)) / 32768.0)

                if rms >= silence_threshold:
                    speech_seen = True
                    silence_blocks = 0
                else:
                    if speech_seen and total_blocks >= min_blocks:
                        silence_blocks += 1

                if speech_seen and silence_blocks >= blocks_needed_for_silence:
                    print("[audio] silence detected")
                    break

            if not speech_seen:
                print("[audio] no speech detected")

        finally:
            self._recording = False

            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception as e:
                    print("[audio] stream close error:", e)

        if len(self._audio_buffer) == 0:
            return None

        raw_audio = np.concatenate(self._audio_buffer, axis=0).flatten().astype(np.int16)

        if not speech_seen:
            return None

        raw_duration = len(raw_audio) / float(self.mic_sample_rate)
        resampled = self._resample_to_target_rate(raw_audio)
        final_duration = len(resampled) / float(self.sample_rate)

        print("[audio] raw duration: {:.2f}s at {} Hz".format(raw_duration, self.mic_sample_rate))
        print("[audio] final duration: {:.2f}s at {} Hz".format(final_duration, self.sample_rate))

        try:
            self.save_to_wav(resampled, "debug_last_stt.wav")
            print("[audio] saved debug_last_stt.wav")
        except Exception as e:
            print("[audio] failed to save debug STT wav:", e)

        return resampled

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.astype(np.int16).tobytes())

    def play_wav(self, filepath: str):
        self.mute()

        try:
            subprocess.run(
                ["paplay", filepath],
                check=True,
                capture_output=True
            )

        except FileNotFoundError:
            with wave.open(filepath, "rb") as wf:
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
        self.mute()

        try:
            sd.play(audio, self.sample_rate)
            sd.wait()

        finally:
            self.unmute()
