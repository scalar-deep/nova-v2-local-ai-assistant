# Nova OpenWakeModel — Local AI Companion for Raspberry Pi

Nova is a local-first, wake-word-activated AI companion assistant for Raspberry Pi 5 and tiny Linux machines.

This repository contains the verified working checkpoint:

**Nova-V2 Emotional Companion Working**

Source checkpoint:

`pibot_local_agent_Nova_V2_emotional_companion_working`

Nova includes voice, memory, emotional reactions, safe camera capture, basic local vision, and a PyGame face UI.

## Current Status

This build includes:

- Wake word activation using the current `Hey Jarvis` openWakeWord model
- Whisper-based speech-to-text
- Piper text-to-speech
- Local AI routing through Ollama/local model
- Deterministic identity and capability responses
- Persistent simple memory for important facts
- Emotional companion layer
- Sad/happy/tired/angry detection
- Ask-one-question-and-wait behavior
- Safe on-demand camera snapshot using `rpicam-still`
- Basic local vision analysis using OpenCV
- PyGame face UI with emotional face assets

## Important

This repository intentionally does not include:

- Python virtual environments
- `.env` files
- API keys
- local model binaries
- camera captures
- `debug_last_stt.wav`
- broken experimental versions
- backup checkpoint folders

## Current Wake Word

The current working wake phrase is:

`Hey Jarvis`

Nova identity is already Nova-V2, but wake word training for `Hey Nova` is future work.

## Features

| Feature | How it works | API key needed? |
|---|---|---|
| Wake word | openWakeWord, phrase: `Hey Jarvis` | No |
| Speech recognition | Whisper-based STT | No |
| Text-to-speech | Piper TTS | No |
| Local AI routing | Ollama/local model fallback | No |
| Identity responses | Deterministic response layer | No |
| Memory | Simple persistent fact memory | No |
| Emotional companion | Deterministic emotional layer | No |
| Camera snapshot | `rpicam-still` on demand | No |
| Basic vision | OpenCV brightness and face-count analysis | No |
| Face UI | PyGame and PNG emotional face assets | No |

## Quick Start

```bash
git clone <YOUR_GITHUB_REPO_URL> Nova_OpenWakeModel
cd Nova_OpenWakeModel
chmod +x scripts/*.sh
./scripts/setup_system_pi.sh
./scripts/setup_venv.sh
source .venv313_sys/bin/activate
python orchestrator.py
```

Say:

`Hey Jarvis`

Then test:

```text
What do you do?
I am happy.
I am sad.
Ask me something.
Happy.
My favorite color is blue. Remember that.
What is my favorite color?
Take a picture.
What do you see?
```

## Camera Mode

Continuous camera presence is disabled intentionally.

Stable camera flow:

`voice command -> rpicam-still snapshot -> save image -> optional OpenCV analysis -> release camera`

This avoids camera lockups on Raspberry Pi.

## Hardware Requirements

- Raspberry Pi 5
- Raspberry Pi OS 64-bit
- USB microphone
- USB speaker or supported audio output
- Optional 800x480 display
- Optional Raspberry Pi camera compatible with `rpicam-still`
- Active cooling recommended
- 32 GB+ microSD or SSD/NVMe storage recommended

## Install Notes

Install system dependencies:

```bash
chmod +x scripts/*.sh
./scripts/setup_system_pi.sh
```

Create environment:

```bash
./scripts/setup_venv.sh
source .venv313_sys/bin/activate
```

Install or start Ollama if needed:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama
ollama list
```

Pull the configured model. Use the model your `config.py` expects.

```bash
ollama pull smollm2:135m
```

or:

```bash
ollama pull qwen2.5:1.5b
```

## Audio Test

```bash
arecord -l
aplay -l
arecord -d 3 test.wav
aplay test.wav
```

## Camera Test

```bash
rpicam-still -o test.jpg --width 640 --height 480 --timeout 1000
```

## How It Works

1. Wake word: Nova listens for `Hey Jarvis`.
2. Record: Audio Manager records speech and saves a debug WAV.
3. Transcribe: Whisper STT converts audio to text.
4. Pre-handle: deterministic handlers check memory, emotion, vision, and identity commands.
5. Route: if no deterministic match exists, router/local AI handles the query.
6. Respond: Piper TTS converts the response to speech.
7. Display: PyGame face UI shows the matching emotional/state face.
8. Return to idle: Nova goes back to wake-word listening.

## Emotional Companion Layer

Nova detects simple emotional phrases:

```text
I am happy.
I am sad.
I am tired.
I am angry.
Ask me something.
Talk to me.
```

Example:

```text
User: Ask me something.
Nova: Okay. What is one small thing that made today better or worse?
User: Happy.
Nova: I am glad to hear that. I like when things get a little better.
```

Nova does not repeatedly push follow-up questions by herself.

## Memory

Nova can remember simple facts.

```text
User: My favorite color is blue. Remember that.
Nova: I will remember that your favorite color is blue.
User: What is my favorite color?
Nova: Your favorite color is blue.
```

## Vision Safe Mode

Continuous camera presence is disabled. This is deliberate.

Earlier continuous camera experiments caused camera frontend timeouts and Picamera2 ownership errors.

Current stable camera flow:

```text
voice command -> rpicam-still snapshot -> save image -> optional OpenCV analysis -> release camera
```

Supported examples:

```text
Take a picture.
What do you see?
```

## Face UI

Nova uses PNG face assets stored in `assets/face/`.

Expected face names include:

```text
idle.png
happy.png
happy_eye_glistening.png
sad.png
cry_sad.png
emotional.png
emotional_cry.png
thinking.png
confused.png
surprised.png
winking.png
angry.png
irritated.png
listening.png
speaking_1.png
speaking_2.png
error.png
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Wake word does not trigger | Say `Hey Jarvis`, not `Hey Nova`. Check mic with `arecord -d 3 test.wav`. |
| STT is wrong | Play `debug_last_stt.wav`; move mic closer; reduce noise. |
| No speaker output | Run `aplay -l`; update audio output config. |
| Camera timeout | Test `rpicam-still`; do not enable continuous camera presence. |
| Face assets not loading | Check `ls assets/face`; ensure PNG filenames match expected names. |
| Ollama not responding | Run `systemctl status ollama`, `ollama list`, then restart Ollama. |
| Python import error | Activate `.venv313_sys` and install missing package. |

## Known Limitations

- Wake word still uses `Hey Jarvis`
- STT can mishear names and short phrases
- No heavy local object recognition yet
- No cloud vision yet
- No structured long-term memory database yet
- Continuous camera presence is disabled intentionally

## Development Rules

Do not commit:

```text
.venv313_sys/
.venv/
venv/
.env
debug_last_stt.wav
vision/captures/
backup folders
broken folders
model binaries
```

Recommended stable branch: `release/emotional-companion-working`

Recommended next development branch: `dev/nova-v2-next`

## Roadmap

- Replace `Hey Jarvis` with trained `Hey Nova` wake word
- Finalize professional 3D robot face pack
- Improve speaking face animation
- Improve STT accuracy carefully
- Add structured long-term memory
- Add on-demand cloud vision
- Add complete test suite
- Add demo videos to README

## License

MIT
