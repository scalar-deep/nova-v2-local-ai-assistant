# Nova-V2 Current Working State

This state is working with the following wake/STT settings:

- Wake threshold: 0.3
- Wake no-audio restart: 8.0 seconds
- Wake scheduled stream refresh: 180.0 seconds
- Wake ignore after resume: 2.0 seconds
- STT silence duration: 1.5 seconds
- STT max duration: 15.0 seconds
- STT silence threshold: 0.008
- STT blocksize: 1024

Observed behavior:
- Wake word resumes after each interaction.
- Wake watchdog can recover the mic stream after no-audio stalls.
- UI remains alive.
- Camera capture and 3-second photo preview work.
- Some STT recordings reach 15 seconds, but commands are still generally recognized.

Do not tune wake settings unless logs prove the wake stream is actually stuck.
