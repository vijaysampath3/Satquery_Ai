"""
Application Settings and Configuration for SatQuery AI.
"""

import os
from pathlib import Path

# BASE_DIR points to SAT_Query repository root directory
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR: Path = BASE_DIR / "backend"


def _load_dotenv():
    """Load key-value pairs from .env file into os.environ if present."""
    for env_path in [BACKEND_DIR / ".env", BASE_DIR / ".env"]:
        if env_path.is_file():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, _, val = line.partition("=")
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key and key not in os.environ:
                                os.environ[key] = val
            except Exception:
                pass


_load_dotenv()


class Settings:
    """Central configuration for SatQuery AI backend."""

    # ── Paths ──
    BASE_DIR: Path = BASE_DIR
    BACKEND_DIR: Path = BACKEND_DIR
    RESULTS_DIR: Path = BASE_DIR / "results"
    MODELS_DIR: Path = BASE_DIR / "models"
    DATA_DIR: Path = BASE_DIR / "data"

    # ── LLM / Summarizer ──
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")

    # ── Qwen2.5-VL ──
    QWEN_MODEL_PATH: str = os.environ.get(
        "QWEN_MODEL_PATH",
        str(MODELS_DIR / "vqa" / "qwen25vl"),
    )

    # ── Server ──
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "8000"))
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",   # VS Code Live Server
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",                      # file:// protocol
    ]

    # ── GPU ──
    MAX_VRAM_GB: float = float(os.environ.get("MAX_VRAM_GB", "8.0"))

    # ── Uploads ──
    MAX_UPLOAD_SIZE_MB: int = 50
    TEMP_DIR: str = os.environ.get("TEMP_DIR", "/tmp/satquery")


settings = Settings()

# Ensure dirs exist
settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)

