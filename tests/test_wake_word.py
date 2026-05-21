#!/usr/bin/env python3
"""
Test wake word detection.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_wake_word():
    """Test wake word model loading and basic detection."""
    from senses.wake_word_detector import WakeWordDetector
    
    print("Testing wake word detector...\n")
    
    # Test model loading
    try:
        detector = WakeWordDetector()
        print("✓ Wake word model loaded successfully")
    except FileNotFoundError as e:
        print(f"✗ Model not found: {e}")
        return False
    except Exception as e:
        print(f"✗ Error loading model: {e}")
        return False
    
    # Test listening (interactive)
    print("\nStarting interactive test...")
    print("Say 'Hey Nova-V2' to test detection.")
    print("Press Ctrl+C to stop.\n")
    
    detected = False
    
    def on_wake_word():
        nonlocal detected
        detected = True
        print("✓ Wake word detected!")
    
    try:
        detector.start(callback=on_wake_word)
        
        import time
        timeout = 30
        start = time.time()
        
        while not detected and (time.time() - start) < timeout:
            time.sleep(0.5)
        
        if not detected:
            print(f"No detection in {timeout} seconds")
        
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        detector.stop()
    
    return detected


if __name__ == "__main__":
    success = test_wake_word()
    sys.exit(0 if success else 1)
