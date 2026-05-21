# Nova Build Log

## Nova-V1 Freeze
Date: 2026-05-20

Status:
- Wake word working
- STT working
- TTS working
- UI face working
- Local SmolLM/Ollama response working
- Bluetooth speaker working
- Camera available
- Needs personality control and Nova-V2 emotion/presence upgrade

## Nova-V2 Goal
- Presence detection
- Emotion engine
- Idle behavior loop
- SmolLM JSON response format
- Short controlled replies
- Nova naming cleanup

## Nova-V2 Vision Checkpoint
- Wake word working in .venv313_sys
- Camera module working through Picamera2
- PresenceDetector integrated
- Face detected on wake cycle
- Face controller binding active
- Deterministic fact / identity / wellbeing responses active

## Vision Safe Basic Vision Checkpoint
- Continuous Picamera2 presence disabled for stability
- SnapshotCamera uses rpicam-still on demand
- Camera opens only when asked and releases after capture
- "Take a picture" captures image
- "What do you see?" captures and performs lightweight local analysis
- BasicVisionAnalyzer detects face count and brightness
- Dim-room response improved
- Works on Raspberry Pi 5 1GB-safe architecture
