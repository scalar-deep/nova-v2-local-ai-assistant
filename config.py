"""
Configuration management for Nova-V2.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json


@dataclass
class Config:
    """Application configuration."""

    # Paths (adjusted for actual installation location)
    project_root: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release"
    assets_path: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/assets/face"

    # Audio - Piper TTS (using piper-tts Python package)
    piper_voice: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/piper/voices/en_GB-semaine-medium.onnx"

    # Whisper.cpp
    whisper_path: str = "/usr/local/bin/whisper-cpp"
    whisper_model: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/whisper.cpp/models/ggml-base.en.bin"

    # Models
    chat_model: str = "qwen2.5:1.5b"

    # Wake word
    wake_word_model: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/models/wake_word/hey_jarvis_v0.1.onnx"
    wake_word_threshold: float = 0.30

    # Microphone settings (for USB mics that may have different sample rates)
    mic_sample_rate: int = 48000

    # Local location default
    local_location: str = "Kingston, CA"
    target_sample_rate: int = 16000

    # API Keys (loaded from environment)
    openweather_api_key: str = ""
    moonshot_api_key: str = ""
    newsapi_key: str = ""

    # Soul/personality files
    local_soul_path: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/config/local_soul.md"
    cloud_soul_path: str = "/home/pi/projects/test_bot/Nova_OpenWakeModel_release/config/cloud_soul.md"

    # Display
    display_width: int = 800
    display_height: int = 480
    use_framebuffer: bool = True

    # Features
    enable_streaming_tts: bool = False
    enable_ui: bool = True

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from file and environment."""
        config = cls()

        # Load from JSON file if exists
        if config_path is None:
            config_path = os.path.join(config.project_root, "config", "config.json")

        if Path(config_path).exists():
            with open(config_path) as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

        # Load from .env file if present
        env_path = os.path.join(config.project_root, ".env")
        if Path(env_path).exists():
            config._load_env_file(env_path)

        # Override with environment variables
        config.openweather_api_key = os.getenv(
            "OPENWEATHER_API_KEY",
            config.openweather_api_key
        )
        config.moonshot_api_key = os.getenv(
            "MOONSHOT_API_KEY",
            config.moonshot_api_key
        )
        config.newsapi_key = os.getenv(
            "NEWSAPI_KEY",
            config.newsapi_key
        )

        return config

    def _load_env_file(self, path: str):
        """Load environment variables from .env file."""
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    def save(self, config_path: Optional[str] = None):
        """Save configuration to file."""
        if config_path is None:
            config_path = os.path.join(self.project_root, "config", "config.json")

        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        # Don't save API keys to file
        data = {
            k: v for k, v in self.__dict__.items()
            if not k.endswith("_api_key") and not k.endswith("_key")
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
