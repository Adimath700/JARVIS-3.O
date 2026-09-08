from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    ollama_think: bool = env_bool("OLLAMA_THINK", False)
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
    ollama_num_predict: int = int(os.getenv("OLLAMA_NUM_PREDICT", "128"))
    ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    gemini_vision_model: str = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash")
    whisper_model: str = os.getenv("WHISPER_MODEL", "tiny.en")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    piper_exe: str = os.getenv("PIPER_EXE", "")
    piper_voice: str = os.getenv("PIPER_VOICE", "en_US-lessac-medium")
    screen_dir: Path = ROOT / os.getenv("JARVIS_SCREEN_DIR", "data/screenshots")
    log_dir: Path = ROOT / os.getenv("JARVIS_LOG_DIR", "data/logs")
    presentation_dir: Path = ROOT / os.getenv(
        "JARVIS_PRESENTATION_DIR", "data/presentations"
    )
    memory_file: Path = ROOT / os.getenv(
        "JARVIS_MEMORY_FILE", "data/memory/memory.json"
    )

    def ensure_dirs(self):
        self.screen_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.presentation_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
