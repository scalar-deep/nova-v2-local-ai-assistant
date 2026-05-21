"""
Piper TTS wrapper with streaming support.
Uses the piper-tts Python package.
"""

import tempfile
import os
import wave
from pathlib import Path
from typing import Optional, Generator

# Use piper-tts Python package
try:
    from piper import PiperVoice
    from piper.voice import SynthesisConfig
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False


class PiperTTS:
    """Piper TTS engine wrapper using piper-tts Python package."""
    
    def __init__(
        self,
        model_path: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/piper/voices/en_GB-semaine-medium.onnx",
        speaking_rate: float = 1.0,
        speaker_id: int = 0  # For multi-speaker models
    ):
        self.model_path = model_path
        self.speaking_rate = speaking_rate
        self.speaker_id = speaker_id
        self._voice = None
        
        # Verify model exists
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Voice model not found at {model_path}")
        
        # Load the voice model
        if PIPER_AVAILABLE:
            self._voice = PiperVoice.load(model_path)
        else:
            raise RuntimeError("piper-tts package not installed. Run: pip install piper-tts")
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> str:
        """
        Synthesize text to speech.
        
        Args:
            text: Text to synthesize
            output_path: Optional output path, generates temp file if None
        
        Returns:
            Path to generated WAV file
        """
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        
        # Use piper-tts 1.4.1 API: synthesize_wav handles wav format automatically
        syn_config = SynthesisConfig(speaker_id=self.speaker_id)
        with wave.open(output_path, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file, syn_config=syn_config)
        
        return output_path
    
    def synthesize_to_audio(self, text: str):
        """
        Synthesize text directly to audio array.
        
        Args:
            text: Text to synthesize
        
        Returns:
            Tuple of (audio_bytes, sample_rate)
        """
        # Collect raw PCM from the streaming synthesize() iterator
        audio_parts = []
        syn_config = SynthesisConfig(speaker_id=self.speaker_id)
        for chunk in self._voice.synthesize(text, syn_config=syn_config):
            audio_parts.append(chunk.audio_int16_bytes)
        
        audio_bytes = b"".join(audio_parts)
        sample_rate = self._voice.config.sample_rate
        
        return audio_bytes, sample_rate
