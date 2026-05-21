#!/usr/bin/env python3
"""
Test the complete audio pipeline.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_tts():
    """Test text-to-speech."""
    from audio.tts_engine import PiperTTS
    from audio.audio_manager import AudioManager
    
    print("Testing TTS...")
    
    try:
        tts = PiperTTS()
        audio_path = tts.synthesize("Hello! I am Nova-V2, your personal assistant.")
        
        audio = AudioManager()
        audio.play_wav(audio_path)
        print("✓ TTS working")
        return True
    except Exception as e:
        print(f"✗ TTS failed: {e}")
        return False


def test_stt():
    """Test speech-to-text."""
    from audio.audio_manager import AudioManager
    from audio.stt_engine import WhisperSTT
    
    print("\nTesting STT...")
    print("Speak now... (recording for up to 10 seconds)")
    
    try:
        audio = AudioManager()
        recording = audio.record_until_silence(max_duration=10.0)
        
        if recording is None or len(recording) == 0:
            print("✗ No audio recorded")
            return False
        
        stt = WhisperSTT()
        text = stt.transcribe_audio_array(recording)
        print(f"✓ Transcribed: {text}")
        return True
    except Exception as e:
        print(f"✗ STT failed: {e}")
        return False


def test_round_trip():
    """Test full round-trip: speak -> transcribe -> speak back."""
    from audio.audio_manager import AudioManager
    from audio.tts_engine import PiperTTS
    from audio.stt_engine import WhisperSTT
    
    print("\nTesting round-trip...")
    print("Say something, I'll repeat it back...")
    
    try:
        audio = AudioManager()
        tts = PiperTTS()
        stt = WhisperSTT()
        
        # Record
        recording = audio.record_until_silence()
        if recording is None:
            print("✗ No audio recorded")
            return False
        
        # Transcribe
        text = stt.transcribe_audio_array(recording)
        print(f"You said: {text}")
        
        # Speak back
        response = f"You said: {text}"
        audio_path = tts.synthesize(response)
        audio.play_wav(audio_path)
        
        print("✓ Round-trip complete")
        return True
    except Exception as e:
        print(f"✗ Round-trip failed: {e}")
        return False


if __name__ == "__main__":
    results = []
    results.append(("TTS", test_tts()))
    results.append(("STT", test_stt()))
    results.append(("Round-trip", test_round_trip()))
    
    print("\n" + "="*40)
    print("Results:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    sys.exit(0 if all_passed else 1)
