# Nova-V2 Evidence Package

This folder contains evidence supporting the README claims for the Nova-V2 Emotional Companion Working release.

## Evidence Map

| Claim | Evidence |
|---|---|
| GitHub release is clean and tagged | `git/git_release_status.txt` |
| Runs on Raspberry Pi / tiny Linux | `system/system_info.txt` |
| Successful boot | `logs/full_runtime_demo.log` |
| Wake word works | `logs/01_wake_word.log` |
| STT works | `logs/02_stt.log`, `audio/debug_last_stt.wav` |
| TTS works | `logs/03_tts.log` |
| Deterministic identity works | `logs/04_identity_routing.log` |
| Memory recall works | `logs/05_memory.log` |
| Emotional companion works | `logs/06_emotional_companion.log` |
| Camera snapshot works | `logs/07_camera_snapshot.log`, `images/capture_test.jpg` |
| Basic vision works | `logs/08_basic_vision.log` |
| Face UI works | `logs/09_face_ui.log` |
| Camera safe mode/code proof | `logs/10_camera_safe_mode_code_check.log` |

## Honest Notes

- STT can mishear short phrases and names.
- The runtime demo includes both successful commands and imperfect STT examples.
- Camera is used on demand and released after snapshot.
