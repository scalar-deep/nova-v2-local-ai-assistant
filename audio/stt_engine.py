"""
Whisper.cpp STT wrapper.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import os


class WhisperSTT:
    """Whisper.cpp speech-to-text engine."""
    
    def __init__(
        self,
        whisper_path: str = "/usr/local/bin/whisper-cpp",
        model_path: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/whisper.cpp/models/ggml-base.en-q5_0.bin",
        language: str = "en",
        threads: int = 4
    ):
        self.whisper_path = whisper_path
        self.model_path = model_path
        self.language = language
        self.threads = threads
        
        # Verify paths
        if not Path(whisper_path).exists():
            # Try alternative paths
            alt_paths = [
                "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/whisper.cpp/build/bin/whisper-cli",
                "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/whisper.cpp/main",
            ]
            for alt in alt_paths:
                if Path(alt).exists():
                    self.whisper_path = alt
                    break
            else:
                raise FileNotFoundError(f"Whisper not found at {whisper_path}")
        
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found at {model_path}")
    
    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file to text.
        
        Args:
            audio_path: Path to WAV file (16kHz, mono, 16-bit)
        
        Returns:
            Transcribed text
        """
        # Run whisper.cpp
        process = subprocess.run(
            [
                self.whisper_path,
                "-m", self.model_path,
                "-f", audio_path,
                "-l", self.language,
                "-t", str(self.threads),
                "--no-timestamps",
                "-np"  # No prints except results
            ],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            raise RuntimeError(f"Whisper failed: {process.stderr}")
        
        # Parse output
        text = process.stdout.strip()
        
        # Clean up common artifacts
        text = text.replace("[BLANK_AUDIO]", "").strip()
        
        return text
    
    def transcribe_audio_array(self, audio, sample_rate: int = 16000) -> str:
        """
        Transcribe audio from numpy array.
        
        Args:
            audio: Numpy array of audio samples
            sample_rate: Sample rate of audio
        
        Returns:
            Transcribed text
        """
        import numpy as np
        import wave
        
        # Save to temp file
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        try:
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())
            
            return self.transcribe(temp_path)
        finally:
            os.unlink(temp_path)
